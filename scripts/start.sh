#!/bin/sh
# Démarrage du conteneur de production : migrations, puis gunicorn.
# Les migrations tournent ici car l'offre gratuite de Render n'a pas de
# « pre-deploy command » ; une seule instance, donc pas de course.
set -e

python manage.py migrate --noinput

# gunicorn écoute sur $PORT (fourni par l'hébergeur). Un worker, plusieurs
# threads : léger en mémoire (512 Mo sur l'offre gratuite).
# UN SEUL worker obligatoire tant que le rate-limit utilise le cache mémoire
# (config/settings.py, CACHES) : sinon chaque worker aurait ses compteurs.
exec gunicorn config.wsgi:application --workers 1 --threads 8 --timeout 30 --no-control-socket
