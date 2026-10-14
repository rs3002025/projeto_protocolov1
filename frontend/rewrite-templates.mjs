// Mechanical migration of external library URLs to audited, local assets.
import { readFile, writeFile, readdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(await readFile(resolve(root, '../static/vendor/manifest.json'), 'utf8'));
const assets = {
  'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css': 'bootstrap-5.1.3.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js': 'bootstrap-5.1.3.bundle.min.js',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css': 'bootstrap-5.3.3.min.css',
  'https://cdn.jsdelivr.net/npm/chart.js': 'chart-4.5.1.umd.js',
  'https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js': 'html2pdf-0.14.0.bundle.min.js',
  'https://cdn.jsdelivr.net/gh/davidshimjs/qrcodejs/qrcode.min.js': 'qrcode-1.0.0.min.js',
};
for (const name of await readdir(resolve(root, '../templates'))) {
  if (!name.endsWith('.html')) continue;
  const path = resolve(root, '../templates', name);
  const before = await readFile(path, 'utf8');
  let after = before;
  for (const [source, target] of Object.entries(assets)) {
    after = after.replaceAll(`"${source}"`,
      `"{{ url_for('static', filename='vendor/${target}') }}" integrity="${manifest[target].integrity}" crossorigin="anonymous"`);
  }
  if (after !== before) await writeFile(path, after);
}
