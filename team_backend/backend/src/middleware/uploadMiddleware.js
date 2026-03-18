import multer from 'multer';
import path from 'path';
import fs from 'fs';
import { randomUUID } from 'crypto';

const uploadDirectory = path.resolve('src/uploads');
fs.mkdirSync(uploadDirectory, { recursive: true });

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDirectory),
  filename: (_req, file, cb) => {
    const extension = path.extname(file.originalname);
    const safeName = file.originalname
      .replace(extension, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-');

    cb(null, `${Date.now()}-${safeName}-${randomUUID().slice(0, 8)}${extension}`);
  }
});

function fileFilter(_req, file, cb) {
  const allowed = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
  if (allowed.includes(file.mimetype)) cb(null, true);
  else cb(new Error('Formats acceptés : PDF, PNG, JPG, WEBP'));
}

export const upload = multer({
  storage,
  fileFilter,
  limits: { fileSize: 8 * 1024 * 1024 }
});
