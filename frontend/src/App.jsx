import { Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import PrivateRoute from './components/PrivateRoute';
import AppShell from './components/layout/AppShell';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import DocumentsPage from './pages/DocumentsPage';
import DocumentDetailsPage from './pages/DocumentDetailsPage';
import CRMPage from './pages/CRMPage';
import UserPage from './pages/UserPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        
        <Route path="/" element={
          <PrivateRoute>
            <AppShell>
              <DashboardPage />
            </AppShell>
          </PrivateRoute>
        } />
        
        <Route path="/upload" element={
          <PrivateRoute>
            <AppShell>
              <UploadPage />
            </AppShell>
          </PrivateRoute>
        } />
        
        <Route path="/documents" element={
          <PrivateRoute>
            <AppShell>
              <DocumentsPage />
            </AppShell>
          </PrivateRoute>
        } />
        
        <Route path="/documents/:id" element={
          <PrivateRoute>
            <AppShell>
              <DocumentDetailsPage />
            </AppShell>
          </PrivateRoute>
        } />
        
        <Route path="/crm" element={
          <PrivateRoute>
            <AppShell>
              <CRMPage />
            </AppShell>
          </PrivateRoute>
        } />
        
        <Route path="/user" element={
          <PrivateRoute>
            <AppShell>
              <UserPage />
            </AppShell>
          </PrivateRoute>
        } />
      </Routes>
    </AuthProvider>
  );
}
