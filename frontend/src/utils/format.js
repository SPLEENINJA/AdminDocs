export function formatDate(date) {
  if (!date) return '-';
  return new Date(date).toLocaleString('fr-FR');
}

//badgeTone est une fonction qui prend un statut en entrée et retourne une chaîne 
//de classes CSS pour définir la couleur du badge en fonction du statut.


export function badgeTone(status) {
  switch (status) {
    case 'validated':
    case 'verified':
    case 'passed':
      return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
    case 'warning':
    case 'pending':
      return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
    case 'failed':
    case 'rejected':
      return 'bg-rose-500/15 text-rose-300 border-rose-500/30';
    case 'processing':
      return 'bg-sky-500/15 text-sky-300 border-sky-500/30';
    default:
      return 'bg-slate-500/15 text-slate-300 border-slate-500/30';
  }
}
