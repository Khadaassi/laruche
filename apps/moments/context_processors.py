"""Thème de la page : saison toujours ; moments (Aïd, Ramadan, vendredi…) si une famille."""

from django.utils import timezone

from .calendar import season_of
from .selectors import moments_for


def theme(request):
    today = timezone.localdate()
    family = getattr(request, "family", None)
    if family is None:
        return {"theme_season": season_of(today), "theme_moment": ""}
    cached = getattr(request, "_moments", None)
    if cached is None or cached.day != today:
        cached = request._moments = moments_for(family, today)
    return {"theme_season": cached.season, "theme_moment": cached.theme, "moments": cached}
