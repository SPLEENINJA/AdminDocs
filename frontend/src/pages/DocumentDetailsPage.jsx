import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import { fetchDocumentById } from '../api/documents';

export default function DocumentDetailsPage() {
  const { id } = useParams();
  const [document, setDocument] = useState(null);

  useEffect(() => {
    fetchDocumentById(id).then(setDocument).catch(console.error);
  }, [id]);

  if (!document) return <p className="text-slate-400">Chargement...</p>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm uppercase tracking-[0.35em] text-brand-500">Détail document</p>
          <h1 className="mt-2 text-3xl font-bold text-white">{document.filename}</h1>
        </div>
        <div className="flex gap-3">
          <Badge status={document.documentType}>{document.documentType || 'pending'}</Badge>
          <Badge status={document.validation?.status || document.status}>{document.validation?.status || document.status}</Badge>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Card title="Prévisualisation / OCR">
          <div className="space-y-4">
            <a
              className="inline-flex rounded-2xl border border-slate-700 px-4 py-2 text-sm text-slate-200"
              href={`http://localhost:4000${document.previewUrl}`}
              target="_blank"
              rel="noreferrer"
            >
              Ouvrir le fichier uploadé
            </a>
            <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
              <p className="mb-2 text-sm font-medium text-white">Texte OCR</p>
              <p className="text-sm leading-7 text-slate-300">{document.ocrText || 'OCR en attente...'}</p>
            </div>
          </div>
        </Card>

        <Card title="Champs extraits">
          <div className="space-y-3">
            {Object.entries(document.extractedData || {}).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
                <span className="text-slate-400">{key}</span>
                <span className="font-medium text-white">{String(value)}</span>
              </div>
            ))}
            {!document.extractedData && <p className="text-slate-400">Aucune donnée extraite pour l’instant.</p>}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Validation et anomalies">
          <div className="space-y-3">
            {document.validation?.checks?.map((check) => (
              <div key={check.name} className="flex items-center justify-between rounded-2xl border border-slate-800 px-4 py-3">
                <span className="text-slate-300">{check.name}</span>
                <Badge status={check.status}>{check.status}</Badge>
              </div>
            ))}

            {document.validation?.anomalies?.length ? (
              <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-200">
                <p className="font-medium">Anomalies détectées</p>
                <ul className="mt-2 list-disc pl-5 text-sm">
                  {document.validation.anomalies.map((anomaly) => (
                    <li key={anomaly}>{anomaly}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-emerald-200">
                Aucune anomalie détectée.
              </div>
            )}
          </div>
        </Card>

        <Card title="Actions métier">
          <div className="space-y-4 text-sm text-slate-300">
            <p>Cette partie montre comment ta couche API peut injecter les données extraites dans deux outils simulés.</p>
            {document.supplierId ? (
              <div className="flex flex-wrap gap-3">
                <Link className="rounded-2xl bg-brand-500 px-5 py-3 font-medium text-white" to={`/crm?selected=${document.supplierId}`}>
                  Ouvrir dans le CRM
                </Link>
                <Link className="rounded-2xl border border-slate-700 px-5 py-3 font-medium text-slate-200" to={document.supplierId ? `/user?supplierId=${document.supplierId}` : '/user'}>
                  Ouvrir dans l’espace utilisateur
                </Link>
              </div>
            ) : (
              <p className="text-slate-400">Le fournisseur sera créé automatiquement après la fin du pipeline.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
