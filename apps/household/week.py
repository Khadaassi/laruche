"""Assemblage du semainier : ménage, école et fêtes, jour par jour.

Partagé par la vue parent (mobile) et l'écran partagé (lecture seule).
"""

import datetime
from dataclasses import dataclass, field

from django.utils import timezone

from apps.celebrations.models import Celebration
from apps.families.models import Person
from apps.school.selectors import school_days_range

from .selectors import chores_by_day


@dataclass
class DayPlan:
    date: datetime.date
    is_today: bool
    chores: list = field(default_factory=list)
    school: list = field(default_factory=list)  # [(enfant, SchoolDay)]
    celebrations: list = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.chores or self.school or self.celebrations)


def build_week(family, monday: datetime.date) -> dict:
    today = timezone.localdate()
    children = list(Person.objects.for_family(family).children())
    chores = chores_by_day(family, monday, 7)
    school = school_days_range(family, monday, 7, people=children)
    celebrations = {}
    for celebration in Celebration.objects.for_family(family).filter(
        date__gte=monday, date__lt=monday + datetime.timedelta(days=7)
    ):
        celebrations.setdefault(celebration.date, []).append(celebration)

    days = []
    for offset in range(7):
        day = monday + datetime.timedelta(days=offset)
        days.append(
            DayPlan(
                date=day,
                is_today=day == today,
                chores=chores[day],
                school=[(c, school[day][c.pk]) for c in children if c.pk in school[day]],
                celebrations=celebrations.get(day, []),
            )
        )
    return {
        "monday": monday,
        "sunday": monday + datetime.timedelta(days=6),
        "days": days,
        "previous_monday": monday - datetime.timedelta(days=7),
        "next_monday": monday + datetime.timedelta(days=7),
        "is_current_week": monday <= today < monday + datetime.timedelta(days=7),
    }
