"""Ce que la revue du dimanche passe en revue (aucune écriture ici)."""

import datetime

from apps.celebrations.models import Celebration
from apps.holidays.models import SchoolHoliday
from apps.household.models import monday_of
from apps.household.week import build_week
from apps.meals.models import Recipe
from apps.meals.suggest import empty_slots

from .models import WeeklyReview

REVIEW_FROM_WEEKDAY = 4  # à partir du vendredi, on prépare la semaine suivante


def review_monday(today: datetime.date) -> datetime.date:
    """Semaine à préparer : la suivante dès le vendredi, sinon la semaine en cours."""
    monday = monday_of(today)
    if today.weekday() >= REVIEW_FROM_WEEKDAY:
        monday += datetime.timedelta(days=7)
    return monday


def is_done(family, monday: datetime.date) -> bool:
    return WeeklyReview.objects.filter(family=family, week=monday).exists()


def review_context(family, monday: datetime.date) -> dict:
    week = build_week(family, monday, None)
    sunday = monday + datetime.timedelta(days=6)
    days = week["days"]
    return {
        "monday": monday,
        "sunday": sunday,
        "days_with_events": [d for d in days if d.blocks],
        "absences": sorted(
            {a.pk: a for d in days for a in d.absences}.values(), key=lambda a: a.start_date
        ),
        "holidays": SchoolHoliday.objects.for_family(family).filter(
            start_date__lte=sunday, end_date__gte=monday
        ),
        "celebrations": list(
            Celebration.objects.filter(family=family)
            .filter(date__gte=monday, date__lte=sunday + datetime.timedelta(days=7))
            .order_by("date")[:5]
        ),
        "empty_meals": len(empty_slots(family, monday)),
        "has_recipes": Recipe.objects.for_family(family).exists(),
        "done": is_done(family, monday),
    }
