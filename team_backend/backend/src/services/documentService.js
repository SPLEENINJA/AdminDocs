import path from 'path';
import { randomUUID } from 'crypto';
import { readDb, writeDb } from './db.js';
import { processDocument } from './mockProcessingService.js';
import { uploadToRaw, uploadJsonToClean } from './minioService.js';

// File d'attente globale : les documents uploadés ensemble sont traités 1 par 1
let pipelineQueue = Promise.resolve();

function enqueuePipeline(documentId) {
  pipelineQueue = pipelineQueue
    .then(() => runPipeline(documentId))
    .catch((err) => console.error(`[pipeline] Erreur doc ${documentId}:`, err));
}

export async function createUploadedDocuments(files) {
  const db = await readDb();

  const createdDocs = files.map((file) => ({
    id: randomUUID(),
    filename: file.originalname,
    storedFilename: file.filename,
    mimetype: file.mimetype,
    size: file.size,
    status: 'uploaded',
    step: 'raw_storage',
    createdAt: new Date().toISOString(),
    rawPath: path.posix.join('/raw', file.filename),
    cleanPath: null,
    curatedPath: null,
    ocrText: '',
    documentType: null,
    extractedData: null,
    validation: null,
    supplierId: null,
    previewUrl: `/uploads/${file.filename}`
  }));

  db.documents.unshift(...createdDocs);
  await writeDb(db);

  // Enfile chaque document dans la queue — traitement séquentiel garanti
  for (const doc of createdDocs) {
    enqueuePipeline(doc.id);
  }

  return createdDocs;
}

export async function runPipeline(documentId) {
  console.log(`[pipeline] Début traitement : ${documentId}`);

  let db = await readDb();
  const document = db.documents.find((item) => item.id === documentId);
  if (!document) return;

  // 1. Upload vers MinIO raw (awaité pour garantir l'ordre)
  const uploadDir = path.resolve('src/uploads');
  const filePath = path.join(uploadDir, document.storedFilename);
  await uploadToRaw(document.storedFilename, filePath, document.mimetype);

  // 2. Marquer en cours
  document.status = 'processing';
  document.step = 'ocr';
  await writeDb(db);

  // 3. OCR
  const result = await processDocument(document);

  // 4. Relire la DB fraîche avant d'écrire (évite les conflits résiduels)
  db = await readDb();
  const currentDoc = db.documents.find((item) => item.id === documentId);
  if (!currentDoc) return;

  currentDoc.status = 'processed';
  currentDoc.step = 'validation';
  currentDoc.documentType = result.documentType;
  currentDoc.ocrText = result.ocrText;
  currentDoc.extractedData = result.extractedData;
  currentDoc.validation = result.validation;
  currentDoc.cleanPath = `/clean/${documentId}.json`;
  currentDoc.curatedPath = `/curated/${documentId}.json`;

  const supplierId = upsertSupplierFromDocument(db, currentDoc);
  currentDoc.supplierId = supplierId;
  currentDoc.status = 'validated';
  currentDoc.step = 'completed';
  await writeDb(db);

  // 5. Upload résultat OCR vers MinIO clean (awaité)
  await uploadJsonToClean(documentId, {
    documentId,
    filename: document.filename,
    storedFilename: document.storedFilename,
    documentType: result.documentType,
    extractedData: result.extractedData,
    validation: result.validation,
    ocrText: result.ocrText,
    processedAt: new Date().toISOString(),
  });

  console.log(`[pipeline] Terminé : ${documentId}`);
}

function upsertSupplierFromDocument(db, document) {
  if (!document.extractedData) return null;

  const { supplierName, siret, vat, iban, address } = document.extractedData;
  let supplier = db.suppliers.find((item) => item.siret === siret);

  if (!supplier) {
    supplier = {
      id: randomUUID(),
      supplierName,
      siret,
      vat,
      iban,
      address,
      status: document.validation?.status === 'validated' ? 'verified' : 'pending',
      documentIds: [document.id],
      createdAt: new Date().toISOString()
    };
    db.suppliers.unshift(supplier);
  } else {
    supplier.documentIds = Array.from(new Set([...(supplier.documentIds || []), document.id]));
    supplier.supplierName = supplierName || supplier.supplierName;
    supplier.vat = vat || supplier.vat;
    supplier.iban = iban || supplier.iban;
    supplier.address = address || supplier.address;
    if (document.validation?.status === 'warning') supplier.status = 'pending';
  }

  return supplier.id;
}

export async function getAllDocuments() {
  const db = await readDb();
  return db.documents;
}

export async function getDocumentById(documentId) {
  const db = await readDb();
  return db.documents.find((item) => item.id === documentId);
}

export async function getAllSuppliers() {
  const db = await readDb();
  return db.suppliers;
}

export async function getSupplierById(id) {
  const db = await readDb();
  return db.suppliers.find((item) => item.id === id);
}

export async function getComplianceBySupplierId(id) {
  const db = await readDb();
  const supplier = db.suppliers.find((item) => item.id === id);
  if (!supplier) return null;

  const documents = db.documents.filter((doc) => supplier.documentIds?.includes(doc.id));
  const documentsReceived = documents.map((doc) => doc.documentType || 'pending');
  const anomalies = documents.flatMap((doc) => doc.validation?.anomalies || []);

  return {
    supplierId: supplier.id,
    supplierName: supplier.supplierName,
    documentsReceived,
    checks: [
      {
        name: 'Présence des documents',
        status: documents.length >= 2 ? 'passed' : 'warning'
      },
      {
        name: 'Cohérence SIRET',
        status: anomalies.some((item) => item.toLowerCase().includes('siret')) ? 'failed' : 'passed'
      },
      {
        name: 'Validité des attestations',
        status: anomalies.some((item) => item.toLowerCase().includes('expiration')) ? 'failed' : 'passed'
      }
    ],
    anomalies,
    globalStatus: anomalies.length ? 'warning' : 'validated'
  };
}
