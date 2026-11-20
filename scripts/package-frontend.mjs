// Package public build output in bounded parts for transfer to a small VPS.
import { mkdtempSync, mkdirSync, readdirSync, statSync, writeFileSync, createReadStream } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
const temporary = mkdtempSync(join(tmpdir(), 'openc-frontend-'));
execFileSync('tar', ['-czf', join(temporary, 'frontend.tar.gz'), '-C', 'build', '.']);
mkdirSync('build/_transfer', { recursive: true });
execFileSync('split', ['-b', '64m', '-d', join(temporary, 'frontend.tar.gz'), 'build/_transfer/frontend.part-']);
const files = [];
for (const name of readdirSync('build/_transfer').filter(n => n.startsWith('frontend.part-')).sort()) {
  const file = join('build/_transfer', name);
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  files.push({ name, bytes: statSync(file).size, sha256: hash.digest('hex') });
}
writeFileSync('build/_transfer/manifest.json', JSON.stringify({ commit: process.env.VERCEL_GIT_COMMIT_SHA, files }));
console.log('Packaged frontend:', files.length, 'parts');
