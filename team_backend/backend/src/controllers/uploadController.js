import { createUploadedDocuments } from '../services/documentService.js';

export async function uploadDocuments(req, res) {
  const user_id = req.user.id; // Assuming user ID is available in the request object
  console.log('Received files for upload:', req.files);
  if (!req.files?.length) {
    return res.status(400).json({ success: false, message: 'Aucun fichier reçu' });
  }

  const documents = await createUploadedDocuments(req.files, user_id);

  res.status(201).json({
    success: true,
    message: 'Documents uploadés avec succès',
    documents
  });
}
