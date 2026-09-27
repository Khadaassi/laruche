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

## Déployer (Google Cloud Run + Neon)

La production tourne sur **Cloud Run** (0 à 1 instance, redémarrage en quelques
secondes après une période sans visite) et la base sur **Neon** (branche principale).
Chaque merge sur `main` déclenche `.github/workflows/deploy.yml` :

1. construction de l'image (`Dockerfile`) et envoi dans Artifact Registry ;
2. migrations via le job Cloud Run `laruche-migrate` ;
3. déploiement du service `laruche`, puis appel de `/healthz/`.

Les secrets (`DJANGO_SECRET_KEY`, `DATABASE_URL`) vivent dans **Secret Manager**.
GitHub s'authentifie auprès de Google par **Workload Identity Federation** (limitée
à `main`) : aucune clé de compte de service n'existe.

### Installation (une seule fois)

1. Créer un projet sur [console.cloud.google.com](https://console.cloud.google.com)
   et lui lier un compte de facturation (carte demandée, l'usage reste dans l'offre gratuite).
2. **Budget** : Facturation → Budgets et alertes → budget de 1 € sur ce projet, alertes
   à 50 % et 100 %.
3. Depuis le dépôt, avec `gcloud` et `gh` connectés au bon compte :
   ```bash
   gcloud auth login
   scripts/gcp-setup.sh <PROJECT_ID>            # région par défaut : europe-west1
   ```
   Le script demande l'URL Neon **de production** (saisie masquée), génère la
   `SECRET_KEY`, et renseigne les variables GitHub (`GCP_*`, `DJANGO_ALLOWED_HOSTS`).
4. Premier déploiement : `gh workflow run deploy.yml`, ou merger une PR.

L'app est alors servie sur `https://laruche-<numéro-de-projet>.europe-west1.run.app/`.

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
