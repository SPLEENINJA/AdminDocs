import path from "path";
import { randomUUID } from "crypto";
import { processDocument } from "./mockProcessingService.js";
import { uploadToRaw, uploadJsonToClean } from "./minioService.js";
import pool from "../config/database.js";

// File d'attente globale : les documents uploadés ensemble sont traités 1 par 1
let pipelineQueue = Promise.resolve();

function enqueuePipeline(documentId) {
  pipelineQueue = pipelineQueue
    .then(() => runPipeline(documentId))
    .catch((err) => console.error(`[pipeline] Erreur doc ${documentId}:`, err));
}

export async function createUploadedDocuments(files, userId) {
  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    const createdDocs = [];

    for (const file of files) {
      const result = await client.query(
        `INSERT INTO documents (user_id, mimetype, size, filename, path, metadata)
         VALUES ($1,$2,$3,$4,$5, $6)
         RETURNING *`,
        [
          userId,
          file.mimetype,
          file.size,
          file.originalname,
          `/uploads/${file.filename}`,
          JSON.stringify({
            storedFilename: file.filename,
            status: 'uploaded',
            step: 'raw_storage'
          })
        ]
      );

      const doc = result.rows[0];
      createdDocs.push(doc);

      enqueuePipeline(doc.id);
    }

    await client.query('COMMIT');
    return createdDocs;

  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

export async function runPipeline(documentId) {
  const client = await pool.connect();

  try {
    console.log(`[pipeline] Début traitement : ${documentId}`);

    const { rows } = await client.query(
      `SELECT * FROM documents WHERE id = $1`,
      [documentId]
    );

    const document = rows[0];
    if (!document) return;

    const metadata = document.metadata || {};
    const uploadDir = path.resolve('src/uploads');
    const filePath = path.join(uploadDir, metadata.storedFilename);

    await uploadToRaw(metadata.storedFilename, filePath, document.mimetype);

    // update status -> processing
    await client.query(
      `UPDATE documents
       SET metadata = $2
       WHERE id = $1`,
      [
        documentId,
        {
          ...metadata,
          status: 'processing',
          step: 'ocr'
        }
      ]
    );

    const result = await processDocument({
      ...document,
      ...metadata
    });

    // update final
    await client.query(
      `UPDATE documents
       SET 
         ocr_text = $2,
         metadata = $3
       WHERE id = $1`,
      [
        documentId,
        result.ocrText,
        {
          ...metadata,
          status: 'validated',
          step: 'completed',
          documentType: result.documentType,
          extractedData: result.extractedData,
          validation: result.validation,
          cleanPath: `/clean/${documentId}.json`,
          curatedPath: `/curated/${documentId}.json`
        }
      ]
    );

    await uploadJsonToClean(documentId, {
      documentId,
      filename: document.filename,
      ...result
    });

    console.log(`[pipeline] Terminé : ${documentId}`);

  } finally {
    client.release();
  }
}



export async function getAllDocuments(userId) {
  try {
    const client = await pool.connect();

    const data = await client.query(
      `SELECT * FROM documents WHERE user_id = $1 ORDER BY created_at DESC `,
      [userId]
    );

    return data.rows;

  } catch (error) {
    console.error("Error fetching documents:", error);
  }
  return [];
}

export async function getDocumentById(documentId) {
  const client = await pool.connect();

  try {
    const { rows } = await client.query(
      `SELECT * FROM documents WHERE id = $1`,
      [documentId]
    );

    return rows[0] || null;

  } finally {
    client.release();
  }
}

export async function getAllSuppliers() {
  const client = await pool.connect();

  try {
    const { rows } = await client.query(
      `SELECT metadata->'extractedData' AS data
       FROM documents
       WHERE metadata->'extractedData' IS NOT NULL`
    );

    const suppliersMap = new Map();

    for (const row of rows) {
      const data = row.data;
      if (!data?.siret) continue;

      if (!suppliersMap.has(data.siret)) {
        suppliersMap.set(data.siret, {
          supplierName: data.supplierName,
          siret: data.siret,
          vat: data.vat,
          iban: data.iban,
          address: data.address
        });
      }
    }

    return Array.from(suppliersMap.values());

  } finally {
    client.release();
  }
}

export async function getSupplierById(siret) {
  const client = await pool.connect();

  try {
    const { rows } = await client.query(
      `SELECT metadata->'extractedData' AS data
       FROM documents
       WHERE metadata->'extractedData'->>'siret' = $1`,
      [siret]
    );

    if (!rows.length) return null;

    const data = rows[0].data;

    return {
      supplierName: data.supplierName,
      siret: data.siret,
      vat: data.vat,
      iban: data.iban,
      address: data.address
    };

  } finally {
    client.release();
  }
}

export async function getComplianceBySupplierId(siret) {
  const client = await pool.connect();

  try {
    const { rows } = await client.query(
      `SELECT *
       FROM documents
       WHERE metadata->'extractedData'->>'siret' = $1`,
      [siret]
    );

    if (!rows.length) return null;

    const documents = rows.map(doc => {
      const metadata = doc.metadata || {};
      return {
        documentType: metadata.documentType,
        validation: metadata.validation
      };
    });

    const documentsReceived = documents.map(
      (doc) => doc.documentType || 'pending'
    );

    const anomalies = documents.flatMap(
      (doc) => doc.validation?.anomalies || []
    );

    return {
      supplierId: siret,
      documentsReceived,
      checks: [
        {
          name: 'Présence des documents',
          status: documents.length >= 2 ? 'passed' : 'warning'
        },
        {
          name: 'Cohérence SIRET',
          status: anomalies.some(a => a.toLowerCase().includes('siret'))
            ? 'failed'
            : 'passed'
        },
        {
          name: 'Validité des attestations',
          status: anomalies.some(a => a.toLowerCase().includes('expiration'))
            ? 'failed'
            : 'passed'
        }
      ],
      anomalies,
      globalStatus: anomalies.length ? 'warning' : 'validated'
    };

  } finally {
    client.release();
  }
}

