import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import { fetchCrmSupplier, fetchSuppliers } from '../api/suppliers';

export default function CRMPage() {
  const [searchParams] = useSearchParams();
  const selectedFromUrl = searchParams.get('selected');

  const [suppliers, setSuppliers] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [supplier, setSupplier] = useState(null);

  useEffect(() => {
    fetchSuppliers().then((items) => {
      setSuppliers(items);
      setSelectedId(selectedFromUrl || items[0]?.siret || '');
    }).catch(console.error);
  }, [selectedFromUrl]);

  useEffect(() => {
    if (!selectedId) return;
    fetchCrmSupplier(selectedId).then(setSupplier).catch(console.error);
  }, [selectedId]);

  const selectedLabel = useMemo(
    () => suppliers.find((item) => item.siret === selectedId)?.supplierName,
    [suppliers, selectedId]
  );

  return (
    <div className="grid gap-6 xl:grid-cols-[340px,1fr]">
      <Card title="Fournisseurs détectés">
        <div className="space-y-3">
          {suppliers.map((item) => (
            <button
              key={item.siret}
              onClick={() => setSelectedId(item.siret)}
              className={`w-full rounded-2xl border p-4 text-left transition ${
                selectedId === item.siret
                  ? 'border-brand-500 bg-brand-500/10'
                  : 'border-slate-800 bg-slate-950/60 hover:border-slate-700'
              }`}
            >
              <p className="font-medium text-white">{item.supplierName}</p>
              <p className="mt-1 text-sm text-slate-400">{item.siret}</p>
              <div className="mt-3">
                <Badge status={item.status}>{item.status}</Badge>
              </div>
            </button>
          ))}
          {!suppliers.length && (
            <p className="text-slate-400">Aucun fournisseur créé pour l'instant.</p>
          )}
        </div>
      </Card>

      <Card title={`CRM fournisseur${selectedLabel ? ` • ${selectedLabel}` : ''}`}>
        {supplier ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Raison sociale" value={supplier.supplierName} />
            <Field label="SIRET" value={supplier.siret} />
            <Field label="TVA" value={supplier.vat} />
            <Field label="IBAN" value={supplier.iban} />
            <Field label="Adresse" value={supplier.address} />
            <Field label="Statut fournisseur" value={supplier.status} />
          </div>
        ) : (
          <p className="text-slate-400">Sélectionne un fournisseur pour voir le formulaire auto-rempli.</p>
        )}
      </Card>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 font-medium text-white">{value || '-'}</p>
    </div>
  );
}