import { useState } from 'react';
import { UploadCloud } from 'lucide-react';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import { uploadDocuments } from '../api/documents';

export default function UploadPage() {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function onSelectFiles(event) {
    setSelectedFiles(Array.from(event.target.files || []));
  }

  async function handleUpload() {
    if (!selectedFiles.length) return;
    setLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('token');
      console.log('Token for upload:', token);
      const response = await uploadDocuments(selectedFiles, token);
      setUploadedDocs(response.documents || []);
      setSelectedFiles([]);
    } catch (err) {
      setError(err.response?.data?.message || 'Erreur pendant l’upload');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card title="Upload multi-documents">
        <div className="rounded-[2rem] border border-dashed border-brand-500/40 bg-brand-500/5 p-8 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-500">
            <UploadCloud size={28} />
          </div>
          <h2 className="mt-4 text-2xl font-semibold text-white">Dépose tes PDF et images</h2>
          <p className="mx-auto mt-2 max-w-2xl text-slate-400">
            Formats acceptés : PDF, PNG, JPG, WEBP. Le backend stocke les fichiers puis déclenche automatiquement le pipeline de traitement.
          </p>

          <input
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.webp"
            onChange={onSelectFiles}
            className="mt-6 block w-full rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-300 file:mr-4 file:rounded-xl file:border-0 file:bg-brand-500 file:px-4 file:py-2 file:text-white"
          />

          <button
            onClick={handleUpload}
            disabled={loading || !selectedFiles.length}
            className="mt-6 rounded-2xl bg-brand-500 px-6 py-3 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Upload en cours...' : 'Uploader et lancer le pipeline'}
          </button>

          {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}
        </div>
      </Card>

      <Card title="Fichiers sélectionnés">
        <div className="space-y-3">
          {selectedFiles.map((file) => (
            <div key={file.name} className="flex items-center justify-between rounded-2xl border border-slate-800 p-4">
              <div>
                <p className="font-medium text-white">{file.name}</p>
                <p className="text-sm text-slate-400">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
              <Badge status="pending">prêt</Badge>
            </div>
          ))}
          {!selectedFiles.length && <p className="text-slate-400">Aucun fichier sélectionné.</p>}
        </div>
      </Card>

      <Card title="Réponse API après upload">
        <div className="space-y-3">
          {uploadedDocs.map((doc) => (
            <div key={doc.id} className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
              <div>
                <p className="font-medium text-white">{doc.filename}</p>
                <p className="text-sm text-slate-400">ID : {doc.id}</p>
              </div>
              <Badge status={doc.status}>{doc.status}</Badge>
            </div>
          ))}
          {!uploadedDocs.length && <p className="text-slate-400">L’API retournera ici les documents créés.</p>}
        </div>
      </Card>
    </div>
  );
}
