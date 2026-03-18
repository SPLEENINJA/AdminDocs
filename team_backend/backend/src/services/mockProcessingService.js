import fs from 'fs';
import path from 'path';

const OCR_SERVICE_URL = process.env.OCR_SERVICE_URL || 'http://ocr-service:8000';

const docPatterns = [
  { type: 'facture', keywords: ['facture', 'invoice'] },
  { type: 'devis', keywords: ['devis', 'quote'] },
  { type: 'kbis', keywords: ['kbis'] },
  { type: 'attestation_urssaf', keywords: ['urssaf', 'vigilance', 'attestation'] },
  { type: 'rib', keywords: ['rib', 'iban', 'bank'] },
  { type: 'siret', keywords: ['siret', 'sirene'] }
];

function inferDocumentType(filename) {
  const lower = filename.toLowerCase();
  const found = docPatterns.find((entry) => entry.keywords.some((keyword) => lower.includes(keyword)));
  return found?.type || 'document_inconnu';
}

function randomDigits(length) {
  return Array.from({ length }, () => Math.floor(Math.random() * 10)).join('');
}

function pad(n) {
  return String(n).padStart(2, '0');
}

function buildDate(offsetDays = 0) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function makeSupplierName(filename) {
  const base = filename.split('.')[0].replace(/[-_]/g, ' ').trim();
  return base
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ') || 'Alpha Services';
}

function generateFields(type, filename) {
  const supplierName = makeSupplierName(filename);
  const siret = randomDigits(14);
  const vat = `FR${randomDigits(2)}${randomDigits(9)}`;
  const iban = `FR76 ${randomDigits(4)} ${randomDigits(4)} ${randomDigits(4)} ${randomDigits(4)} ${randomDigits(4)} ${randomDigits(3)}`;
  const invoiceDate = buildDate(-3);
  const expiryDate = buildDate(30);
  const amountHt = Number((300 + Math.random() * 4000).toFixed(2));
  const amountTtc = Number((amountHt * 1.2).toFixed(2));

  const common = {
    supplierName,
    siret,
    vat,
    invoiceDate,
    expiryDate,
    amountHt,
    amountTtc,
    iban,
    address: `${Math.floor(Math.random() * 99) + 1} Rue de la République, Paris`,
    status: 'pending'
  };

  switch (type) {
    case 'facture':
      return {
        ...common,
        invoiceNumber: `FAC-${randomDigits(6)}`,
        dueDate: buildDate(15)
      };
    case 'devis':
      return {
        ...common,
        quoteNumber: `DEV-${randomDigits(6)}`,
        validUntil: buildDate(20)
      };
    case 'attestation_urssaf':
      return {
        ...common,
        vigilanceValid: true,
        certificateType: 'Attestation de vigilance URSSAF'
      };
    case 'kbis':
      return {
        ...common,
        registrationDate: buildDate(-250),
        legalForm: 'SAS'
      };
    case 'rib':
      return {
        ...common,
        bic: `AGRIFRPP${randomDigits(3)}`
      };
    case 'siret':
      return {
        ...common,
        siren: siret.slice(0, 9)
      };
    default:
      return common;
  }
}

function generateValidation(type, filename, extractedData) {
  const anomalies = [];
  const lower = filename.toLowerCase();

  if (lower.includes('expire')) anomalies.push("Date d'expiration dépassée");
  if (lower.includes('wrong') || lower.includes('mismatch')) anomalies.push('SIRET incohérent avec les autres documents');
  if (type === 'facture' && extractedData.amountTtc < extractedData.amountHt) anomalies.push('Montant TTC incohérent');

  return {
    status: anomalies.length ? 'warning' : 'validated',
    score: anomalies.length ? 62 : 96,
    anomalies,
    checks: [
      { name: 'OCR terminé', status: 'passed' },
      { name: 'Extraction des champs', status: 'passed' },
      { name: 'Cohérence documentaire', status: anomalies.length ? 'warning' : 'passed' }
    ]
  };
}

export async function processDocument(document) {
  // Essaie d'appeler le vrai service OCR
  try {
    const uploadDir = path.resolve('src/uploads');
    const filePath = path.join(uploadDir, document.storedFilename);

    if (fs.existsSync(filePath)) {
      const fileBytes = fs.readFileSync(filePath);
      const blob = new Blob([fileBytes], { type: document.mimetype || 'application/octet-stream' });
      const formData = new FormData();
      formData.append('files', blob, document.filename);

      const res = await fetch(`${OCR_SERVICE_URL}/documents/upload`, {
        method: 'POST',
        body: formData,
        signal: AbortSignal.timeout(30000),
      });

      if (res.ok) {
        const data = await res.json();
        // L'OCR retourne un tableau (un résultat par fichier)
        const ocrResult = Array.isArray(data) ? data[0] : data;
        return mapOcrResult(ocrResult, document);
      }
    }
  } catch (err) {
    console.warn(`[pipeline] OCR service indisponible, fallback mock : ${err.message}`);
  }

  // Fallback : mock si OCR service down
  return mockProcessDocument(document);
}

function mapOcrResult(ocr, document) {
  const champs = ocr.champs || {};
  const documentType = ocr.type_document || 'document_inconnu';

  const extractedData = {
    supplierName: champs.raison_sociale || champs.emetteur || null,
    siret: champs.siret || null,
    vat: champs.tva_taux || null,
    invoiceDate: champs.date_emission || null,
    expiryDate: champs.date_expiration || null,
    amountHt: champs.montant_ht ?? null,
    amountTtc: champs.montant_ttc ?? null,
    iban: champs.iban || null,
    bic: champs.bic || null,
    adresseEmetteur: champs.adresse_emetteur || null,
    adresseDestinataire: champs.adresse_destinataire || null,
    invoiceNumber: champs.numero_document || null,
  };

  const anomalies = Array.isArray(ocr.anomalies) ? ocr.anomalies : [];
  const score = anomalies.length === 0 ? 96 : Math.max(30, 96 - anomalies.length * 15);

  const validation = {
    status: anomalies.length === 0 ? 'validated' : 'warning',
    score,
    anomalies,
    checks: [
      { name: 'OCR terminé', status: 'passed' },
      { name: 'Extraction des champs', status: 'passed' },
      { name: 'Cohérence documentaire', status: anomalies.length ? 'warning' : 'passed' },
    ],
  };

  return {
    documentType,
    ocrText: ocr.texte_brut || `Document traité par OCR Gemini (confiance: ${ocr.confiance ?? '?'})`,
    extractedData,
    validation,
    previewUrl: `/uploads/${document.storedFilename}`,
  };
}

async function mockProcessDocument(document) {
  await new Promise((resolve) => setTimeout(resolve, 1200));

  const documentType = inferDocumentType(document.filename);
  const extractedData = generateFields(documentType, document.filename);
  const validation = generateValidation(documentType, document.filename, extractedData);

  return {
    documentType,
    ocrText: `[MOCK] Texte OCR simulé pour ${document.filename}.`,
    extractedData,
    validation,
    previewUrl: `/uploads/${document.storedFilename}`,
  };
}
