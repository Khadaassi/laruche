"""Qui est absent, et quand. Deux requêtes au plus, quelle que soit la période."""

import datetime
from dataclasses import dataclass, field

from .models import Absence


@dataclass
class DayAbsences:
    """Absences d'un jour : de toute la famille, et par personne."""

    family_wide: Absence | None = None
    people: dict = field(default_factory=dict)  # {person_id: Absence}

    def for_person(self, person_id) -> Absence | None:
        return self.people.get(person_id) or self.family_wide

    def is_absent(self, person_id) -> bool:
        return self.for_person(person_id) is not None

    @property
    def any(self) -> bool:
        return bool(self.family_wide or self.people)


def absences_range(family, start: datetime.date, days: int) -> dict[datetime.date, DayAbsences]:
    """{date: DayAbsences} pour chaque jour de [start, start + days[."""
    end = start + datetime.timedelta(days=days - 1)
    result = {start + datetime.timedelta(days=i): DayAbsences() for i in range(days)}
    rows = Absence.objects.for_family(family).overlapping(start, end).select_related("person")
    for absence in rows:
        day = max(absence.start_date, start)
        while day <= min(absence.end_date, end):
            slot = result[day]
            if absence.person_id is None:
                slot.family_wide = slot.family_wide or absence
            else:
                slot.people.setdefault(absence.person_id, absence)
            day += datetime.timedelta(days=1)
    return result


def absences_on(family, day: datetime.date) -> DayAbsences:
    return absences_range(family, day, 1)[day]
