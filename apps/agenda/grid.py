"""Placement des rendez-vous dans la grille horaire du semainier.

Grille de 7 h à 22 h, par demi-heures (30 lignes). Le serveur calcule la
ligne de départ, la hauteur et la « voie » (colonne) de chaque bloc : le
gabarit n'utilise que des classes Tailwind (row-start-N, row-span-N,
col-start-N), aucun style inline (CSP).
"""

import datetime
import math
from dataclasses import dataclass

from .models import Event

DAY_START_HOUR, DAY_END_HOUR = 7, 22
SLOT_MINUTES = 30
SLOTS = (DAY_END_HOUR - DAY_START_HOUR) * 60 // SLOT_MINUTES
MAX_LANES = 3
HOURS = list(range(DAY_START_HOUR, DAY_END_HOUR))

FAMILY_CLASSES = "border border-border-strong bg-surface-100 text-ink"


def _minutes(t: datetime.time) -> int:
    return t.hour * 60 + t.minute


@dataclass
class Block:
    event: Event
    row_start: int  # 1-indexé
    row_span: int
    lane: int = 1
    clipped: bool = False  # hors de 7 h–22 h : heure réelle affichée dans le bloc

    @property
    def classes(self) -> str:
        people = list(self.event.people.all())
        colors = people[0].avatar_classes if len(people) == 1 else FAMILY_CLASSES
        return f"row-start-{self.row_start} row-span-{self.row_span} col-start-{self.lane} {colors}"


def place(event: Event) -> Block:
    start = _minutes(event.start_time) - DAY_START_HOUR * 60
    end = _minutes(event.end_time) - DAY_START_HOUR * 60
    first = min(max(start // SLOT_MINUTES, 0), SLOTS - 1)
    last = min(max(math.ceil(end / SLOT_MINUTES), first + 1), SLOTS)
    clipped = start < 0 or end > SLOTS * SLOT_MINUTES
    return Block(event, first + 1, last - first, clipped=clipped)


def layout_day(events) -> tuple[list[Block], int]:
    """Blocs d'un jour et nombre de voies : deux rendez-vous qui se chevauchent
    sont côte à côte (au plus 3 voies ; au-delà, ils se superposent)."""
    blocks = [place(e) for e in sorted(events, key=lambda e: (e.start_time, e.end_time, e.pk))]
    lane_ends = []  # dernière ligne occupée par voie
    for block in blocks:
        for index, end in enumerate(lane_ends):
            if end < block.row_start:
                lane_ends[index] = block.row_start + block.row_span - 1
                block.lane = index + 1
                break
        else:
            lane_ends.append(block.row_start + block.row_span - 1)
            block.lane = len(lane_ends)
        block.lane = min(block.lane, MAX_LANES)
    return blocks, max(1, min(len(lane_ends), MAX_LANES))


def events_by_day(family, start: datetime.date, days: int = 7) -> dict:
    """{date: [Event]} sur [start, start + days[, en deux requêtes."""
    end = start + datetime.timedelta(days=days - 1)
    events = list(Event.objects.for_family(family).between(start, end).prefetch_related("people"))
    return {
        start + datetime.timedelta(days=i): [
            e for e in events if e.occurs_on(start + datetime.timedelta(days=i))
        ]
        for i in range(days)
    }
