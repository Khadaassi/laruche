# CLAUDE.md — La Ruche

Application d'organisation familiale (semainier, tâches des enfants, menu, roue du
samedi…). Projet repris **de zéro** : ne jamais réutiliser de code de l'ancien repo
« notre-semaine ».

## Phase actuelle

**Phase 2 — école, ménage, fêtes.** En plus de la Phase 1 (familles, tâches du jour,
accueil parent, écran partagé) : cantine/APC/étude par enfant avec exceptions datées,
« à préparer pour demain », ménage et semainier, fêtes (préparatifs, cadeaux, recettes).
Modèle et choix documentés dans `.claude/skills/domain-model/SKILL.md`.
Menu est encore une page « à venir ».

## Stack

- **Python 3.13**, **Django 5.2 LTS**, dépendances gérées par **uv** (`pyproject.toml`, `uv.lock`)
- **PostgreSQL via Neon** (`DATABASE_URL`, parsée par `dj-database-url`, URL « pooled »)
- **Tailwind CSS 3** (`tailwind.config.js`, source `assets/css/app.css` → `static/css/app.css`)
- **HTMX 2** pour les interactions serveur sans rechargement (drag & drop, roue du samedi…)
- **Alpine.js 3, build CSP** (`@alpinejs/csp`) pour l'interactivité légère côté client
- **django-csp 4**, **WhiteNoise** (statiques), **gunicorn** (1 worker : requis par le cache
  mémoire du rate-limit), **django-ratelimit** (connexion, code famille, sortie tablette)
- Hébergement : **Render** gratuit (`render.yaml`, `Dockerfile`), déployé à chaque merge sur
  `main` si la CI est verte ; sonde `/livez/` sans base (ne jamais sonder `/healthz/` en boucle : Neon)
- Qualité : **ruff** (lint + format), tests Django (`manage.py test`)
- Releases : **semantic-release** sur Conventional Commits

## Structure

```
config/                 réglages, urls, wsgi/asgi (settings.py unique, piloté par env)
apps/
  core/                 transverse : /healthz/, pages « à venir », tests des gabarits/sécurité
  accounts/             accounts.User, connexion par e-mail, inscription par code famille
  families/             Family, FamilyMembership, Person ; access.py (décorateurs d'accès), réglages
  tasks/                Task, TaskCompletion, périodes, accueil parent, cochage
  display/              SharedDisplayDevice, écran partagé tablette (aujourd'hui, semaine, fêtes)
  school/               SchoolDaySchedule, SchoolDayOverride (cantine, APC, étude)
  household/            HouseholdChore, ChoreCompletion, semainier
  celebrations/         Celebration, CelebrationTodo, GiftItem, RecipeIdea
templates/
  base.html             squelette HTML commun (polices, CSS, HTMX, Alpine, CSRF)
  layouts/
    parent_mobile.html  famille « parent » : mobile, nav fixe en bas
    shared_display.html famille « affichage partagé » : tablette, colonnes par enfant, nav en haut
    public.html         connexion, inscription, erreurs (sans navigation)
  parent/  shared/      pages de chaque famille de gabarits
  accounts/ components/ pages d'authentification, fragments réutilisables
assets/css/app.css      source Tailwind (non servie)
static/js/app.js        composants Alpine (Alpine.data)
static/css/, static/vendor/   générés par `npm run build` (non versionnés)
scripts/                copy-vendor.mjs, check-tokens.mjs
.claude/skills/         design-system, permissions, domain-model
```

Nouvelle app : `apps/<nom>/`, `name = "apps.<nom>"`, `label = "<nom>"`, tests dans
`apps/<nom>/tests/test_*.py`. Une app par sous-domaine (ex. `families`, `tasks`,
`planning`, `meals`), pas de grosse app fourre-tout.

## Conventions

- **Code en anglais** (modèles, variables, URLs nommées), **textes UI en français**,
  commentaires et docstrings en français.
- Python : `snake_case`, classes `PascalCase`, ruff fait foi (`uv run ruff check . && uv run ruff format .`).
- Modèles : nom singulier (`Task`), `related_name` explicite au pluriel.
- URLs : `app_name` par app, noms `app:action` (`tasks:toggle`), chemins en kebab-case.
- Gabarits : pages dans `templates/parent/` ou `templates/shared/` ; fragments HTMX
  préfixés `_` (`_task_row.html`).
