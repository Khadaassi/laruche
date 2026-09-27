# La Ruche

Organisation familiale : semainier, tâches des enfants, menu de la semaine.
Deux usages : une **vue parent** sur mobile, et un **affichage partagé** sur une
tablette commune où les enfants voient leurs tâches côte à côte.

> Phase 0 : fondations uniquement (config, sécurité, CI, charte). Aucune fonctionnalité métier.

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

## Déployer

N'importe quel PaaS Python (Render, Fly.io, Railway…) + Neon :

1. **Base** : projet Neon, base `laruche`, récupérer l'URL de connexion *pooled* (`?sslmode=require`).
2. **Variables d'environnement** sur l'hébergeur (voir `.env.example`) :
   `DJANGO_SECRET_KEY` (nouvelle, jamais celle de dev), `DJANGO_ALLOWED_HOSTS=ton-domaine`,
   `DJANGO_CSRF_TRUSTED_ORIGINS=https://ton-domaine`, `DATABASE_URL`, et
   `DJANGO_BEHIND_PROXY=true` si l'hébergeur termine TLS (cas de Render/Fly/Railway).
   Ne pas définir `DJANGO_DEBUG`.
3. **Build** :
   ```bash
   pip install uv && uv sync --locked --no-dev
   npm ci && npm run build
   uv run python manage.py collectstatic --noinput
   ```
4. **Release** (avant chaque démarrage de version) : `uv run python manage.py migrate --noinput`
5. **Démarrage** : `uv run gunicorn config.wsgi --bind 0.0.0.0:$PORT`
6. **Sonde de santé** : `/healthz/` (exemptée de la redirection HTTPS).

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
