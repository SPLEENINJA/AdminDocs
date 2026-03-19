import express from 'express';
import { askDocuments } from '../services/chatService.js';

const router = express.Router();

/**
 * POST /api/chat
 * Body: { question: string, nResults?: number }
 * Response: { answer, sources, documents_count }
 */
router.post('/', async (req, res) => {
  const { question, nResults = 5 } = req.body;
  if (!question?.trim()) {
    return res.status(400).json({ message: 'La question ne peut pas être vide.' });
  }
  try {
    const result = await askDocuments(question.trim(), nResults);
    return res.status(200).json(result);
  } catch (error) {
    console.error('Erreur chat :', error.message);
    const status  = error.response?.status  || 500;
    const message = error.response?.data?.detail || 'Erreur lors de la génération de la réponse.';
    return res.status(status).json({ message });
  }
});

export default router;
