"""Journée d'école effective : exception datée si elle existe, sinon semaine type."""

import datetime
from dataclasses import dataclass

from .models import Lunch, SchoolDayOverride, SchoolDaySchedule


@dataclass(frozen=True)
class SchoolDay:
    lunch: str
    lunch_note: str
    study: bool
    is_override: bool

    @property
    def has_school(self) -> bool:
        return self.lunch != Lunch.NONE

    @property
    def lunch_label(self) -> str:
        if self.lunch == Lunch.OTHER and self.lunch_note:
            return self.lunch_note
        return Lunch(self.lunch).label

    @property
    def needs_packed_lunch(self) -> bool:
        return self.lunch == Lunch.PACKED


def _from(row, is_override) -> SchoolDay:
    return SchoolDay(row.lunch, row.lunch_note, row.study, is_override)


def school_days_range(family, start: datetime.date, days: int, people=None) -> dict:
    """{date: {person_id: SchoolDay}} sur [start, start + days[, en deux requêtes.

    Un enfant absent du dictionnaire d'un jour n'a ni semaine type ni
    exception ce jour-là (rien à afficher).
    """
    end = start + datetime.timedelta(days=days)
    weekly = SchoolDaySchedule.objects.for_family(family)
    overrides = SchoolDayOverride.objects.for_family(family).filter(date__gte=start, date__lt=end)
    if people is not None:
        weekly = weekly.filter(person__in=people)
        overrides = overrides.filter(person__in=people)
    by_weekday = {}
    for row in weekly:
        by_weekday.setdefault(row.weekday, {})[row.person_id] = _from(row, False)
    result = {}
    for offset in range(days):
        day = start + datetime.timedelta(days=offset)
        result[day] = dict(by_weekday.get(day.weekday(), {}))
    for row in overrides:
        result[row.date][row.person_id] = _from(row, True)
    return result


def school_days_for(family, day: datetime.date, people=None) -> dict[int, SchoolDay]:
    """{person_id: SchoolDay} pour un jour (exception datée > semaine type)."""
    return school_days_range(family, day, 1, people=people)[day]


def school_day(person, day: datetime.date) -> SchoolDay | None:
    return school_days_for(person.family, day, people=[person]).get(person.pk)
