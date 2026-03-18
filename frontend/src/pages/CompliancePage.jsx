import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import { fetchCompliance, fetchSuppliers } from '../api/suppliers';

export default function CompliancePage() {
  const [searchParams] = useSearchParams();
  const selectedFromUrl = searchParams.get('selected');
  const [suppliers, setSuppliers] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [compliance, setCompliance] = useState(null);

  useEffect(() => {
    fetchSuppliers().then((items) => {
      setSuppliers(items);
      setSelectedId(selectedFromUrl || items[0]?.id || '');
    }).catch(console.error);
  }, [selectedFromUrl]);

  useEffect(() => {
    if (!selectedId) return;
    fetchCompliance(selectedId).then(setCompliance).catch(console.error);
  }, [selectedId]);

  return (
    <div className="grid gap-6 xl:grid-cols-[340px,1fr]">
      <Card title="Dossiers fournisseurs">
        <div className="space-y-3">
          {suppliers.map((item) => (
            <button
              key={item.id}
              onClick={() => setSelectedId(item.id)}
              className={`w-full rounded-2xl border p-4 text-left transition ${selectedId === item.id ? 'border-brand-500 bg-brand-500/10' : 'border-slate-800 bg-slate-950/60'}`}
            >
              <p className="font-medium text-white">{item.supplierName}</p>
              <p className="mt-1 text-sm text-slate-400">{item.siret}</p>
            </button>
          ))}
          {!suppliers.length && <p className="text-slate-400">Aucun dossier disponible.</p>}
        </div>
      </Card>

      <div className="space-y-6">
        <Card title="Décision conformité">
          {compliance ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <div>
                  <p className="text-sm text-slate-400">Fournisseur</p>
                  <p className="text-lg font-semibold text-white">{compliance.supplierName}</p>
                </div>
                <Badge status={compliance.globalStatus}>{compliance.globalStatus}</Badge>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p className="text-sm text-slate-400">Documents reçus</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {compliance.documentsReceived.map((item) => (
                    <Badge key={item} status="validated">{item}</Badge>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-slate-400">Sélectionne un fournisseur pour voir son dossier conformité.</p>
          )}
        </Card>

        <Card title="Contrôles de cohérence">
          <div className="space-y-3">
            {compliance?.checks?.map((check) => (
              <div key={check.name} className="flex items-center justify-between rounded-2xl border border-slate-800 px-4 py-3">
                <span className="text-slate-300">{check.name}</span>
                <Badge status={check.status}>{check.status}</Badge>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Anomalies détectées">
          {compliance?.anomalies?.length ? (
            <ul className="space-y-3 text-slate-300">
              {compliance.anomalies.map((item) => (
                <li key={item} className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-amber-200">
                  {item}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-slate-400">Aucune anomalie détectée.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
