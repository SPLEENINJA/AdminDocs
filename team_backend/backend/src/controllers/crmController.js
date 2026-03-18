import { getSupplierById } from '../services/documentService.js';

export async function getCrmSupplier(req, res) {
  const supplier = await getSupplierById(req.params.supplierId);
  if (!supplier) {
    return res.status(404).json({ success: false, message: 'Fournisseur introuvable' });
  }
  res.json(supplier);
}
