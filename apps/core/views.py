from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def healthz(request):
    """Sonde de santé pour l'hébergeur : l'app répond et la base est joignable."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


# --- Appli installable (PWA) -------------------------------------------------

from django.shortcuts import render  # noqa: E402
from django.templatetags.static import static  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.views.decorators.cache import cache_control  # noqa: E402


@require_GET
@cache_control(max_age=3600)
def manifest(request):
    """Manifeste : nom, icônes, couleurs ; s'ouvre en plein écran sur l'accueil."""
    icons = [
        {"src": static("icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
        {"src": static("icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
        {
            "src": static("icons/maskable-512.png"),
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "maskable",
        },
    ]
    data = {
        "name": "La Ruche",
        "short_name": "La Ruche",
        "description": "L'organisation de la famille : tâches, menu, semaine, étoiles.",
        "lang": "fr",
        "start_url": "/?source=app",
        "scope": "/",
        "display": "standalone",
        "background_color": "#FBF6EC",
        "theme_color": "#FBF6EC",
        "icons": icons,
    }
    return JsonResponse(data, content_type="application/manifest+json")


@require_GET
@never_cache
def service_worker(request):
    """Service worker servi à la racine (portée « / »). Toujours revalidé."""
    response = render(
        request,
        "core/sw.js",
        {
            "offline_url": "/hors-ligne/",
            "app_css": static("css/app.css"),
            "store_url": reverse("shopping:store"),
            "login_url": reverse("accounts:login"),
        },
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
@cache_control(max_age=3600)
def offline(request):
    """Page affichée par le service worker quand le réseau manque."""
    return render(request, "core/offline.html")
