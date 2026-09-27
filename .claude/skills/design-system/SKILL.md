---
name: design-system
description: Charte visuelle de La Ruche — tokens de couleur, typographie, rayons, espacements en config Tailwind, règles d'usage et de contraste, les deux familles de gabarits, et les règles de mouvement & célébration. À lire avant de créer ou modifier un gabarit, un composant, une classe CSS ou toute animation.
---

# Design system — La Ruche

**Symbole** : une alvéole hexagonale dorée contenant un toit stylisé en trait encre et un
trait de sol (la ruche + le foyer) — pas une icône « maison » générique.
**Source unique** : `templates/components/_logo.html` (géométrie exacte de la marque,
viewBox 120 : hexagone `60,14 99.8,37 99.8,83 60,106 20.2,83 20.2,37`, toit
`M36 60 L60 38 L84 60`, sol de (44,78) à (76,78), traits de 7). Toute page l'inclut ;
ne jamais recopier le SVG (un test échoue si c'est le cas). `static/favicon.svg` reprend la
même géométrie avec les hex de la charte (fichier statique).
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
- **En-tête de l'accueil parent** : logomark + salutation selon la période (« Bonjour la
  famille » / « Bon après-midi » / « Bonsoir la famille ») + « Famille · date » en
  sous-titre, et **pastille d'étoiles** de la famille à droite (`bg-honey text-ink`,
  `rounded-sm`, icône étoile + nombre). « X tâches restantes » juste en dessous.
