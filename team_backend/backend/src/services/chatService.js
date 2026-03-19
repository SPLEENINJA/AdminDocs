import axios from 'axios';

const OCR_SERVICE_URL = process.env.OCR_SERVICE_URL || 'http://localhost:8000';

/**
 * Envoie une question au service OCR Python (ChromaDB + Gemini).
 * @param {string} question
 * @param {number} nResults
 */
export const askDocuments = async (question, nResults = 5) => {
  const response = await axios.post(
    `${OCR_SERVICE_URL}/documents/chat`,
    { question, n_results: nResults },
    { headers: { 'Content-Type': 'application/json' }, timeout: 60000 }
  );
  return response.data;
};
