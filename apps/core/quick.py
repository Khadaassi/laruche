"""Saisie rapide : une course, un rendez-vous ou une tâche d'enfant, depuis n'importe où.

Formulaire minimal (le détail se règle ensuite dans la page dédiée). Retour à la page
d'origine (`next`, même site uniquement) avec `?ajoute=…` pour la confirmation.
"""

import datetime

from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.agenda.models import Event
from apps.families.access import parent_required
from apps.families.models import Person
from apps.shopping.models import ShoppingItem
from apps.tasks.models import ALL_WEEKDAYS, Task
from apps.tasks.periods import current_period

KINDS = {"course", "rdv", "tache"}


def _back(request, kind):
    target = request.POST.get("next") or "/"
    if not url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        target = "/"
    target = target.split("#")[0]
    separator = "&" if "?" in target else "?"
    return redirect(f"{target}{separator}ajoute={kind}")


@require_POST
@parent_required
def quick_add(request):
    kind = request.POST.get("kind")
    title = (request.POST.get("title") or "").strip()
    if kind not in KINDS or not title:
        return HttpResponseBadRequest("Saisie incomplète.")
    today = timezone.localdate()
    if kind == "course":
        ShoppingItem.objects.create(family=request.family, name=title[:80])
    elif kind == "rdv":
        try:
            day = datetime.date.fromisoformat(request.POST.get("date") or today.isoformat())
            start = datetime.time.fromisoformat(request.POST.get("time") or "")
        except ValueError:
            return HttpResponseBadRequest("Date ou heure invalide.")
        end = (datetime.datetime.combine(day, start) + datetime.timedelta(hours=1)).time()
        if end <= start:  # rendez-vous tard le soir : jusqu'à 23 h 59
            end = datetime.time(23, 59)
        event = Event.objects.create(
            family=request.family,
            title=title[:80],
            start_time=start,
            end_time=end,
            weekdays=ALL_WEEKDAYS,
            start_date=day,
            end_date=day,
        )
        person_pk = request.POST.get("person")
        if person_pk:
            event.people.set(
                [get_object_or_404(Person.objects.for_family(request.family), pk=person_pk)]
            )
    else:
        child = get_object_or_404(
            Person.objects.for_family(request.family).children(), pk=request.POST.get("person")
        )
        # Tâche ponctuelle : aujourd'hui seulement, période en cours.
        Task.objects.create(
            person=child,
            title=title[:120],
            period=current_period(),
            weekdays=ALL_WEEKDAYS,
            start_date=today,
            end_date=today,
        )
    return _back(request, kind)
