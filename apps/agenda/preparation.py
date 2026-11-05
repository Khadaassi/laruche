"""Préparatifs des rendez-vous d'aujourd'hui et de demain, et qui accompagne."""

import datetime
from dataclasses import dataclass, field

from .grid import events_by_day
from .models import EventOccurrence, EventPrepCheck


@dataclass
class PrepOccurrence:
    event: object
    date: datetime.date
    driver: object | None = None  # Person : accompagne ce jour-là
    taken_over: bool = False  # « Je m'en occupe » pour cette date
    preps: list = field(default_factory=list)  # [(EventPrep, fait ?)]

    @property
    def remaining(self) -> int:
        return sum(1 for _, done in self.preps if not done)


def upcoming(family, today: datetime.date, days: int = 2, people=None) -> list[PrepOccurrence]:
    """Rendez-vous d'aujourd'hui et de demain qui ont des préparatifs ou un accompagnateur.

    `people` : ne garder que ceux qui concernent ces personnes (ou toute la famille).
    """
    by_day = events_by_day(family, today, days)
    events = {e.pk: e for evs in by_day.values() for e in evs}
    preps = {}
    for event in events.values():
        preps[event.pk] = list(event.preps.all())
    dates = list(by_day)
    done = set(
        EventPrepCheck.objects.filter(prep__event_id__in=events, date__in=dates).values_list(
            "prep_id", "date"
        )
    )
    overrides = {
        (o.event_id, o.date): o.driver
        for o in EventOccurrence.objects.filter(event_id__in=events, date__in=dates).select_related(
            "driver"
        )
    }
    wanted = {p.pk for p in people} if people is not None else None
    result = []
    for day, day_events in by_day.items():
        for event in day_events:
            if not preps[event.pk] and not event.driver_id and (event.pk, day) not in overrides:
                continue
            concerned = {p.pk for p in event.people.all()}
            if wanted is not None and concerned and not concerned & wanted:
                continue
            driver = overrides.get((event.pk, day)) or event.driver
            result.append(
                PrepOccurrence(
                    event=event,
                    date=day,
                    driver=driver,
                    taken_over=(event.pk, day) in overrides,
                    preps=[(p, (p.pk, day) in done) for p in preps[event.pk]],
                )
            )
    return result
