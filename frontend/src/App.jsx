import { Route, Routes } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import DocumentsPage from './pages/DocumentsPage';
import DocumentDetailsPage from './pages/DocumentDetailsPage';
import CRMPage from './pages/CRMPage';
import UserPage from "./pages/UserPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />   //dashboard
        <Route path="/upload" element={<UploadPage />} />  //page upload
        <Route path="/documents" element={<DocumentsPage />} />  //liste des documents
        <Route path="/documents/:id" element={<DocumentDetailsPage />} />  //détail d’un document
        <Route path="/crm" element={<CRMPage />} />   //CRM fournisseur
        <Route path="/user" element={<UserPage />} />
      </Routes>
    </AppShell>
  );
}
