import { build } from 'esbuild';
import { readFile, writeFile, copyFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const output = resolve(root, '../static/vendor');
await mkdir(output, { recursive: true });
const copies = [
  ['bootstrap', 'dist/css/bootstrap.min.css', 'bootstrap-5.1.3.min.css'],
  ['bootstrap', 'dist/js/bootstrap.bundle.min.js', 'bootstrap-5.1.3.bundle.min.js'],
  ['bootstrap-portal', 'dist/css/bootstrap.min.css', 'bootstrap-5.3.3.min.css'],
  ['chart.js', 'dist/chart.umd.js', 'chart-4.5.1.umd.js'],
  ['qrcodejs', 'qrcode.min.js', 'qrcode-1.0.0.min.js'],
  ['quill', 'dist/quill.js', 'quill-2.0.2.js'],
  ['quill', 'dist/quill.snow.css', 'quill-2.0.2.snow.css'],
];
const manifest = {};
for (const [pkg, source, name] of copies) {
  const packageInfo = JSON.parse(await readFile(resolve(root, 'node_modules', pkg, 'package.json'), 'utf8'));
  await copyFile(resolve(root, 'node_modules', pkg, source), resolve(output, name));
  manifest[name] = { package: packageInfo.name, version: packageInfo.version };
}
await build({
  entryPoints: [resolve(root, 'node_modules/html2pdf.js/src/index.js')],
  bundle: true, minify: true, format: 'iife', globalName: 'MuniprotHtml2pdf',
  platform: 'browser', target: ['chrome120', 'firefox120', 'safari17'],
  outfile: resolve(output, 'html2pdf-0.14.0.bundle.min.js'),
  footer: { js: 'globalThis.html2pdf = MuniprotHtml2pdf.default;' },
  legalComments: 'eof',
});
manifest['html2pdf-0.14.0.bundle.min.js'] = {
  package: 'html2pdf.js', version: '0.14.0', jspdf: '4.2.1', dompurify: '3.4.17',
};
for (const [name, info] of Object.entries(manifest)) {
  const data = await readFile(resolve(output, name));
  info.bytes = data.length;
  info.sha256 = createHash('sha256').update(data).digest('hex');
  info.integrity = 'sha384-' + createHash('sha384').update(data).digest('base64');
}
const licenses = [];
for (const pkg of ['bootstrap', 'bootstrap-portal', 'chart.js', 'qrcodejs', 'html2pdf.js', 'jspdf', 'dompurify', 'quill']) {
  for (const name of ['LICENSE', 'LICENSE.md', 'LICENSE.txt']) {
    try { licenses.push(`${pkg}\n${await readFile(resolve(root, 'node_modules', pkg, name), 'utf8')}`); break; }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
}
await writeFile(resolve(output, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
await writeFile(resolve(output, 'LICENSES.txt'), licenses.join('\n\n--------------------\n\n'));
console.log(JSON.stringify(Object.fromEntries(Object.entries(manifest).map(([name, x]) => [name, x.bytes]))));
