"""Réglages des moments : dates islamiques, Ramadan allégé, anniversaires."""

import datetime

from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.families.access import parent_required
from apps.families.models import Person

from . import calendar as cal
from .forms import MomentSettingsForm
from .models import PersonBirthday
from .selectors import settings_for


def _parse_birthdays(post, people, today):
    """{person: date ou None} depuis les champs `naissance-<id>` ; erreurs en français."""
    values, errors = {}, {}
    for person in people:
        raw = (post.get(f"naissance-{person.pk}") or "").strip()
        if not raw:
            values[person] = None
            continue
        try:
            date = datetime.date.fromisoformat(raw)
        except ValueError:
            errors[person.pk] = "Date invalide."
            continue
        if date > today:
            errors[person.pk] = "La date ne peut pas être dans le futur."
            continue
        values[person] = date
    return values, errors


@require_http_methods(["GET", "POST"])
@parent_required
def manage(request):
    family = request.family
    today = timezone.localdate()
    settings = settings_for(family)
    people = list(Person.objects.for_family(family))
    form = MomentSettingsForm(request.POST or None, instance=settings)
    birthdays = {
        b.person_id: b.birth_date for b in PersonBirthday.objects.filter(person__in=people)
    }
    errors = {}
    if request.method == "POST":
        values, errors = _parse_birthdays(request.POST, people, today)
        if form.is_valid() and not errors:
            form.save()
            for person, date in values.items():
                if date is None:
                    PersonBirthday.objects.filter(person=person).delete()
                else:
                    PersonBirthday.objects.update_or_create(
                        person=person, defaults={"birth_date": date}
                    )
            return redirect("moments:manage")
    shift = settings.hijri_shift
    upcoming_ramadan = next((r for r in cal.ramadans_around(today, shift) if r.end >= today), None)
    return render(
        request,
        "parent/moments_manage.html",
        {
            "nav_active": "settings",
            "form": form,
            "people": [
                (
                    p,
                    request.POST.get(f"naissance-{p.pk}") if errors else birthdays.get(p.pk),
                    errors.get(p.pk),
                )
                for p in people
            ],
            "ramadan": upcoming_ramadan,
            "eids": [e for e in cal.eids_around(today, shift) if e.date >= today][:2],
        },
        status=400 if (form.is_bound and form.errors) or errors else 200,
    )
