import { useEffect, useState } from 'react';
import { ArrowRight, CheckCircle2, Clock3, FileSearch, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import { fetchDocuments } from '../api/documents';

export default function DashboardPage() {

  const [documents, setDocuments] = useState([]);

  useEffect(() => {
    fetchDocuments().then(setDocuments).catch(console.error);
  }, []);

  const total = documents.length;
  const processed = documents.filter((doc) => doc.status === 'validated').length;
  const warnings = documents.filter((doc) => doc.validation?.status === 'warning').length;
  const processing = documents.filter((doc) => doc.status === 'processing').length;

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900 to-brand-600/20 p-8">
        <p className="text-sm uppercase tracking-[0.35em] text-brand-500">Plateforme documentaire</p>
        <h2 className="mt-4 max-w-3xl text-4xl font-bold leading-tight text-white">
          Upload, classification, extraction et auto-remplissage des outils métier.
        </h2>
        <p className="mt-4 max-w-2xl text-slate-300">
          Cette interface démontre la partie Front & API du hackathon : dépôt multi-documents, suivi du pipeline et injection automatique dans le CRM et l’outil de conformité.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link className="rounded-2xl bg-brand-500 px-5 py-3 font-medium text-white" to="/upload">
            Commencer un upload
          </Link>
          <Link className="rounded-2xl border border-slate-700 px-5 py-3 font-medium text-slate-200" to="/documents">
            Voir les documents
          </Link>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={FileSearch} label="Documents" value={total} />
        <StatCard icon={CheckCircle2} label="Traités" value={processed} />
        <StatCard icon={ShieldAlert} label="Warnings" value={warnings} />
        <StatCard icon={Clock3} label="En cours" value={processing} />
      </section>

      <Card title="Derniers documents">
        <div className="space-y-3">
          {documents.slice(0, 5).map((doc) => (
            <Link
              key={doc.id}
              to={`/documents/${doc.id}`}
              className="flex flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-950/70 p-4 transition hover:border-brand-500/40 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <p className="font-medium text-white">{doc.filename}</p>
                <p className="text-sm text-slate-400">{doc.documentType || 'Type en attente'} • {doc.step}</p>
              </div>
              <div className="flex items-center gap-3">
                <Badge status={doc.validation?.status || doc.status}>{doc.validation?.status || doc.status}</Badge>
                <ArrowRight className="text-slate-500" size={18} />
              </div>
            </Link>
          ))}

          {!documents.length && <p className="text-slate-400">Aucun document pour le moment. Lance un upload pour commencer la démo.</p>}
        </div>
      </Card>
    </div>
  );
}

function StatCard({ icon: Icon, label, value }) {
  return (
    <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">{label}</p>
        <Icon size={18} className="text-brand-500" />
      </div>
      <p className="mt-4 text-3xl font-bold text-white">{value}</p>
    </div>
  );
}
