
//Card.jsx est un composant réutilisable qui affiche une section avec un titre, une action (comme un bouton) et du contenu.

export default function Card({ title, action, children }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6 shadow-2xl shadow-black/20">
      {(title || action) && (
        <div className="mb-5 flex items-center justify-between gap-4">
          {title ? <h2 className="text-lg font-semibold text-white">{title}</h2> : <span />}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
