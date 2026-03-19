import { Router } from 'express';
import { getDocumentDetails, getDocumentStatus, listDocuments } from '../controllers/documentController.js';
import { authenticateToken } from '../middleware/auth.js';

const router = Router();

router.get('/', authenticateToken,(req, res)=>  listDocuments(req, res));
router.get('/:id', authenticateToken, getDocumentDetails);
router.get('/:id/status', authenticateToken, getDocumentStatus);

export default router;
