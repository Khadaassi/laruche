# La Ruche

Organisation familiale : semainier, tâches des enfants, menu de la semaine.
Deux usages : une **vue parent** sur mobile, et un **affichage partagé** sur une
tablette commune où les enfants voient leurs tâches côte à côte.

> Phase 1 : familles et inscription par code, tâches du jour, accueil parent (mobile)
> et affichage partagé (tablette). Semaine, menu et courses sont encore « à venir ».

## Premiers pas

1. `/inscription/` avec un **nouveau code** (8 caractères minimum) et un nom de famille :
   la famille est créée et vous en êtes le premier parent.
2. Les autres membres s'inscrivent avec **le même code** : ils arrivent en « enfant » ;
   un parent peut les passer en parent depuis **Réglages**.
3. **Réglages** : ajouter des enfants sans compte, puis **Gérer les tâches du quotidien**.
4. Sur la tablette commune : se connecter en parent, **Réglages → Affichage partagé →
   Activer sur cet appareil**. Pour en sortir : bouton « Mode parent » + mot de passe.

## Stack

| | |
|---|---|
| Backend | Python 3.13, Django 5.2 LTS, gunicorn, WhiteNoise |
| Base de données | PostgreSQL sur [Neon](https://neon.tech) (`dj-database-url`) |
| Front | Tailwind CSS 3, HTMX 2, Alpine.js 3 (build CSP) |
| Sécurité | django-csp (CSP stricte), cookies Secure/HttpOnly/SameSite, HSTS |
| Outillage | uv, ruff, GitHub Actions, semantic-release |

## Charte de marque

Fond crème `#FBF6EC`, encre brune `#241B13`, miel `#E8A33D` pour la marque (toujours texte encre dessus), terracotta `#B34F39` pour « à faire », sauge `#3F6B47` + icône pour « fait ».
Titres en Fredoka, texte en Inter ; formes arrondies (10 / 16 / 28 px) et motif hexagonal (l'alvéole).
Tout le détail — tokens, contrastes, règles d'animation : [`.claude/skills/design-system/SKILL.md`](.claude/skills/design-system/SKILL.md).

## Lancer en local

Prérequis : [uv](https://docs.astral.sh/uv/), Node.js ≥ 22.

```bash
git clone git@github.com:Khadaassi/laruche.git && cd laruche
uv sync                       # installe Python 3.13 et les dépendances
npm ci && npm run build       # compile Tailwind, copie HTMX/Alpine dans static/vendor
cp .env.example .env          # puis renseigner DJANGO_SECRET_KEY (commande dans le fichier)
uv run python manage.py migrate
uv run python manage.py runserver
```

- Sans `DATABASE_URL` et avec `DJANGO_DEBUG=true`, une base SQLite locale est utilisée.
  Pour travailler sur Postgres, créer une **branche Neon de dev** et coller son URL pooled.
- `npm run watch:css` recompile Tailwind en continu pendant le développement.
- http://127.0.0.1:8000/healthz/ doit répondre `{"status": "ok"}`.

### Vérifications (identiques à la CI)

```bash
uv run ruff check . && uv run ruff format --check .
npm run check:tokens
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py test
```

## Déployer (Render + Neon)

La production tourne sur **Render** (offre gratuite, Docker, Francfort) et la base
sur **Neon** (branche principale). Tout est décrit dans `render.yaml` :

- image construite depuis le `Dockerfile` ; au démarrage, `scripts/start.sh`
  applique les migrations puis lance gunicorn ;
- déploiement automatique à chaque merge sur `main`, **uniquement si la CI est verte** ;
- `DJANGO_SECRET_KEY` générée par Render, `DATABASE_URL` saisie à la création ;
- `ALLOWED_HOSTS` reçoit automatiquement l'hôte `xxx.onrender.com` fourni par Render
  (`RENDER_EXTERNAL_HOSTNAME`). Pour un domaine perso, ajouter `DJANGO_ALLOWED_HOSTS`.

**Deux sondes :**

| Chemin | Base de données | Usage |
|---|---|---|
| `/livez/` | non | Render (toutes les quelques secondes) et UptimeRobot |
| `/healthz/` | oui (`SELECT 1`) | vérification manuelle après un déploiement |

Ne jamais faire pointer une sonde fréquente vers `/healthz/` : Neon ne s'endormirait
plus et épuiserait son quota gratuit (100 h de calcul par mois).

### Installation (une seule fois)

1. **Neon** : dans le projet, branche principale, base `laruche`, copier l'URL
   *pooled* (`-pooler` dans l'hôte, `?sslmode=require`). C'est l'URL **de production**,
   différente de celle de `.env`.
2. **Render** : [dashboard.render.com](https://dashboard.render.com) → connexion avec
   GitHub → **New** → **Blueprint** → dépôt `laruche` → coller l'URL Neon dans
   `DATABASE_URL` → **Apply**.
3. **Anti-veille** : [uptimerobot.com](https://uptimerobot.com) → *New monitor* → HTTP(s),
   URL `https://<service>.onrender.com/livez/`, intervalle 5 minutes. Sans lui, l'offre
   gratuite de Render met l'app en veille après 15 minutes sans visite.

## Workflow Git

- `main` est protégée : tout passe par une PR, CI verte obligatoire.
- Commits et titres de PR en [Conventional Commits](https://www.conventionalcommits.org/) ;
  squash merge.
- À chaque merge sur `main`, semantic-release calcule la version, crée le tag et publie
  la [GitHub Release](../../releases) avec le changelog.

## Documentation projet

- [`CLAUDE.md`](CLAUDE.md) — conventions, structure, règles de sécurité
- [`.claude/skills/design-system/`](.claude/skills/design-system/SKILL.md) — charte visuelle
- [`.claude/skills/permissions/`](.claude/skills/permissions/SKILL.md) — rôles, isolation par famille, affichage partagé
