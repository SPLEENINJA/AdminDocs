import { Router } from 'express';
import { getComplianceData } from '../controllers/complianceController.js';

const router = Router();

router.get('/:supplierId', getComplianceData);

export default router;
