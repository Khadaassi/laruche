"""
Réglages Django de La Ruche.

Un seul fichier, piloté par variables d'environnement (voir .env.example).
Principe : sécurisé par défaut. Le mode développement doit être demandé
explicitement (DJANGO_DEBUG=true) ; sans lui, tout ce qui manque est une erreur.
"""

import os
import sys
from pathlib import Path

import dj_database_url
from csp.constants import NONCE, NONE, SELF
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# .env est lu en local uniquement s'il existe ; en production les variables
# viennent de la plateforme d'hébergement. Les variables déjà définies gagnent.
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return default if value is None or value == "" else int(value)


def env_list(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def env_required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"La variable d'environnement {name} est obligatoire.")
    return value


TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"

# --- Noyau -------------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env_required("DJANGO_SECRET_KEY")

# Liste blanche stricte : aucune valeur par défaut, joker interdit.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
# Render fournit l'hôte public exact du service (xxx.onrender.com) : pas un joker.
if render_host := os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(render_host)
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS ne doit jamais contenir '*'.")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "csp",
    "django_ratelimit",
    "apps.core",
    "apps.accounts",
    "apps.families",
    "apps.tasks",
    "apps.display",
    "apps.school",
    "apps.household",
    "apps.celebrations",
    "apps.stars",
    "apps.saturday",
    "apps.meals",
    "apps.shopping",
    "apps.absences",
]

MIDDLEWARE = [
    "apps.core.middleware.LivenessMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# L'admin peut être déplacé hors de /admin/ pour réduire le bruit des scanners.
ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "admin/")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "csp.context_processors.nonce",
            ],
        },
    },
]

# --- Base de données (Neon en production) ------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    if not DEBUG:
        raise ImproperlyConfigured("DATABASE_URL est obligatoire hors mode DEBUG.")
    # Confort de développement uniquement : SQLite local si aucune URL fournie.
    DATABASE_URL = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=env_int("DATABASE_CONN_MAX_AGE", 60),
        conn_health_checks=True,
        ssl_require=env_bool("DATABASE_SSL_REQUIRE", default=not DEBUG),
    )
}
# Compatible avec le pooler PgBouncer de Neon (mode transaction).
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Cache et limitation des tentatives --------------------------------------

# Cache mémoire du processus, utilisé par django-ratelimit (apps/core/ratelimit.py).
# Suffisant car gunicorn tourne avec UN worker sur UNE instance (scripts/start.sh) :
# tous les threads partagent les mêmes compteurs, incrémentés sous verrou.
# django-ratelimit le signale comme « non partagé » (E003/W001) : avertissements
# volontairement neutralisés. Plusieurs workers/instances => passer à Redis.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
SILENCED_SYSTEM_CHECKS = ["django_ratelimit.E003", "django_ratelimit.W001"]

# --- Authentification --------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "tasks:home"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Tests uniquement : hachage rapide (les vrais hacheurs coûtent ~0,3 s par mot de passe).
if TESTING:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# --- Internationalisation ----------------------------------------------------

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# --- Fichiers statiques (WhiteNoise) -----------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or TESTING
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# --- Sécurité HTTP -----------------------------------------------------------

# Derrière un reverse proxy qui termine TLS (Render, Fly, Railway…).
if env_bool("DJANGO_BEHIND_PROXY", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=not DEBUG)
# Les sondes de santé des hébergeurs appellent souvent en HTTP interne.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]

SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 0 if DEBUG else 31_536_000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Cookies : Secure hors DEBUG, jamais lisibles en JS, SameSite=Lax.
# CSRF_COOKIE_HTTPONLY=True => HTMX récupère le jeton via le gabarit
# (hx-headers sur <body>), jamais via document.cookie.
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# Content Security Policy (django-csp 4).
# Scripts : uniquement servis par l'app ou porteurs du nonce. Pas d'unsafe-inline,
# pas d'unsafe-eval (d'où le build CSP d'Alpine et htmx.config.allowEval=false).
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        "script-src": [SELF, NONCE],
        "style-src": [SELF, "https://fonts.googleapis.com"],
        "font-src": [SELF, "https://fonts.gstatic.com"],
        "img-src": [SELF, "data:"],
        "connect-src": [SELF],
        "object-src": [NONE],
        "base-uri": [SELF],
        "form-action": [SELF],
        "frame-ancestors": [NONE],
    },
}

# --- Journalisation ----------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}
