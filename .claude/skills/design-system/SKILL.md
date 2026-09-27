---
name: design-system
description: Charte visuelle de La Ruche — tokens de couleur, typographie, rayons, espacements en config Tailwind, règles d'usage et de contraste, les deux familles de gabarits, et les règles de mouvement & célébration. À lire avant de créer ou modifier un gabarit, un composant, une classe CSS ou toute animation.
---

# Design system — La Ruche

**Symbole** : une alvéole hexagonale contenant un toit simplifié (la ruche + le foyer).
L'hexagone est le motif récurrent : avatars, badges de tâche, barre de progression en alvéoles.

La config ci-dessous est **déjà en place** dans `tailwind.config.js`. Elle est vérifiée
en CI par `npm run check:tokens` (`scripts/check-tokens.mjs`) : un hex qui dérive
fait échouer le build. Toute modification de token = modifier les trois ensemble
(config, script de contrôle, ce fichier).

## Couleurs (thème clair uniquement)

| Token | Hex | Classe | Usage |
|---|---|---|---|
| surface-100 | `#FBF6EC` | `bg-surface-100` | Fond de page. **Jamais de blanc pur en fond de page.** |
| surface-0 | `#FFFFFF` | `bg-surface-0` | Fond des cartes. Aussi le « texte blanc » : `text-surface-0`. |
| ink | `#241B13` | `text-ink` | Texte principal. |
| ink-soft | `#5C4E3F` | `text-ink-soft` | Texte secondaire. |
| border | `#E7DCC6` | `border-border` | Séparateurs discrets (décoratif uniquement). |
| border-strong | `#9C8B65` | `border-border-strong` | Contours des champs interactifs, cases à cocher. |
| honey | `#E8A33D` | `bg-honey` | Marque, boutons primaires. **Texte `text-ink` dessus, jamais blanc.** |
| honey-dark | `#B97A1E` | `bg-honey-dark` | Survol / pressé des éléments miel. Anneau de focus. |
| terracotta | `#B34F39` | `bg-terracotta` | Accent « à faire » / enfants. Texte `text-surface-0` dessus. |
| sage | `#3F6B47` | `bg-sage` | État validé. Texte `text-surface-0` dessus, **toujours accompagné d'une icône** (jamais la couleur seule). |

La palette **remplace** celle de Tailwind : `bg-white`, `text-gray-500`, `bg-red-600`…
n'existent pas. Seuls `transparent` et `current` s'ajoutent aux 10 tokens.

### Contrastes mesurés (WCAG 2.x)

| Combinaison | Ratio | Verdict |
|---|---|---|
| ink sur surface-100 / surface-0 | 15.7 / 16.9 | AAA |
| ink-soft sur surface-100 / surface-0 | 7.45 / 8.03 | AAA |
| ink sur honey | 7.85 | AAA — c'est pour ça que le texte des boutons miel est ink |
| surface-0 (blanc) sur honey | **2.16** | **Interdit** |
| ink sur honey-dark | 4.73 | AA |
| blanc sur terracotta | 5.13 | AA |
| blanc sur sage | 6.17 | AA |
| border-strong sur surface-100 / surface-0 | 3.10 / 3.34 | OK pour contours d'UI (seuil 3:1) |
| border sur surface-100 | **1.26** | Décoratif seulement : jamais seule limite d'un élément interactif |
| honey (texte) sur surface-100 | **2.00** | **Interdit comme couleur de texte ou d'icône seule** |
| honey-dark sur surface-100 | 3.32 | Grand texte / focus ring uniquement |
| terracotta / sage (texte) sur surface-100 | 4.76 / 5.72 | AA |

## Typographie

- `font-display` = **Fredoka** (500, 600) : titres. Appliquée d'office à `h1`–`h4`.
- `font-sans` = **Inter** (400, 500, 600) : texte courant (police par défaut).
- Graisses disponibles : `font-normal` (400), `font-medium` (500), `font-semibold` (600).
  `font-bold` n'existe volontairement pas (graisse non chargée → faux gras).
