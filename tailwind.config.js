/**
 * La Ruche — configuration Tailwind.
 *
 * Les valeurs ci-dessous sont la charte validée, au caractère près.
 * Source de vérité documentaire : .claude/skills/design-system/SKILL.md
 * Toute modification doit être répercutée dans scripts/check-tokens.mjs
 * (vérifié en CI) et dans le skill.
 *
 * La palette REMPLACE celle de Tailwind (pas d'extend) : aucune couleur hors
 * charte n'est disponible, donc aucune ne peut se glisser dans un gabarit.
 *
 * @type {import('tailwindcss').Config}
 */
module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './apps/**/*.py',
    './static/js/**/*.js',
  ],
  // Grille horaire du semainier (apps/agenda/grid.py) : lignes et hauteurs des
  // blocs calculées côté serveur, donc absentes des gabarits.
  safelist: [{ pattern: /^row-(start|span)-([1-9]|[12][0-9]|30)$/ }, { pattern: /^col-start-[1-3]$/ }],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      surface: {
        0: '#FFFFFF', // fond des cartes
        100: '#FBF6EC', // fond de page (jamais de blanc pur en fond)
      },
      ink: {
        DEFAULT: '#241B13', // texte principal
        soft: '#5C4E3F', // texte secondaire
      },
      border: {
        DEFAULT: '#E7DCC6', // séparateurs discrets
        strong: '#9C8B65', // contours des champs interactifs / cases à cocher
      },
      honey: {
        DEFAULT: '#E8A33D', // marque, boutons primaires (texte ink dessus)
        dark: '#B97A1E', // survol / pressé
      },
      terracotta: '#B34F39', // accent « à faire » / enfants (texte blanc dessus)
      sage: '#3F6B47', // état validé (texte blanc dessus, toujours avec icône)
    },
    fontFamily: {
      display: ['Fredoka', 'ui-rounded', 'system-ui', 'sans-serif'],
      sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
    },
    // Seules les graisses réellement chargées depuis Google Fonts.
    fontWeight: {
      normal: '400',
      medium: '500',
      semibold: '600',
    },
    extend: {
      borderRadius: {
        sm: '10px', // chips, petits boutons
        md: '16px', // cartes, champs
        lg: '28px', // boutons principaux, modales
      },
      gridRowStart: Object.fromEntries(
        Array.from({ length: 31 }, (_, i) => [String(i + 1), String(i + 1)]),
      ),
      gridRow: Object.fromEntries(
        Array.from({ length: 30 }, (_, i) => [`span-${i + 1}`, `span ${i + 1} / span ${i + 1}`]),
      ),
      spacing: {
        'space-2': '8px',
        'space-4': '16px',
        'space-6': '24px',
        'space-8': '32px',
      },
    },
  },
  plugins: [],
};
