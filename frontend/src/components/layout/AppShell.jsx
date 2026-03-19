import {
  FileText,
  FolderKanban,
  LayoutDashboard,
  Upload,
  UserCircle2,
  Sparkles,
  BellRing,
  LogOut
} from 'lucide-react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/upload', label: 'Upload', icon: Upload },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/crm', label: 'CRM', icon: FolderKanban },
  { to: '/user', label: 'User', icon: UserCircle2 }
];

function getNavLinkClass(isActive) {
  return [
    'flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-all duration-200',
    isActive
      ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/20'
      : 'text-slate-300 hover:bg-slate-900 hover:text-white'
  ].join(' ');
}

export default function AppShell({
  children,
  title = 'AdminDocs',
  subtitle = '',
  actions = null
}) {
  const navigate = useNavigate();
  const { logout, user } = useAuth();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Sidebar gauche */}
      <aside className="fixed inset-y-0 left-0 hidden w-72 border-r border-slate-800 bg-slate-950/95 p-6 lg:flex lg:flex-col">
        <Link to="/" className="block">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-400">
              <Sparkles size={22} />
            </div>

            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-brand-500">
                Hackathon 2026
              </p>
              <h1 className="mt-1 text-2xl font-bold text-white">AdminDocs</h1>
            </div>
          </div>

          <p className="mt-4 text-sm leading-6 text-slate-400">
            Front & API pour la gestion documentaire intelligente, la détection
            d’anomalies et l’intégration métier.
          </p>
        </Link>

        <nav className="mt-8 space-y-2 flex-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => getNavLinkClass(isActive)}
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto pt-6 border-t border-slate-800">
          <div className="mb-3 rounded-2xl bg-slate-900/60 px-4 py-3">
            <p className="text-xs text-slate-500">Connecté en tant que</p>
            <p className="mt-1 font-medium text-white">{user?.username || 'Utilisateur'}</p>
          </div>
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium text-slate-300 transition-all duration-200 hover:bg-slate-900 hover:text-white"
          >
            <LogOut size={18} />
            <span>Déconnexion</span>
          </button>
        </div>
      </aside>

      {/* Contenu principal */}
      <main className="lg:pl-72">
        {/* Header */}
        <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/85 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                AdminDocs Platform
              </p>
              <h2 className="mt-1 text-2xl font-bold text-white lg:text-3xl">
                {title}
              </h2>
              {subtitle ? (
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                  {subtitle}
                </p>
              ) : null}
            </div>

            <div className="flex items-center gap-3">
              {actions}
            </div>
          </div>
        </header>

        {/* Page */}
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </div>
      </main>
    </div>
  );
}