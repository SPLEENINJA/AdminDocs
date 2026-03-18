import api from './client';

export async function fetchSuppliers() {
  const { data } = await api.get('/suppliers');
  return data;
}

export async function fetchCrmSupplier(id) {
  const { data } = await api.get(`/crm/suppliers/${id}`);
  return data;
}

export async function fetchCompliance(id) {
  const { data } = await api.get(`/compliance/${id}`);
  return data;
}
