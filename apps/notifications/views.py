"""Réglages des notifications (parents), abonnement d'un appareil, déclencheur planifié."""

import hmac
import json

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.maintenance import run_daily
from apps.families.access import parent_required

from .keys import public_key_b64
from .models import NotificationPrefs, PushSubscription
from .services import prefs_for, run_scheduled, send_to_user

PREF_FIELDS = ("dinner", "review", "day_done")


@require_http_methods(["GET", "POST"])
@parent_required
def manage(request):
    prefs = prefs_for(request.user)
    if request.method == "POST":
        prefs, _ = NotificationPrefs.objects.get_or_create(user=request.user)
        for name in PREF_FIELDS:
            setattr(prefs, name, request.POST.get(name) == "on")
        prefs.save()
        return redirect("notifications:manage")
    return render(
        request,
        "parent/notifications.html",
        {
            "nav_active": "settings",
            "prefs": [
                (name, NotificationPrefs._meta.get_field(name).verbose_name, getattr(prefs, name))
                for name in PREF_FIELDS
            ],
            "public_key": public_key_b64(),
            "devices": PushSubscription.objects.filter(user=request.user).count(),
        },
    )


def _json(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return None


@require_POST
@parent_required
def subscribe(request):
    """Enregistre l'abonnement push de cet appareil (JSON du navigateur)."""
    data = _json(request)
    keys = (data or {}).get("keys") or {}
    endpoint = (data or {}).get("endpoint", "")
    if not endpoint.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        return HttpResponseBadRequest("Abonnement invalide.")
    PushSubscription.objects.update_or_create(
        endpoint=endpoint[:1000],
        defaults={"user": request.user, "p256dh": keys["p256dh"][:200], "auth": keys["auth"][:100]},
    )
    return HttpResponse(status=204)


@require_POST
@parent_required
def unsubscribe(request):
    data = _json(request) or {}
    PushSubscription.objects.filter(user=request.user, endpoint=data.get("endpoint", "")).delete()
    return HttpResponse(status=204)


@require_POST
@parent_required
def test(request):
    delivered = send_to_user(
        request.user,
        title="La Ruche",
        body="Les notifications fonctionnent sur cet appareil.",
        url="/reglages/notifications/",
        tag="test",
    )
    return JsonResponse({"delivered": delivered})


@csrf_exempt
@require_POST
def cron(request):
    """Tâche planifiée GitHub (jeton `CRON_TOKEN`) : maintenance quotidienne + rappels.

    Sans jeton configuré : la route n'existe pas (404). Mauvais jeton : 404 aussi.
    Tout est idempotent : plusieurs appels par jour ne font rien de plus.
    """
    expected = getattr(settings, "CRON_TOKEN", "")
    given = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
        raise Http404
    maintenance = run_daily(timezone.localdate())
    return JsonResponse({**run_scheduled(), "maintenance": maintenance})
