import { Router } from 'express';
import { upload } from '../middleware/uploadMiddleware.js';
import { uploadDocuments } from '../controllers/uploadController.js';

const router = Router();

router.post('/', upload.array('files', 10), uploadDocuments);

export default router;