- Chargement : Google Fonts dans `templates/base.html`, autorisé par la CSP
  (`fonts.googleapis.com` / `fonts.gstatic.com`).

## Rayons

| Token | Valeur | Classe | Usage |
|---|---|---|---|
| radius-sm | 10px | `rounded-sm` | Chips, petits boutons |
| radius-md | 16px | `rounded-md` | Cartes, champs |
| radius-lg | 28px | `rounded-lg` | Boutons principaux, modales |

## Espacements

| Token | Valeur | Classes |
|---|---|---|
| space-2 | 8px | `p-space-2`, `gap-space-2`, `m-space-2`… |
| space-4 | 16px | `p-space-4`… |
| space-6 | 24px | `p-space-6`… |
| space-8 | 32px | `p-space-8`… |

Préférer ces tokens à l'échelle numérique de Tailwind pour tout espacement de mise en page.

## Config Tailwind de référence

```js
// tailwind.config.js (extrait — le fichier réel fait foi)
theme: {
  colors: {
    transparent: 'transparent',
    current: 'currentColor',
    surface: { 0: '#FFFFFF', 100: '#FBF6EC' },
    ink: { DEFAULT: '#241B13', soft: '#5C4E3F' },
    border: { DEFAULT: '#E7DCC6', strong: '#9C8B65' },
    honey: { DEFAULT: '#E8A33D', dark: '#B97A1E' },
    terracotta: '#B34F39',
    sage: '#3F6B47',
  },
  fontFamily: {
    display: ['Fredoka', 'ui-rounded', 'system-ui', 'sans-serif'],
    sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
  },
  fontWeight: { normal: '400', medium: '500', semibold: '600' },
  extend: {
    borderRadius: { sm: '10px', md: '16px', lg: '28px' },
    spacing: { 'space-2': '8px', 'space-4': '16px', 'space-6': '24px', 'space-8': '32px' },
  },
}
```

Les tokens sont aussi exposés en variables CSS (`var(--color-honey)`, etc.) dans
`assets/css/app.css`, pour les SVG inline (hexagones) et les rares styles calculés.

## Recettes de composants

- **Bouton primaire** : `bg-honey text-ink rounded-lg font-medium hover:bg-honey-dark`.
- **Carte** : `bg-surface-0 rounded-md border border-border`.
- **Champ / case à cocher** : contour `border-border-strong`, `rounded-md` pour les champs.
- **Alvéole** : classe `.hex` (`clip-path` hexagonal, `assets/css/app.css`) sur une boîte
  carrée. Sert aux avatars, badges et à la progression.
- **Avatar** : `components/_avatar.html`, initiale sur la couleur de la personne
  (`terracotta`, `honey`, `honey-dark`, `ink-soft` ; jamais `sage`, réservé à « validé »).
- **Case à cocher de tâche** : vraie `<input type="checkbox">` en `appearance-none`,
  contour `border-border-strong`, cochée = fond `sage` + coche blanche.
- **Badge de tâche hexagonal** : doré (`honey`) = à faire ; `sage` + icône coche = fait.
  L'état suit la case en CSS (`group-has-[:checked]:`), donc instantanément.
- **Étiquette « Fait ! +1 »** sur les tâches cochées (vue enfants) ; « Fait » en vue parent.
- **Badges d'information** (école) : `components/_school_badges.html`. Puce
  `border-border-strong` + alvéole `honey` avec icône `ink` + texte (« Cantine »,
  « Sandwich (APC) », « Étude ce soir »). Même famille que les badges de tâche, mais
  sans état « fait » : jamais `sage`.
- **Icônes** : `components/_icon.html` (trait `currentColor`, décoratives, toujours
  accompagnées de texte).
- **Choix en puces** (radio / cases) : `parent/_chip_choices.html`, sélection = fond `ink`
  + texte `surface-0`, focus visible sur la puce.
- **Badges d'activité** : `components/_activity_badges.html` (étoiles, gratuit/payant,
  sortie/maison), même recette que les badges d'école.
- **Roue du samedi** : `parent/_wheel.html`, secteurs alternant `honey`, `surface-0` et
  `honey-dark` (texte `ink` : contrastes AA), pointeur `terracotta`, moyeu hexagonal.
