import { Router } from 'express';
import { getDocumentDetails, getDocumentStatus, listDocuments } from '../controllers/documentController.js';

const router = Router();

router.get('/', listDocuments);
router.get('/:id', getDocumentDetails);
router.get('/:id/status', getDocumentStatus);

export default router;
