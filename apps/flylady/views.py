"""Ménage FlyLady : page du jour (parents) et réglages du contenu."""

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.families.access import parent_required

from .models import FlyMission, FlyRoutineItem, FlyZone, RoutineKind
from .selectors import fly_day, valid_keys
from .services import ensure_defaults, set_checked

FIFTEEN_MINUTES = 15 * 60


@require_GET
@parent_required
def today(request):
    ensure_defaults(request.family)
    plan = fly_day(request.family, timezone.localdate())
    return render(
        request,
        "parent/flylady.html",
        {"nav_active": "week", "plan": plan, "timer_seconds": FIFTEEN_MINUTES},
    )


@require_POST
@parent_required
def toggle(request):
    """Coche / décoche un élément du programme du jour (endpoint HTMX, réponse 204).

    Seules les clés du programme d'aujourd'hui de la famille sont acceptées (404
    sinon) : pas de coche sur une routine d'une autre famille ni sur un autre jour.
    """
    key = request.POST.get("key", "")
    keys = valid_keys(request.family, timezone.localdate())
    if key not in keys:
        raise Http404
    set_checked(request.family, keys[key], key, request.POST.get("done") == "on")
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(status=204)
    return redirect("flylady:today")


@require_http_methods(["GET", "POST"])
@parent_required
def manage(request):
    """Réglages : étapes des routines, noms des zones, missions de 15 minutes."""
    family = request.family
    ensure_defaults(family)
    if request.method == "POST":
        action = request.POST.get("action")
        title = request.POST.get("title", "").strip()[:120]
        if action == "add_item" and title and request.POST.get("kind") in RoutineKind.values:
            kind = request.POST["kind"]
            last = FlyRoutineItem.objects.for_family(family).filter(kind=kind).count()
            FlyRoutineItem.objects.create(family=family, kind=kind, title=title, position=last)
        elif action == "delete_item":
            get_object_or_404(
                FlyRoutineItem.objects.for_family(family), pk=request.POST.get("pk")
            ).delete()
        elif action == "rename_zone" and title:
            zone = get_object_or_404(FlyZone.objects.for_family(family), pk=request.POST.get("pk"))
            zone.name = title[:60]
            zone.save(update_fields=["name"])
        elif action == "add_mission" and title:
            zone = get_object_or_404(FlyZone.objects.for_family(family), pk=request.POST.get("pk"))
            FlyMission.objects.create(zone=zone, title=title, position=zone.missions.count())
        elif action == "delete_mission":
            get_object_or_404(
                FlyMission.objects.filter(zone__family=family), pk=request.POST.get("pk")
            ).delete()
        return redirect("flylady:manage")
    items = FlyRoutineItem.objects.for_family(family)
    return render(
        request,
        "parent/flylady_manage.html",
        {
            "nav_active": "settings",
            "routines": [
                (kind, label, [i for i in items if i.kind == kind])
                for kind, label in RoutineKind.choices
            ],
            "zones": FlyZone.objects.for_family(family).prefetch_related("missions"),
        },
    )
