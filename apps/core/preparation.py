"""« À préparer pour demain » : rappels calculés, jamais saisis.

Sources : la journée d'école de demain de chaque enfant (sandwich à préparer,
pas d'école, midi ailleurs) et les fêtes de demain (préparatifs restants).
"""

import datetime
from dataclasses import dataclass

from apps.celebrations.models import Celebration
from apps.celebrations.services import roll_over_recurring
from apps.families.models import Person
from apps.school.models import Lunch
from apps.school.selectors import school_days_for


@dataclass(frozen=True)
class PrepItem:
    kind: str  # "packed", "no_school", "lunch_elsewhere", "celebration"
    text: str
    person: Person | None = None


def tomorrow_items(family, today: datetime.date, people=None) -> list[PrepItem]:
    """Rappels pour demain, dans un ordre stable (enfants puis fêtes).

    `people` restreint aux personnes choisies (déjà filtrées par famille).
    """
    tomorrow = today + datetime.timedelta(days=1)
    children = Person.objects.for_family(family).children()
    if people is not None:
        children = children.filter(pk__in=[p.pk for p in people])
    days = school_days_for(family, tomorrow, people=children)

    items = []
    for child in children:
        day = days.get(child.pk)
        if day is None:
            continue
        if day.lunch == Lunch.PACKED:
            items.append(PrepItem("packed", f"Préparer le sandwich de {child.name} (APC)", child))
        elif day.lunch == Lunch.NONE and day.is_override:
            # Seulement une exception : un mercredi sans école n'est pas une nouvelle.
            items.append(PrepItem("no_school", f"Pas d'école pour {child.name}", child))
        elif day.lunch == Lunch.OTHER and day.lunch_note:
            items.append(
                PrepItem("lunch_elsewhere", f"Midi de {child.name} : {day.lunch_note}", child)
            )

    roll_over_recurring(family, today)
    for celebration in Celebration.objects.for_family(family).filter(date=tomorrow):
        remaining = celebration.todos.filter(done=False).count()
        suffix = (
            f" — {remaining} préparatif{'s' if remaining > 1 else ''} restant"
            f"{'s' if remaining > 1 else ''}"
            if remaining
            else ""
        )
        items.append(PrepItem("celebration", f"{celebration.name} demain{suffix}"))
    return items
