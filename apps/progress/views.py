"""Page « Progrès » (parents) : suivi mois par mois et semaine après semaine."""

import datetime

from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.families.access import parent_required
from apps.families.models import Person

from .selectors import progress_for

MONTH_PARAM = "mois"


def requested_month(raw, today: datetime.date) -> datetime.date:
    """?mois=AAAA-MM → 1er du mois ; mois courant par défaut ; pas de futur."""
    if not raw:
        return today.replace(day=1)
    try:
        month = datetime.date.fromisoformat(f"{raw}-01")
    except ValueError as error:
        raise Http404 from error
    if month > today:
        raise Http404
    return month


@require_GET
@parent_required
def overview(request):
    today = timezone.localdate()
    month = requested_month(request.GET.get(MONTH_PARAM), today)
    previous = (month - datetime.timedelta(days=1)).replace(day=1)
    following = (month + datetime.timedelta(days=32)).replace(day=1)
    children = list(Person.objects.for_family(request.family).children())
    return render(
        request,
        "parent/progress.html",
        {
            "nav_active": "home",
            "month": month,
            "previous_month": previous,
            "next_month": following if following <= today else None,
            "children": progress_for(request.family, children, month, today),
            "weekday_initials": ["L", "M", "M", "J", "V", "S", "D"],
            "today": today,
        },
    )
