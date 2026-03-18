import { Router } from 'express';
import { getCrmSupplier } from '../controllers/crmController.js';

const router = Router();

router.get('/suppliers/:supplierId', getCrmSupplier);

export default router;
