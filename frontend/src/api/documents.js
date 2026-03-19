import api from "./client";

export async function uploadDocuments(files, token) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const { data } = await api.post("/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
      Authorization: `Bearer ${token}`,
    },
  });
  return data;
}

export async function fetchDocuments(token) {
  try {
    const { data } = await api.get("/documents", {
      headers: { Authorization: `Bearer ${token}` },
    });
    console.log("Documents fetched:", data);
    return data;
  } catch (error) {
    console.error("Error fetching documents:", error);
    return [];
  }
}

export async function fetchDocumentById(id, token) {
  const { data } = await api.get(`/documents/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  console.log("Document details fetched:", data);
  return data;
}

export async function fetchDocumentStatus(id, token) {
  const { data } = await api.get(`/documents/${id}/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return data;
}
