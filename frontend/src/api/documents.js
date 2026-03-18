import api from './client';

export async function uploadDocuments(files) {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  const { data } = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return data;
}

export async function fetchDocuments() {
  const { data } = await api.get('/documents');
  return data;
}

export async function fetchDocumentById(id) {
  const { data } = await api.get(`/documents/${id}`);
  return data;
}

export async function fetchDocumentStatus(id) {
  const { data } = await api.get(`/documents/${id}/status`);
  return data;
}