- **Tâche en mini-carte** (accueil parent comme écran partagé) : `rounded-md border
  border-border`, fond `bg-surface-100` dans une carte `surface-0` (mobile), espacées de
  `space-2` ; bordure `sage` quand la tâche est faite.
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
- **Célébration de palier** (colonne de l'enfant, écran partagé) : encart `bg-surface-100`
  bordé `honey-dark`, « Palier 2 ! Bravo Lina, 20 étoiles gagnées ! ». Distincte de la
  roue pour rester reconnaissable : badge étoilé qui arrive en tournoyant et alvéoles qui
  **montent** (la roue, elle, éclate en confettis). Une seule fois par palier.
- **Suppression** : page de confirmation (pas de `confirm()`), bouton `bg-terracotta
  text-surface-0`.
- **Progression en alvéoles** (écran partagé) : une alvéole par tâche de la période,
  `sage` si faite, `border` sinon, avec `aria-label` « X sur Y faites ».
- **Sélecteur interne « Cuisine »** : `parent/_kitchen_tabs.html`, 3 segments égaux
  (icône + texte), actif `bg-ink text-surface-0`, sinon `border-border-strong bg-surface-0`.
- **Créneau de menu** : ligne cliquable (≥ 56 px) « Déjeuner / Dîner » + repas ; une recette
  porte l'alvéole `honey` avec l'icône couverts, un repas libre est du texte seul ; créneau
  vide = « Ajouter un repas » en `ink-soft`. Jour courant bordé `honey-dark` (comme le semainier).
- **Carte « Ce soir au menu »** (accueil parent) : `parent/_dinner_card.html`, alvéole miel
  + couverts, nom du plat en `font-display`, lien « Voir la recette · 30 min ».
- **Article de courses** : `parent/_shopping_row.html`, même case que les préparatifs
  (cochée = `sage` + coche + « Acheté » + texte barré). L'origine est **toujours écrite** sous
  le nom avec son icône : « Menu · Couscous · Tajine », « Habituel · chaque semaine »,
  « Ajouté à la main ». Deux sections distinctes : « Du menu de la semaine » (alvéole `honey`)
  et « Habituels et ajouts » (alvéole contour `border-strong` sur `surface-100`). Boutons carrés
  44 px : « déjà à la maison » (maison + coche, masqué une fois acheté) et « modifier » (crayon).
- **Question de retransfert** : encart bordé `honey-dark` 2px « Déjà cochés : que faire ? »,
  deux puces radio (recette `_chip_choices`) **sans choix par défaut** ; erreur en `terracotta`
  avec `role="alert"` si on valide sans répondre.
- **Alerte « Le menu a changé »** (écran Courses) : même encart bordé `honey-dark`, bouton
  primaire « Voir les changements ». Jamais de rouge ni d'animation : c'est une information.
- **Favori** : icône cœur au trait (`ink`), jamais l'étoile (réservée aux étoiles gagnées),
  toujours avec le texte « Favoris » / « (favori) ».
- **Focus** : anneau `honey-dark` 2px décalé de 2px (déjà global via `:focus-visible`).
- Un état ne repose **jamais** sur la couleur seule : icône et/ou texte en plus.

## Deux familles de gabarits

Ne pas faire un seul gabarit « responsive » : les usages sont trop différents.

| | Vue parent | Affichage partagé enfants |
|---|---|---|
| Gabarit | `templates/layouts/parent_mobile.html` | `templates/layouts/shared_display.html` |
| Pages | `templates/parent/…` | `templates/shared/…` |
| Appareil | Téléphone personnel | Tablette / ordinateur commun sur un plan de travail |
| Structure | 1 colonne qui défile ; à partir de `lg`, pages à sections en 2 colonnes (`.page-grid`) | Colonnes côte à côte, **une par enfant, simultanées** |
| Navigation | Barre **fixe en bas**, labels toujours visibles ; à partir de `md`, **barre latérale** à gauche (même contenu, logo en tête) | Barre **horizontale en haut** |
| Accueil | Sélecteur de famille, période du jour ouverte, « 3 tâches restantes » (pas de %) | Avatar hexagonal, progression en alvéoles vers le palier d'étoiles |
| URL | `/` et pages parent | `/affichage/` |
| Navigation | Accueil / Semaine / Fêtes / Cuisine / Réglages | Onglets Aujourd'hui / Semaine / Fêtes / Samedi / Menu |

### Navigation parent : onglet « Cuisine » (Phase 4)

La barre du bas reste à **5 entrées, labels toujours visibles** (contrainte de la Phase 0 :
au-delà, les libellés ne tiennent plus sur un téléphone de 360 px). Menu, courses et
recettes partagent **un seul onglet « Cuisine »** (icône couverts, `/menu/`), avec en haut
de chacune de ces pages un **sélecteur interne à 3 segments** : *Menu · Courses · Recettes*
(`parent/_kitchen_tabs.html`, liens `aria-current="page"`, même recette que le sélecteur de
personne de l'accueil : segment actif `bg-ink text-surface-0`).

Pourquoi cette option plutôt qu'un bouton « Courses » dans l'écran Menu :
- **La liste de courses est un usage autonome** (au magasin, téléphone à la main, sans
  passer par le menu) : elle doit être à **deux taps de n'importe quelle page**, toujours au
  même endroit. Un bouton au milieu de la page Menu la rendrait dépendante du défilement
  et de la semaine affichée.
- Menu, recettes et courses forment **un seul flux** (je choisis des recettes → je planifie
  → j'envoie aux courses) : un onglet commun rend ce lien visible, et « Recettes » y trouve
  sa place sans 6e onglet.
- **Aucun onglet existant n'est sacrifié** (Semaine, Fêtes et Réglages gardent leur place),
  et l'URL `/menu/` historique reste l'entrée de l'onglet.
- Le libellé « Cuisine » est un mot court (tient sous l'icône) qui couvre les trois vues ;
  « Menu » seul aurait été trompeur une fois sur la liste de courses.

L'onglet est actif (`nav_active = "kitchen"`) sur les trois vues et leurs sous-pages.
Le bouton **« Envoyer aux courses »** du menu reste en plus un raccourci contextuel
(transfert du menu de la semaine affichée), pas le seul accès à la liste.

Les enfants n'ont pas la liste de courses : l'écran partagé ne gagne qu'un onglet
**« Menu »** en lecture seule (voir `permissions/SKILL.md`).

### Vue parent sur ordinateur et tablette

La vue parent reste pensée pour le téléphone, mais elle **s'adapte aux grands écrans**
(un parent l'ouvre aussi sur son ordinateur) : ce n'est pas un troisième gabarit, ce sont
les breakpoints du même `parent_mobile.html`.
- `< md` (téléphone) : inchangé — une colonne, nav en bas.
- `md` (≥ 768 px) : nav en **barre latérale** de 14 rem (logo + « La Ruche » en tête,
  entrées icône + libellé, entrée active sur `surface-100` avec l'icône sur `honey`) ;
  contenu élargi jusqu'à `max-w-3xl`, marges `space-8`. Le logo de l'en-tête de page est
  masqué (déjà dans la barre).
- `lg` (≥ 1024 px) : contenu jusqu'à `max-w-5xl`. Pages à plusieurs sections :
  `.page-grid` (2 colonnes alignées en haut). Accueil : tâches du jour à gauche (3/5),
  cartes (dîner, école, demain, samedi) à droite. Menu : jours en grille de 3.
- Pages à formulaire seul ou de confirmation : `content_width` étroit (`max-w-xl`), pour
  ne pas étirer un champ sur 1000 px.
- Aucune barre de défilement horizontale à aucune largeur (vérifié à 390 et 1280 px).

Les pages publiques (connexion, inscription, erreurs) utilisent un troisième gabarit
minimal, `layouts/public.html` : une carte centrée, sans navigation.
Le choix mobile / tablette ne dépend jamais du user-agent : deux URL distinctes, et
les adaptations de largeur passent par les breakpoints Tailwind.

## Mouvement & célébration — règles pour toute animation future

Implémenté : la roue du samedi (rotation ~3,6 s, puis révélation du résultat avec
confettis hexagonaux, une seule fois, jamais en boucle) et le palier d'étoiles (badge qui
tournoie, alvéoles qui montent, ~1,6 s, une seule fois par palier) — les deux « vraies
célébrations » de la règle 2. En mouvement réduit, les deux deviennent un état statique
(résultat / encart « Palier N ! » sans mouvement). L'interrupteur des réglages n'existe
pas encore dans l'interface : le CSS et le JS honorent déjà `data-motion="reduced"`.
Aussi : le rebond du badge à la coche (`hex-pop`, 150 ms, `assets/css/app.css`),
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
