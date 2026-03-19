import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  FileText,
  TriangleAlert,
  CheckCircle2,
  FolderOpen,
  ArrowRight
} from 'lucide-react';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import { fetchCompliance, fetchSuppliers } from '../api/suppliers';
import { fetchDocuments } from '../api/documents';

function normalizeStatus(status) {
  const value = String(status || '').toLowerCase();

  if (value === 'passed' || value === 'validated' || value === 'ok') return 'ok';
  if (value === 'failed' || value === 'échec' || value === 'echec') return 'failed';
  if (value === 'warning') return 'warning';
  return 'pending';
}

function getDocStatus(doc) {
  return doc.validation?.status || doc.status || 'pending';
}

function statusPillClass(status) {
  if (status === 'ok') {
    return 'border border-emerald-500/20 bg-emerald-500/15 text-emerald-300';
  }
  if (status === 'failed') {
    return 'border border-rose-500/20 bg-rose-500/15 text-rose-300';
  }
  if (status === 'warning') {
    return 'border border-amber-500/20 bg-amber-500/15 text-amber-300';
  }
  return 'border border-slate-700 bg-slate-800 text-slate-300';
}

function getGlobalChecklistStatus(checks = []) {
  if (!checks.length) return 'pending';

  const normalized = checks.map((check) => normalizeStatus(check.status));

  if (normalized.includes('failed')) return 'partial';
  if (normalized.includes('warning')) return 'partial';
  if (normalized.every((item) => item === 'ok')) return 'ok';

  return 'pending';
}

function globalChecklistClass(status) {
  if (status === 'ok') {
    return 'border border-emerald-500/20 bg-emerald-500/15 text-emerald-300';
  }
  if (status === 'partial') {
    return 'border border-amber-500/20 bg-amber-500/15 text-amber-300';
  }
  return 'border border-slate-700 bg-slate-800 text-slate-300';
}

function displayCheckName(name) {
  const mapping = {
    'Présence des documents': 'KBIS présent',
    'Cohérence SIRET': 'SIRET cohérent sur les pièces',
    'Validité des attestations': 'Attestation URSSAF présente',
    'RIB présent': 'RIB présent',
    'Adresse cohérente': 'Adresse cohérente',
    'Document principal lisible': 'Document principal lisible'
  };

  return mapping[name] || name;
}

