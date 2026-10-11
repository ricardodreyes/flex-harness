import { createServer } from 'node:http';
import { loadEnvFile } from 'node:process';
import { fileURLToPath } from 'node:url';
import { MongoClient } from 'mongodb';
import { fields, organizeReplay, sanitizeRecord } from './src/replay.js';

try { loadEnvFile(fileURLToPath(new URL('../.env', import.meta.url))); }
catch (error) { if (error.code !== 'ENOENT') throw new Error('Cannot load the server environment file.'); }

const collections = { versions: 'harness_versions', runs: 'runs', hours: 'hours', misses: 'misses' };
let client;

const server = createServer(async (request, response) => {
  response.setHeader('Content-Type', 'application/json');
  response.setHeader('Cache-Control', 'no-store');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  if (request.method !== 'GET' || request.url !== '/api/replay') {
    response.writeHead(404).end(JSON.stringify({ error: 'Not found.' }));
    return;
  }
  try {
    const uri = process.env.MONGODB_READER_URI;
    if (!uri) throw new Error('Reader configuration unavailable.');
    client ??= new MongoClient(uri, { serverSelectionTimeoutMS: 5000, maxPoolSize: 2 });
    const replay = { schema_version: 1, source: 'live', generated_at: new Date().toISOString(), scenarios: [] };
    const db = client.db('flex');
    for (const [kind, collection] of Object.entries(collections)) {
      const projection = Object.fromEntries(fields[kind].map(key => [key, 1]));
      if (!fields[kind].includes('_id')) projection._id = 0;
      const records = await db.collection(collection).find({}, { projection, maxTimeMS: 5000 }).toArray();
      replay[kind] = records.map(record => sanitizeRecord(kind, record));
    }
    const payload = JSON.stringify(replay);
    organizeReplay(JSON.parse(payload));
    response.writeHead(200).end(payload);
  } catch {
    response.writeHead(503).end(JSON.stringify({ error: 'Live replay unavailable. Check reader credentials and stored contract records on the server.' }));
  }
});

server.listen(4174, '127.0.0.1', () => console.log('Read-only replay API on http://127.0.0.1:4174/api/replay'));
process.once('SIGINT', () => server.close(async () => { await client?.close(); process.exit(0); }));
process.once('SIGTERM', () => server.close(async () => { await client?.close(); process.exit(0); }));
