import { Router } from 'express';
import { upload } from '../middleware/uploadMiddleware.js';
import { uploadDocuments } from '../controllers/uploadController.js';
import { authenticateToken } from '../middleware/auth.js';

const router = Router();

router.post('/', authenticateToken, upload.array('files', 10),uploadDocuments);

export default router;
