// Vérifie que tailwind.config.js reproduit exactement la charte La Ruche.
// Lancé en CI : un token qui dérive fait échouer le build.
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const resolveConfig = require('tailwindcss/resolveConfig');
const { theme } = resolveConfig(require('../tailwind.config.js'));

const expected = {
  colors: {
    'surface-0': '#FFFFFF',
    'surface-100': '#FBF6EC',
    ink: '#241B13',
    'ink-soft': '#5C4E3F',
    border: '#E7DCC6',
    'border-strong': '#9C8B65',
    honey: '#E8A33D',
    'honey-dark': '#B97A1E',
    terracotta: '#B34F39',
    sage: '#3F6B47',
  },
  borderRadius: { sm: '10px', md: '16px', lg: '28px' },
  spacing: { 'space-2': '8px', 'space-4': '16px', 'space-6': '24px', 'space-8': '32px' },
  fontFamily: { display: 'Fredoka', sans: 'Inter' },
};

// Aplatit { ink: { DEFAULT, soft } } en { ink, 'ink-soft' }, comme les classes.
function flatten(obj, prefix = '') {
  return Object.entries(obj).reduce((acc, [key, value]) => {
    const name = key === 'DEFAULT' ? prefix : prefix ? `${prefix}-${key}` : key;
    return typeof value === 'object'
      ? { ...acc, ...flatten(value, name) }
      : { ...acc, [name]: value };
  }, {});
}

const errors = [];
const colors = flatten(theme.colors);
const allowed = new Set([...Object.keys(expected.colors), 'transparent', 'current']);

for (const [name, hex] of Object.entries(expected.colors)) {
  if (colors[name] !== hex) errors.push(`couleur ${name} : attendu ${hex}, trouvé ${colors[name]}`);
}
for (const name of Object.keys(colors)) {
  if (!allowed.has(name)) errors.push(`couleur hors charte : ${name} (${colors[name]})`);
}
for (const key of ['borderRadius', 'spacing']) {
  for (const [name, value] of Object.entries(expected[key])) {
    if (theme[key][name] !== value) {
      errors.push(`${key}.${name} : attendu ${value}, trouvé ${theme[key][name]}`);
    }
  }
}
for (const [name, family] of Object.entries(expected.fontFamily)) {
  if (theme.fontFamily[name]?.[0] !== family) {
    errors.push(`fontFamily.${name} : attendu ${family} en premier`);
  }
}

if (errors.length) {
  console.error('Tokens non conformes à la charte :\n- ' + errors.join('\n- '));
  process.exit(1);
}
console.log(`Tokens conformes : ${Object.keys(expected.colors).length} couleurs, 3 rayons, 4 espacements, 2 polices.`);