- **Étoiles** : alvéole `honey` + icône étoile + « 12 étoiles · palier dans 8 ».
- **Suppression** : page de confirmation (pas de `confirm()`), bouton `bg-terracotta
  text-surface-0`.
- **Progression en alvéoles** (écran partagé) : une alvéole par tâche de la période,
  `sage` si faite, `border` sinon, avec `aria-label` « X sur Y faites ».
- **Focus** : anneau `honey-dark` 2px décalé de 2px (déjà global via `:focus-visible`).
- Un état ne repose **jamais** sur la couleur seule : icône et/ou texte en plus.

## Deux familles de gabarits

Ne pas faire un seul gabarit « responsive » : les usages sont trop différents.

| | Vue parent | Affichage partagé enfants |
|---|---|---|
| Gabarit | `templates/layouts/parent_mobile.html` | `templates/layouts/shared_display.html` |
| Pages | `templates/parent/…` | `templates/shared/…` |
| Appareil | Téléphone personnel | Tablette / ordinateur commun sur un plan de travail |
| Structure | 1 colonne qui défile | Colonnes côte à côte, **une par enfant, simultanées** |
| Navigation | Barre **fixe en bas**, labels toujours visibles | Barre **horizontale en haut** |
| Accueil | Sélecteur de famille, période du jour ouverte, « 3 tâches restantes » (pas de %) | Avatar hexagonal, progression en alvéoles vers le palier d'étoiles |
| URL | `/` et pages parent | `/affichage/` |
| Navigation | Accueil / Semaine / Fêtes / Menu / Réglages | Onglets Aujourd'hui / Semaine / Fêtes |

Les pages publiques (connexion, inscription, erreurs) utilisent un troisième gabarit
minimal, `layouts/public.html` : une carte centrée, sans navigation.
Le choix mobile / tablette ne dépend jamais du user-agent : deux URL distinctes, et
les adaptations de largeur passent par les breakpoints Tailwind.

## Mouvement & célébration — règles pour toute animation future

Implémenté : la roue du samedi (rotation ~3,6 s, puis révélation du résultat avec
confettis hexagonaux, une seule fois, jamais en boucle) — c'est la « vraie célébration »
de la règle 2 ; le rebond du badge à la coche (`hex-pop`, 150 ms, `assets/css/app.css`),
limité au geste de l'utilisateur et désactivé en mouvement réduit (système ou
`data-motion="reduced"`). Toute animation ajoutée ensuite doit respecter :

1. **Coche = micro-feedback immédiat.** Réponse visuelle instantanée au tap (≤ 150 ms,
   ex. léger rebond du badge, passage à sage + coche). Optimiste côté client, confirmé
   par HTMX. Discret, jamais bloquant.
2. **Palier d'étoiles = vraie célébration** (confettis, éclat). Réservée aux vraies
   réussites. Ne jamais la déclencher pour une action ordinaire : sa rareté fait sa valeur.
3. **`prefers-reduced-motion` toujours respecté.** Écrire les animations avec la variante
   `motion-safe:` de Tailwind (ou à l'intérieur d'un `@media (prefers-reduced-motion: no-preference)`).
   En mouvement réduit : la célébration devient un état statique (message + étoile), sans
   mouvement ni confettis.
4. **Interrupteur dans les réglages** pour réduire les animations indépendamment de l'OS
   (prévu : attribut `data-motion="reduced"` sur `<html>`, qui doit produire le même
   résultat que la préférence système). Toute animation doit honorer les deux.
5. **Jamais d'animation culpabilisante pour les retards** : pas de clignotement, de
   tremblement, de rouge qui pulse, de compte à rebours anxiogène, de mascotte triste.
   Une tâche en retard reste simplement « à faire ».
6. Pas d'animation en boucle infinie sur l'écran partagé (distraction permanente).
7. Animations CSS ou Alpine (build CSP, composants déclarés dans `static/js/app.js`) ;
   aucune bibliothèque d'animation chargée depuis un CDN (CSP).
