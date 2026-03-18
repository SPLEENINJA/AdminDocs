import { FileText, FolderKanban, LayoutDashboard, ShieldCheck, Upload } from 'lucide-react';
import { Link, NavLink } from 'react-router-dom';

//avec NavLink, le menu devient dynamique  
//générer le menu automatiquement.
const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/upload', label: 'Upload', icon: Upload },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/crm', label: 'CRM', icon: FolderKanban },
  { to: '/compliance', label: 'Conformité', icon: ShieldCheck }
];


// définit la structure visuelle globale de l’application, avec une barre latérale pour la navigation et une zone principale pour le contenu.


export default function AppShell({ children }) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <aside className="fixed inset-y-0 left-0 hidden w-72 border-r border-slate-800 bg-slate-950/95 p-6 lg:block">
        <Link to="/" className="mb-8 block">
          <p className="text-xs uppercase tracking-[0.35em] text-brand-500">Hackathon 2026</p>
          <h1 className="mt-2 text-3xl font-bold text-white">AdminDocs</h1>
          <p className="mt-2 text-sm text-slate-400">Front & API pour la gestion documentaire intelligente.</p>
        </Link>

        <nav className="space-y-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition ${
                  isActive ? 'bg-brand-500 text-white' : 'text-slate-300 hover:bg-slate-900 hover:text-white'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="lg:pl-72">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</div>
      </main>
    </div>
  );
}
