import { createUploadedDocuments } from '../services/documentService.js';

export async function uploadDocuments(req, res) {
  if (!req.files?.length) {
    return res.status(400).json({ success: false, message: 'Aucun fichier reçu' });
  }

  const documents = await createUploadedDocuments(req.files);

  res.status(201).json({
    success: true,
    message: 'Documents uploadés avec succès',
    documents
  });
}
