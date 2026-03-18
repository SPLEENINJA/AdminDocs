import { getAllSuppliers } from '../services/documentService.js';

export async function listSuppliers(_req, res) {
  const suppliers = await getAllSuppliers();
  res.json(suppliers);
}
