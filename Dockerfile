# syntax=docker/dockerfile:1

# Image de production de La Ruche (Google Cloud Run).
# Deux étapes : Node construit le CSS et copie le JS vendor, puis l'image
# Python finale ne contient que l'app, ses dépendances et les statiques.

# --- Étape 1 : front (Tailwind + vendor JS) ----------------------------------
FROM node:22-slim AS front
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
# Tailwind scanne les gabarits, le Python et le JS pour ne garder que les classes utilisées.
COPY tailwind.config.js ./
COPY scripts/ scripts/
COPY assets/ assets/
COPY templates/ templates/
COPY apps/ apps/
COPY static/ static/
RUN npm run build

# --- Étape 2 : app Django ----------------------------------------------------
FROM python:3.13-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Dépendances d'abord : cette couche reste en cache tant que uv.lock ne change pas.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
COPY --from=front /app/static/ static/

# collectstatic n'ouvre pas la base : valeurs factices, propres à la construction.
RUN DJANGO_SECRET_KEY=collectstatic-only \
    DJANGO_ALLOWED_HOSTS=build.invalid \
    DATABASE_URL=sqlite:////tmp/unused.sqlite3 \
    python manage.py collectstatic --noinput

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER app

# gunicorn écoute sur $PORT (fourni par Cloud Run). Un seul worker, plusieurs
# threads : recommandé par Cloud Run, et léger en mémoire.
CMD ["gunicorn", "config.wsgi:application", "--workers", "1", "--threads", "8", "--timeout", "0"]
