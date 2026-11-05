"""Rendez-vous : gestion réservée aux parents, scopée par famille.

Les enfants les voient en lecture seule dans la grille du semainier de
l'écran partagé.
"""

import datetime

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.families.access import parent_required
from apps.household.models import monday_of
from apps.household.views import WEEK_PARAM

from .forms import EventForm
from .models import Event, EventOccurrence, EventPrep, EventPrepCheck

DAY_PARAM = "jour"


def _week_url(day: datetime.date | None) -> str:
    url = reverse("household:week")
    if day is None:
        return url
    return f"{url}?{WEEK_PARAM}={monday_of(day).isoformat()}&{DAY_PARAM}={day.isoformat()}"


def _day(request):
    try:
        return datetime.date.fromisoformat(request.GET.get(DAY_PARAM, ""))
    except ValueError:
        return None


def _form_page(request, form, event=None, status=200):
    return render(
        request,
        "parent/event_form.html",
        {"nav_active": "week", "form": form, "event": event, "back_url": _week_url(_day(request))},
        status=status,
    )


@require_http_methods(["GET", "POST"])
@parent_required
def add(request):
    form = EventForm(request.POST or None, family=request.family, day=_day(request))
    if request.method == "POST" and form.is_valid():
        event = form.save()
        return redirect(_week_url(event.start_date or _day(request)))
    return _form_page(request, form, status=400 if form.is_bound else 200)


@require_http_methods(["GET", "POST"])
@parent_required
def edit(request, pk):
    event = get_object_or_404(Event.objects.for_family(request.family), pk=pk)
    form = EventForm(request.POST or None, instance=event, family=request.family)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        return redirect(_week_url(_day(request) or event.start_date))
    return _form_page(request, form, event, status=400 if form.is_bound else 200)


@require_POST
@parent_required
def delete(request, pk):
    """Supprime le rendez-vous (toute la série s'il se répète)."""
    get_object_or_404(Event.objects.for_family(request.family), pk=pk).delete()
    return redirect(_week_url(_day(request)))


# --- Préparatifs et accompagnement (accueil parent) ---------------------------

PREP_WINDOW = 7  # on peut cocher / prendre en charge jusqu'à 7 jours avant ou après


def _occurrence_date(request, event) -> datetime.date:
    """Date postée, valide pour ce rendez-vous et proche d'aujourd'hui (404 sinon)."""
    try:
        day = datetime.date.fromisoformat(request.POST.get("date", ""))
    except ValueError as error:
        raise Http404 from error
    today = timezone.localdate()
    if abs((day - today).days) > PREP_WINDOW or not event.occurs_on(day):
        raise Http404
    return day


@require_POST
@parent_required
def prep_toggle(request, pk):
    """Coche / décoche un préparatif pour une date (cochage optimiste, réponse 204)."""
    prep = get_object_or_404(EventPrep.objects.filter(event__family=request.family), pk=pk)
    day = _occurrence_date(request, prep.event)
    if request.POST.get("done") == "on":
        EventPrepCheck.objects.get_or_create(prep=prep, date=day)
    else:
        EventPrepCheck.objects.filter(prep=prep, date=day).delete()
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(status=204)
    return redirect("tasks:home")


@require_POST
@parent_required
def take_over(request, pk):
    """« Je m'en occupe » : le parent connecté accompagne ce jour-là."""
    event = get_object_or_404(Event.objects.for_family(request.family), pk=pk)
    day = _occurrence_date(request, event)
    me = getattr(request.user, "person", None)
    if me is None or me.family_id != request.family.pk:
        raise Http404
    EventOccurrence.objects.update_or_create(event=event, date=day, defaults={"driver": me})
    return redirect("tasks:home")
