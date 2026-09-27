"""Rendez-vous : gestion réservée aux parents, scopée par famille.

Les enfants les voient en lecture seule dans la grille du semainier de
l'écran partagé.
"""

import datetime

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.families.access import parent_required
from apps.household.models import monday_of
from apps.household.views import WEEK_PARAM

from .forms import EventForm
from .models import Event

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
