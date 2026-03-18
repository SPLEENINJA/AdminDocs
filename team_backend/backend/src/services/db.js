import fs from 'fs/promises';
import path from 'path';

const dataFile = path.resolve('src/data/db.json');

const initialDb = {
  documents: [],
  suppliers: []
};

// Mutex simple pour éviter les écritures concurrentes
let writeLock = Promise.resolve();

async function ensureDb() {
  try {
    await fs.access(dataFile);
  } catch {
    await fs.mkdir(path.dirname(dataFile), { recursive: true });
    await fs.writeFile(dataFile, JSON.stringify(initialDb, null, 2), 'utf-8');
  }
}

export async function readDb() {
  await ensureDb();
  const raw = await fs.readFile(dataFile, 'utf-8');
  return JSON.parse(raw);
}

export async function writeDb(data) {
  await ensureDb();
  writeLock = writeLock.then(() =>
    fs.writeFile(dataFile, JSON.stringify(data, null, 2), 'utf-8')
  );
  return writeLock;
}
