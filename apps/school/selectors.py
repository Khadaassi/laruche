"""Journée d'école effective : exception datée si elle existe, sinon semaine type."""

import datetime
from dataclasses import dataclass

from apps.absences.selectors import absences_range

from .models import Lunch, SchoolDayOverride, SchoolDaySchedule


@dataclass(frozen=True)
class SchoolDay:
    lunch: str
    lunch_note: str
    study: bool
    is_override: bool
    absence: str = ""  # libellé de l'absence (« Malade »), prioritaire sur l'école
    absence_kind: str = ""

    @property
    def has_school(self) -> bool:
        return self.lunch != Lunch.NONE and not self.absence

    @property
    def icon(self) -> str:
        return f"absence_{self.absence_kind}" if self.absence else self.lunch

    @property
    def lunch_label(self) -> str:
        if self.absence:
            return self.absence
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
    exception ce jour-là (rien à afficher). Une absence (vacances, malade)
    remplace l'école ce jour-là (`SchoolDay.absence`).
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
    # Absence (vacances, malade) : remplace l'école de la personne ce jour-là.
    absences = absences_range(family, start, days)
    ids = None if people is None else {getattr(p, "pk", p) for p in people}
    for day, absent in absences.items():
        if not absent.any:
            continue
        targets = ids if ids is not None else set(result[day]) | set(absent.people)
        for person_id in targets:
            absence = absent.for_person(person_id)
            if absence:
                result[day][person_id] = SchoolDay(
                    Lunch.NONE, "", False, True, absence.label, absence.kind
                )
    return result


def school_days_for(family, day: datetime.date, people=None) -> dict[int, SchoolDay]:
    """{person_id: SchoolDay} pour un jour (exception datée > semaine type)."""
    return school_days_range(family, day, 1, people=people)[day]


def school_day(person, day: datetime.date) -> SchoolDay | None:
    return school_days_for(person.family, day, people=[person]).get(person.pk)
