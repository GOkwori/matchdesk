/**
 * Enforce the frontend performance budget on a production build (run after `npm run build`).
 *
 * For every prerendered studio page it sums the gzip size of the JavaScript and CSS that the
 * page's HTML loads, and fails when a page exceeds the budget: 170 KB of JS and 40 KB of
 * CSS (gzip), as set in the frontend implementation brief. Scripts marked `nomodule` (legacy
 * polyfills) are excluded because modern browsers never fetch them. No dependencies are needed.
 *
 * Usage: node scripts/check_web_budget.mjs [apps/web]
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { gzipSync } from 'node:zlib';

const app = process.argv[2] ?? 'apps/web';
const next = join(app, '.next');
const pages = join(next, 'server', 'app');
const BUDGET = { js: 170 * 1024, css: 40 * 1024 };

/** Every prerendered HTML file, skipping framework error shells and the developer workbench. */
function htmlFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === 'dev' ? [] : htmlFiles(path);
    return name.endsWith('.html') && !name.startsWith('_') ? [path] : [];
  });
}

const gzCache = new Map();
function gzipSize(asset) {
  if (!gzCache.has(asset)) gzCache.set(asset, gzipSync(readFileSync(join(next, asset.replace(/^\/_next\//, '')))).length);
  return gzCache.get(asset);
}

const rows = [];
for (const file of htmlFiles(pages)) {
  const html = readFileSync(file, 'utf8');
  // Read each tag's attributes; this is measurement, not sanitising. Legacy-browser
  // polyfills load with `nomodule`, which modern browsers never download.
  const assets = new Set();
  for (const [tag] of html.matchAll(/<(?:script|link)\s[^>]*>/gi)) {
    if (/\snomodule(?:[\s=>]|$)/i.test(tag)) continue;
    const ref = /\s(?:src|href)="(\/_next\/static\/[^"?]+\.(?:js|css))"/.exec(tag);
    if (ref) assets.add(ref[1]);
  }
  let js = 0;
  let css = 0;
  for (const asset of assets) {
    if (asset.endsWith('.js')) js += gzipSize(asset);
    else css += gzipSize(asset);
  }
  const route = '/' + relative(pages, file).replace(/\\/g, '/').replace(/\.html$/, '').replace(/(^|\/)index$/, '').replace(/\([^)]+\)\//g, '');
  rows.push({ route, js, css, ok: js <= BUDGET.js && css <= BUDGET.css });
}

if (!rows.length) {
  console.error('No prerendered pages found. Run `npm run build` in apps/web first.');
  process.exit(1);
}
const kb = (n) => `${(n / 1024).toFixed(1)} KB`;
for (const r of rows.sort((a, b) => b.js - a.js)) {
  console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.route.padEnd(48)} js ${kb(r.js).padStart(9)}  css ${kb(r.css).padStart(8)}`);
}
const failed = rows.filter((r) => !r.ok);
console.log(`\n${rows.length} pages checked against ${kb(BUDGET.js)} JS / ${kb(BUDGET.css)} CSS (gzip): ${failed.length} over budget.`);
process.exit(failed.length ? 1 : 0);
