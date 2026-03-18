
//Petit composant pour afficher un statut, depend de badgeTone dans utils/format.js pour définir la couleur du badge en fonction du statut.

import { badgeTone } from '../../utils/format';

export default function Badge({ children, status }) {
  return (
    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${badgeTone(status)}`}>
      {children}
    </span>
  );
}
