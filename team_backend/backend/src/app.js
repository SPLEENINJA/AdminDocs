import express from 'express';
import cors from 'cors';
import path from 'path';
import uploadRoutes from './routes/uploadRoutes.js';
import documentRoutes from './routes/documentRoutes.js';
import crmRoutes from './routes/crmRoutes.js';
import complianceRoutes from './routes/complianceRoutes.js';
import supplierRoutes from './routes/supplierRoutes.js';
import authRoutes from './routes/authRoutes.js';
import { notFound, errorHandler } from './middleware/errorHandler.js';
import { authenticateToken } from './middleware/auth.js';

const app = express();
const __dirname = path.resolve();

app.use(cors());
app.use(express.json());
app.use('/uploads', express.static(path.join(__dirname, 'src/uploads')));

app.get('/api/health', (_req, res) => {
  res.json({ success: true, message: 'AdminDocs API is healthy' });
});

app.use('/api/auth', authRoutes);
app.use('/api/upload', authenticateToken, uploadRoutes);
app.use('/api/documents', authenticateToken, documentRoutes);
app.use('/api/crm', authenticateToken, crmRoutes);
app.use('/api/compliance', authenticateToken, complianceRoutes);
app.use('/api/suppliers', authenticateToken, supplierRoutes);

app.use(notFound);
app.use(errorHandler);

export default app;
