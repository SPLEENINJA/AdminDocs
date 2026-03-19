import api from './client';

/**
 * Envoie une question et reçoit une réponse Gemini
 * basée sur les documents indexés dans ChromaDB.
 * @param {string} question
 * @param {number} nResults
 */
export const askDocuments = (question, nResults = 5) =>
  api.post('/chat', { question, nResults }).then((r) => r.data);
