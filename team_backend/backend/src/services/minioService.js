import { Client } from 'minio';
import fs from 'fs';
import path from 'path';

const [minioHost, minioPort] = (process.env.MINIO_ENDPOINT || 'minio:9000').split(':');

const minioClient = new Client({
  endPoint: minioHost || 'minio',
  port: parseInt(minioPort || '9000'),
  useSSL: false,
  accessKey: process.env.MINIO_ACCESS_KEY || 'minio_user',
  secretKey: process.env.MINIO_SECRET_KEY || 'minio_password',
});

const BUCKET_RAW = process.env.MINIO_BUCKET_RAW || 'raw';
const BUCKET_CLEAN = process.env.MINIO_BUCKET_CLEAN || 'clean';

export async function uploadToRaw(storedFilename, filePath, mimetype) {
  try {
    await minioClient.fPutObject(BUCKET_RAW, storedFilename, filePath, {
      'Content-Type': mimetype || 'application/octet-stream',
    });
    console.log(`[minio] ✓ raw/${storedFilename}`);
  } catch (err) {
    console.warn(`[minio] ✗ upload raw: ${err.message}`);
  }
}

export async function uploadJsonToClean(documentId, data) {
  try {
    const jsonStr = JSON.stringify(data, null, 2);
    const objectName = `${documentId}.json`;
    await minioClient.putObject(BUCKET_CLEAN, objectName, jsonStr, Buffer.byteLength(jsonStr), {
      'Content-Type': 'application/json',
    });
    console.log(`[minio] ✓ clean/${objectName}`);
  } catch (err) {
    console.warn(`[minio] ✗ upload clean: ${err.message}`);
  }
}
