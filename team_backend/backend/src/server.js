import app from './app.js';
import { initDatabase } from './config/database.js';

const PORT = process.env.PORT || 4000;

async function startServer() {
  try {
    await initDatabase();
    app.listen(PORT, () => {
      console.log(`API running on http://localhost:${PORT}`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

startServer();
