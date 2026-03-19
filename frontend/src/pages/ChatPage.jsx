import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, FileText, Loader2, Sparkles } from 'lucide-react';
import Card from '../components/ui/Card';
import { askDocuments } from '../api/chat';

const EXEMPLES = [
  'Quelles factures ont un montant supérieur à 5 000 € ?',
  "Y a-t-il des attestations URSSAF expirées ?",
  'Liste tous les RIB disponibles avec leur IBAN.',
  'Quel est le SIRET du fournisseur principal ?',
];

const TYPE_LABELS = {
  facture: 'Facture', devis: 'Devis',
  attestation_urssaf: 'Attestation URSSAF', extrait_kbis: 'Kbis',
  rib: 'RIB', contrat: 'Contrat', inconnu: 'Inconnu',
};

// ── Bulle de message ──────────────────────────────────────────────────────────
function MessageBubble({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${isUser ? 'bg-brand-500' : 'bg-slate-700'}`}>
        {isUser ? <User size={14} className="text-white" /> : <Bot size={14} className="text-slate-200" />}
      </div>
      <div className={`max-w-[78%] flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${isUser ? 'rounded-tr-sm bg-brand-500 text-white' : 'rounded-tl-sm border border-slate-700 bg-slate-800/80 text-slate-100'}`}>
          {msg.content}
        </div>
        {!isUser && msg.sources?.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {msg.sources.map((src, i) => (
              <div key={i} className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-400">
                <FileText size={11} className="text-brand-400" />
                <span className="max-w-[140px] truncate">{src.fichier_source}</span>
                <span className="text-slate-600">·</span>
                <span className="text-brand-400">{Math.round(src.similarity * 100)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-700">
        <Bot size={14} className="text-slate-200" />
      </div>
      <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm border border-slate-700 bg-slate-800/80 px-4 py-3">
        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]" />
      </div>
    </div>
  );
}

// ── Page principale ───────────────────────────────────────────────────────────
export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [input,    setInput]    = useState('');
  const [loading,  setLoading]  = useState(false);
  const [docCount, setDocCount] = useState(null);
  const bottomRef = useRef(null);
  const inputRef  = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const sendQuestion = async (question) => {
    if (!question.trim() || loading) return;
    setMessages((prev) => [...prev, { role: 'user', content: question }]);
    setInput('');
    setLoading(true);
    try {
      const data = await askDocuments(question);
      setDocCount(data.documents_count);
      setMessages((prev) => [...prev, { role: 'assistant', content: data.answer, sources: data.sources || [] }]);
    } catch (err) {
      const msg = err.response?.data?.message || 'Une erreur est survenue. Veuillez réessayer.';
      setMessages((prev) => [...prev, { role: 'assistant', content: msg, sources: [] }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleSubmit = (e) => { e.preventDefault(); sendQuestion(input); };
  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-[calc(100vh-10rem)] flex-col gap-4">

      {/* Info compteur */}
      {docCount !== null && (
        <p className="text-sm text-slate-400">
          <span className="font-semibold text-brand-400">{docCount}</span> document{docCount !== 1 ? 's' : ''} indexé{docCount !== 1 ? 's' : ''} dans ChromaDB
        </p>
      )}

      {/* Zone messages */}
      <div className="flex-1 overflow-y-auto rounded-[2rem] border border-slate-800 bg-slate-950/60 p-6">
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-6">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-500">
              <Sparkles size={28} />
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-white">Interrogez vos documents</p>
              <p className="mt-1 text-sm text-slate-400">
                Le système recherche dans tous vos documents analysés et génère une réponse précise.
              </p>
            </div>
            <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
              {EXEMPLES.map((q) => (
                <button
                  key={q}
                  onClick={() => { setInput(q); inputRef.current?.focus(); }}
                  className="rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-left text-sm text-slate-300 transition hover:border-brand-500/50 hover:bg-slate-800 hover:text-white"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Saisie */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Posez votre question sur vos documents…"
          disabled={loading}
          className="flex-1 rounded-2xl border border-slate-700 bg-slate-900 px-5 py-3 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-brand-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="flex items-center gap-2 rounded-2xl bg-brand-500 px-5 py-3 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          {loading ? 'Génération…' : 'Envoyer'}
        </button>
      </form>

      {messages.length > 0 && !loading && (
        <button onClick={() => setMessages([])} className="self-end text-xs text-slate-600 hover:text-slate-400">
          Effacer la conversation
        </button>
      )}
    </div>
  );
}
