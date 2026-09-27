from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.families.access import parent_required


@require_GET
@never_cache
def healthz(request):
    """Sonde de santé pour l'hébergeur : l'app répond et la base est joignable."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


# Sections de la nav parent pas encore construites : page « à venir ».
COMING_SOON = {
    "week": ("Semaine", "Le semainier de la famille arrive bientôt."),
    "menu": ("Menu", "Le menu de la semaine arrive bientôt."),
    "shopping": ("Courses", "La liste de courses partagée arrive bientôt."),
}


@require_GET
@parent_required
def coming_soon(request, section):
    if section not in COMING_SOON:
        raise Http404
    title, message = COMING_SOON[section]
    return render(
        request,
        "parent/coming_soon.html",
        {"nav_active": section, "title": title, "message": message},
    )
