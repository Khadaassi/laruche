"""Revue du dimanche (parents) : une page guidée, étape par étape."""

import datetime

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_GET, require_POST

from apps.families.access import parent_required
from apps.household.models import monday_of

from .models import WeeklyReview
from .selectors import review_context, review_monday

WEEK_PARAM = "semaine"


def requested_review_monday(request) -> datetime.date:
    raw = request.GET.get(WEEK_PARAM) or request.POST.get(WEEK_PARAM)
    if not raw:
        return review_monday(timezone.localdate())
    try:
        return monday_of(datetime.date.fromisoformat(raw))
    except ValueError as error:
        raise Http404 from error


@require_GET
@parent_required
def week(request):
    monday = requested_review_monday(request)
    return render(
        request,
        "parent/review.html",
        {
            "nav_active": "week",
            "monday_label": date_format(monday, "j F"),
            **review_context(request.family, monday),
        },
    )


@require_POST
@parent_required
def done(request):
    monday = requested_review_monday(request)
    WeeklyReview.objects.get_or_create(family=request.family, week=monday)
    return redirect(f"{reverse('review:week')}?{WEEK_PARAM}={monday.isoformat()}")