- Commits : **Conventional Commits** en anglais (`feat(tasks): …`, `fix: …`, `chore: …`,
  `docs: …`, `test: …`, `ci: …`), atomiques. Le type détermine la version publiée.
- Branches : `feat/…`, `fix/…`, `chore/…` → PR vers `main`, squash merge avec un titre
  de PR conventionnel (vérifié en CI).

## Identité de marque (résumé — détail dans `.claude/skills/design-system/SKILL.md`)

- Nom **La Ruche** ; symbole : alvéole hexagonale contenant un toit simplifié.
- Couleurs (thème clair seulement) : surface-100 `#FBF6EC` (fond de page, jamais de blanc
  pur en fond), surface-0 `#FFFFFF` (cartes), ink `#241B13`, ink-soft `#5C4E3F`,
  border `#E7DCC6`, border-strong `#9C8B65`, honey `#E8A33D` (primaire, **texte ink dessus**),
  honey-dark `#B97A1E` (survol), terracotta `#B34F39` (à faire / enfants, texte blanc),
  sage `#3F6B47` (validé, texte blanc, **toujours avec une icône**).
- Typo : Fredoka 500/600 (`font-display`, titres), Inter 400/500/600 (`font-sans`).
- Rayons : `rounded-sm` 10px, `rounded-md` 16px, `rounded-lg` 28px.
- Espacements : `space-2` 8px, `space-4` 16px, `space-6` 24px, `space-8` 32px.
- La palette Tailwind par défaut est désactivée ; `npm run check:tokens` vérifie les valeurs.
- Mouvement : coche = micro-feedback ; palier d'étoiles = vraie célébration ;
  `prefers-reduced-motion` + interrupteur respectés ; jamais d'animation culpabilisante.

**Deux familles de gabarits, pas un responsive générique** : vue parent mobile (un
utilisateur, une colonne, nav en bas) vs affichage partagé enfants (tablette commune,
une colonne par enfant côte à côte, nav en haut).

## Sécurité — règles à ne jamais enfreindre

- **Secrets uniquement en variables d'environnement.** Rien de réel dans le code, les
  tests ou `.env.example`. `.env` n'est jamais commité.
- **`ALLOWED_HOSTS` strict** via `DJANGO_ALLOWED_HOSTS` : pas de défaut, `*` refusé au démarrage.
  Seul ajout automatique : l'hôte exact fourni par Render (`RENDER_EXTERNAL_HOSTNAME`).
- **Sécurisé par défaut** : sans `DJANGO_DEBUG=true`, `SECRET_KEY` et `DATABASE_URL` sont
  obligatoires, HTTPS forcé, HSTS actif.
- **Cookies** session et CSRF : `Secure` (hors DEBUG), `HttpOnly`, `SameSite=Lax`.
  Le jeton CSRF parvient à HTMX via `hx-headers` sur `<body>`, jamais via `document.cookie`.
- **CSP stricte** (django-csp) : scripts `'self'` + nonce, ni `unsafe-inline` ni
  `unsafe-eval`. Conséquences : pas de `<script>` inline sans `nonce="{{ request.csp_nonce }}"`,
  pas de `hx-on:*` (eval désactivé), pas d'attribut `style=""` inline, Alpine en build CSP
  (composants déclarés dans `static/js/app.js`), aucun script depuis un CDN.
- **Isolation des données par famille dans chaque queryset** : jamais `Model.objects.get(pk=…)`
  dans une vue ; toujours via un queryset filtré par la famille de la requête ; objet d'une
  autre famille → 404. Détail : `.claude/skills/permissions/SKILL.md`.
- Rôles vérifiés **côté serveur**, y compris pour chaque endpoint HTMX.
- `python manage.py check --deploy --fail-level WARNING` doit rester vert (CI).

## Commandes

```bash
uv sync                                   # dépendances Python
npm ci && npm run build                   # CSS + vendor JS
npm run watch:css                         # Tailwind en continu (dev)
uv run python manage.py runserver
uv run python manage.py test
uv run ruff check . && uv run ruff format --check .
npm run check:tokens                      # tokens conformes à la charte
```

## Skills du projet

- `.claude/skills/design-system/SKILL.md` — avant tout gabarit, CSS ou animation
- `.claude/skills/permissions/SKILL.md` — avant toute vue, queryset, formulaire, endpoint HTMX
- `.claude/skills/domain-model/SKILL.md` — avant tout modèle ou migration (Phase 1)
