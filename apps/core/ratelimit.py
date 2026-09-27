"""Limitation des tentatives (django-ratelimit), comptées sur les ÉCHECS seulement.

Une réussite ne consomme rien : un parent qui se connecte normalement n'est
jamais bloqué. Chaque garde combine plusieurs clés, et il suffit qu'une seule
soit saturée pour bloquer :
- l'IP du client (voir `client_ip`, falsifiable derrière un proxy) ;
- une clé qui ne dépend pas de l'IP (compte visé, appareil, ou global), pour
  que changer d'IP ne suffise pas à contourner la limite.

Cache : LocMemCache du processus. Correct tant que gunicorn tourne avec UN
seul worker sur UNE seule instance (scripts/start.sh, offre gratuite Render) ;
les compteurs repartent à zéro au redémarrage. Avec plusieurs workers ou
instances, passer à un cache partagé (Redis / Key Value).
"""

import hashlib
from dataclasses import dataclass

from django.conf import settings
from django_ratelimit.core import get_usage


def client_ip(group, request) -> str:
    """IP du client. Derrière le proxy de Render, première entrée de X-Forwarded-For."""
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.META.get("REMOTE_ADDR", "")


def _digest(value: str) -> str:
    # Pas d'e-mail ni de jeton en clair dans les clés de cache.
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


@dataclass(frozen=True)
class Guard:
    """Un ensemble de limites pour une action sensible."""

    group: str
    rates: dict  # nom de clé → débit (« 10/15m »)

    def _keys(self, request, target: str):
        keys = {"ip": client_ip, "global": lambda g, r: "global"}
        if target:
            keys["target"] = lambda g, r: _digest(target)
        return [(keys[name], rate) for name, rate in self.rates.items() if name in keys]

    def is_blocked(self, request, target: str = "") -> bool:
        for key, rate in self._keys(request, target):
            usage = get_usage(request, group=self.group, key=key, rate=rate)
            if usage is not None and usage["count"] >= usage["limit"]:
                return True
        return False

    def record_failure(self, request, target: str = "") -> None:
        for key, rate in self._keys(request, target):
            get_usage(request, group=self.group, key=key, rate=rate, increment=True)


# Connexion : par IP, et par compte visé (e-mail) quel que soit l'IP.
LOGIN = Guard("login", {"ip": "20/15m", "target": "10/15m"})

# Rejoindre une famille : codes invalides par IP, et plafond global qui borne
# le nombre total d'essais même en changeant d'IP (espace de 31^10 codes).
JOIN_FAMILY = Guard("join-family", {"ip": "10/h", "global": "100/h"})

# Sortie du mode tablette : par appareil (jeton) et par IP.
EXIT_DISPLAY = Guard("exit-display", {"ip": "10/15m", "target": "5/15m"})

BLOCKED_MESSAGE = "Trop de tentatives. Réessayez dans quelques minutes."