export default function UserPage() {
  const [searchParams] = useSearchParams();
  const selectedFromUrl = searchParams.get('selected');

  const [suppliers, setSuppliers] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [userData, setUserData] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSuppliers()
      .then((items) => {
        setSuppliers(items || []);
        setSelectedId(selectedFromUrl || items[0]?.id || '');
      })
      .catch(console.error);
  }, [selectedFromUrl]);

  useEffect(() => {
    if (!selectedId) return;

    async function loadData() {
      try {
        setLoading(true);

        const [complianceData, allDocuments] = await Promise.all([
          fetchCompliance(selectedId),
          fetchDocuments()
        ]);

        setUserData(complianceData);

        const filteredDocs = (allDocuments || []).filter(
          (doc) => doc.supplierId === selectedId
        );

        setDocuments(filteredDocs);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [selectedId]);

  const checklistStatus = getGlobalChecklistStatus(userData?.checks || []);

  const stats = useMemo(() => {
    return {
      total: documents.length,
      validated: documents.filter((doc) => getDocStatus(doc) === 'validated').length,
      warning: documents.filter((doc) => getDocStatus(doc) === 'warning').length,
      anomalies: documents.reduce(
        (acc, doc) => acc + (doc.validation?.anomalies?.length || 0),
        0
      )
    };
  }, [documents]);

  return (
    <div className="grid gap-6 xl:grid-cols-[320px,1fr]">
      <Card title="Mes dossiers">
        <div className="space-y-3">
          {suppliers.map((item) => (
            <button
              key={item.id}
              onClick={() => setSelectedId(item.id)}
              className={`w-full rounded-2xl border p-4 text-left transition ${
                selectedId === item.id
                  ? 'border-brand-500 bg-brand-500/10'
                  : 'border-slate-800 bg-slate-950/60 hover:border-slate-700'
              }`}
            >
              <p className="font-medium text-white">
                {item.supplierName || 'Utilisateur'}
              </p>
              <p className="mt-1 text-sm text-slate-400">
                {item.siret || 'SIRET non détecté'}
              </p>
            </button>
          ))}

          {!suppliers.length && (
            <p className="text-slate-400">Aucun dossier disponible.</p>
          )}
        </div>
      </Card>

      <div className="space-y-6">
        <Card title="Mon espace utilisateur">
          {userData ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <div>
                  <p className="text-sm text-slate-400">Entreprise</p>
                  <p className="text-lg font-semibold text-white">
                    {userData.supplierName}
                  </p>
                </div>
                <Badge status={userData.globalStatus}>
                  {userData.globalStatus}
                </Badge>
              </div>

              <div className="grid gap-4 md:grid-cols-4">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <p className="text-sm text-slate-400">Documents</p>
                  <p className="mt-2 text-2xl font-bold text-white">{stats.total}</p>
                </div>
                <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
                  <p className="text-sm text-slate-300">Validés</p>
                  <p className="mt-2 text-2xl font-bold text-white">{stats.validated}</p>
                </div>
                <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4">
                  <p className="text-sm text-slate-300">Warnings</p>
                  <p className="mt-2 text-2xl font-bold text-white">{stats.warning}</p>
                </div>
                <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4">
                  <p className="text-sm text-slate-300">Anomalies</p>
                  <p className="mt-2 text-2xl font-bold text-white">{stats.anomalies}</p>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p className="text-sm text-slate-400">Mes documents</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {userData.documentsReceived?.length ? (
                    userData.documentsReceived.map((item) => (
                      <Badge key={item} status="validated">
                        {item}
                      </Badge>
                    ))
                  ) : (
                    <p className="text-slate-400">Aucun document reçu.</p>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-slate-400">
              Sélectionne un dossier pour voir les documents et anomalies.
            </p>
          )}
        </Card>

        <Card title="Documents uploadés par cette entreprise">
          {loading ? (
            <p className="text-slate-400">Chargement des documents...</p>
          ) : documents.length ? (
            <div className="space-y-4">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-800 text-white">
                          <FileText size={18} />
                        </div>
                        <div className="min-w-0">
                          <p className="truncate font-medium text-white">
                            {doc.filename}
                          </p>
                          <p className="truncate text-sm text-slate-400">
                            {doc.documentType || 'document_inconnu'} • {doc.step || 'pending'}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <Badge status={getDocStatus(doc)}>
                        {getDocStatus(doc)}
                      </Badge>
                      <Link
                        to={`/documents/${doc.id}`}
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-700 px-3 py-2 text-sm text-slate-200 transition hover:border-slate-600 hover:text-white"
                      >
                        Voir
                        <ArrowRight size={14} />
                      </Link>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                        Type
                      </p>
                      <p className="mt-1 text-sm text-slate-300">
                        {doc.documentType || 'Non détecté'}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                        Statut
                      </p>
                      <p className="mt-1 text-sm text-slate-300">
                        {getDocStatus(doc)}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                        Anomalies
                      </p>
                      <p className="mt-1 text-sm text-slate-300">
                        {(doc.validation?.anomalies || []).length}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4">
                    {(doc.validation?.anomalies || []).length ? (
                      <div className="space-y-2">
                        {doc.validation.anomalies.map((item, index) => (
                          <div
                            key={`${doc.id}-${index}`}
                            className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-amber-200"
                          >
                            <TriangleAlert size={16} className="mt-0.5 shrink-0" />
                            <p className="text-sm">{item}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="flex items-start gap-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-emerald-200">
                        <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
                        <p className="text-sm">Aucune anomalie détectée.</p>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-400">Aucun document uploadé pour cette entreprise.</p>
          )}
        </Card>

        <Card title="Checklist conformité">
          {userData?.checks?.length ? (
            <div className="space-y-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-base font-semibold text-white">
                    Checklist conformité
                  </p>
                  <p className="mt-1 text-sm text-slate-400">
                    Résultat détaillé des contrôles réglementaires et documentaires.
                  </p>
                </div>

                <span
                  className={`inline-flex w-fit items-center rounded-full px-3 py-1 text-xs font-semibold ${globalChecklistClass(
                    checklistStatus
                  )}`}
                >
                  {checklistStatus === 'ok'
                    ? 'Validation complète'
                    : checklistStatus === 'partial'
                    ? 'Validation partielle'
                    : 'En attente'}
                </span>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {userData.checks.map((check, index) => {
                  const status = normalizeStatus(check.status);

                  return (
                    <div
                      key={`${check.name}-${index}`}
                      className="flex items-center justify-between rounded-3xl border border-slate-800 bg-slate-900/60 px-5 py-4"
                    >
                      <p className="pr-4 text-sm font-medium text-white">
                        {displayCheckName(check.name)}
                      </p>

                      <span
                        className={`inline-flex min-w-[72px] items-center justify-center rounded-full px-3 py-1 text-xs font-semibold ${statusPillClass(
                          status
                        )}`}
                      >
                        {status === 'ok'
                          ? 'OK'
                          : status === 'failed'
                          ? 'Échec'
                          : status === 'warning'
                          ? 'Warning'
                          : 'En attente'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="rounded-3xl border border-dashed border-slate-800 bg-slate-900/30 p-6 text-center text-slate-400">
              Aucun contrôle disponible.
            </div>
          )}
        </Card>

        <Card title="Anomalies détectées">
          {userData?.anomalies?.length ? (
            <ul className="space-y-3 text-slate-300">
              {userData.anomalies.map((item) => (
                <li
                  key={item}
                  className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-amber-200"
                >
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