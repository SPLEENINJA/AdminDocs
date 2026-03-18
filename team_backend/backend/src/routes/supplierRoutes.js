import { Router } from 'express';
import { listSuppliers } from '../controllers/supplierController.js';

const router = Router();

router.get('/', listSuppliers);

export default router;
