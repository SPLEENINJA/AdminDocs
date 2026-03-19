import { useEffect, useState } from 'react';
import { Eye } from 'lucide-react';
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import { fetchDocuments } from '../api/documents';
import { formatDate } from '../utils/format';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);

  useEffect(() => {
    const token = localStorage.getItem('token');
    fetchDocuments(token).then(setDocuments).catch(console.error);
  }, []);

  return (
    <Card title="Documents traités par la plateforme">
      <div className="overflow-hidden rounded-3xl border border-slate-800">
        <div className="grid grid-cols-6 gap-4 border-b border-slate-800 bg-slate-900 px-4 py-3 text-sm font-medium text-slate-400">
          <span className="col-span-2">Fichier</span>
          <span>Type</span>
          <span>Upload</span>
          <span>Statut</span>
          <span>Action</span>
        </div>

        <div className="divide-y divide-slate-800">
          {documents.map((doc) => (
            <div key={String(doc.id)} className="grid grid-cols-6 gap-4 px-4 py-4 text-sm">
              <div className="col-span-2">
                <p className="font-medium text-white">{doc.filename}</p>
              </div>
              <p className="text-slate-300">{doc.mimetype || '-'}</p>
              <p className="text-slate-300">{formatDate(doc.created_at)}</p>
              {/* <Badge status={doc.validation?.status || doc.status}>{doc.validation?.status || doc.status}</Badge> */}
              <div>
                <Link className="inline-flex items-center gap-2 text-brand-500" to={`/documents/${String(doc.id)}`}>
                  <Eye size={16} /> Détails
                </Link>
              </div>
            </div>
          ))}

          {!documents.length && <div className="px-4 py-10 text-center text-slate-400">Aucun document disponible.</div>}
        </div>
      </div>
    </Card>
  );
}
