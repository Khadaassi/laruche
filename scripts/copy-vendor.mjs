// Copie les bibliothèques JS dans static/vendor/ pour qu'elles soient servies
// par l'app elle-même (CSP script-src 'self', aucun CDN tiers).
import { copyFileSync, mkdirSync } from 'node:fs';

const files = {
  'node_modules/htmx.org/dist/htmx.min.js': 'static/vendor/htmx.min.js',
  // Build « CSP » d'Alpine : n'utilise pas eval/new Function.
  'node_modules/@alpinejs/csp/dist/cdn.min.js': 'static/vendor/alpine-csp.min.js',
};

mkdirSync('static/vendor', { recursive: true });
for (const [src, dest] of Object.entries(files)) {
  copyFileSync(src, dest);
  console.log(`${src} -> ${dest}`);
}
