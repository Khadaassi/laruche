#!/bin/sh
# Démarrage du conteneur de production : migrations, puis gunicorn.
# Les migrations tournent ici car l'offre gratuite de Render n'a pas de
# « pre-deploy command » ; une seule instance, donc pas de course.
set -e

python manage.py migrate --noinput

# gunicorn écoute sur $PORT (fourni par l'hébergeur). Un worker, plusieurs
# threads : léger en mémoire (512 Mo sur l'offre gratuite).
exec gunicorn config.wsgi:application --workers 1 --threads 8 --timeout 30 --no-control-socket
