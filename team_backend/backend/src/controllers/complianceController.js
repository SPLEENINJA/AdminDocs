import { getComplianceBySupplierId } from '../services/documentService.js';

export async function getComplianceData(req, res) {
  const result = await getComplianceBySupplierId(req.params.supplierId);
  if (!result) {
    return res.status(404).json({ success: false, message: 'Analyse conformité introuvable' });
  }
  res.json(result);
}
