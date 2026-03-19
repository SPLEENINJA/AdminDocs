import { getAllDocuments, getDocumentById } from '../services/documentService.js';

export async function listDocuments(_req, res) {
  const user_id = _req.user.id; // Assuming user ID is available in the request object
  const documents = await getAllDocuments(user_id);
  res.json(documents);
}

export async function getDocumentDetails(req, res) {
  const document = await getDocumentById(req.params.id);
  if (!document) {
    return res.status(404).json({ success: false, message: 'Document introuvable' });
  }
  res.json(document);
}

export async function getDocumentStatus(req, res) {
  const document = await getDocumentById(req.params.id);
  if (!document) {
    return res.status(404).json({ success: false, message: 'Document introuvable' });
  }

  res.json({
    id: document.id,
    status: document.status,
    step: document.step,
    validationStatus: document.validation?.status || null
  });
}


