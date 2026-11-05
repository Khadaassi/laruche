"""Programme FlyLady du jour, calculé (rien n'est planifié en base)."""

import datetime
from dataclasses import dataclass, field

from .models import FlyCheck, FlyMission, FlyRoutineItem, FlyZone, RoutineKind

HOTSPOT = "hotspot"
FLING = "fling"


def monday_of(day: datetime.date) -> datetime.date:
    return day - datetime.timedelta(days=day.weekday())


def zone_number_for(day: datetime.date) -> int:
    """Zone de la semaine : 1re semaine du mois (lundi du 1 au 7) → zone 1, etc."""
    return min((monday_of(day).day - 1) // 7 + 1, 5)


@dataclass
class Line:
    key: str
    title: str
    done: bool
    date: datetime.date  # date de la coche (lundi pour l'hebdomadaire)


@dataclass
class FlyDay:
    day: datetime.date
    zone: FlyZone | None
    morning: list[Line] = field(default_factory=list)
    mission: Line | None = None
    hotspot: Line | None = None
    evening: list[Line] = field(default_factory=list)
    blessing: list[Line] = field(default_factory=list)
    fling: Line | None = None

    @property
    def daily_lines(self) -> list[Line]:
        return [*self.morning, *[x for x in (self.mission, self.hotspot) if x], *self.evening]

    @property
    def daily_done(self) -> int:
        return sum(line.done for line in self.daily_lines)


def valid_keys(family, day: datetime.date) -> dict[str, datetime.date]:
    """{clé cochable ce jour-là: date de la coche} : la vue refuse tout le reste."""
    plan = fly_day(family, day)
    lines = [*plan.daily_lines, *plan.blessing, *([plan.fling] if plan.fling else [])]
    return {line.key: line.date for line in lines}


def fly_day(family, day: datetime.date) -> FlyDay:
    monday = monday_of(day)
    checks = set(
        FlyCheck.objects.filter(family=family, date__in=[day, monday]).values_list("date", "key")
    )

    def line(key, title, on=day):
        return Line(key, title, (on, key) in checks, on)

    items = list(FlyRoutineItem.objects.for_family(family))
    zone = (
        FlyZone.objects.for_family(family)
        .filter(number=zone_number_for(day))
        .prefetch_related("missions")
        .first()
    )
    plan = FlyDay(day=day, zone=zone)
    for item in items:
        key = f"routine:{item.pk}"
        if item.kind == RoutineKind.MORNING:
            plan.morning.append(line(key, item.title))
        elif item.kind == RoutineKind.EVENING:
            plan.evening.append(line(key, item.title))
        else:
            plan.blessing.append(line(key, item.title, monday))
    missions: list[FlyMission] = list(zone.missions.all()) if zone else []
    if missions:
        # Une mission par jour, en tournant dans la liste (lundi = 1re…).
        mission = missions[day.weekday() % len(missions)]
        plan.mission = line(f"mission:{mission.pk}", mission.title)
    plan.hotspot = line(HOTSPOT, "Hot spot : 2 minutes sur le coin qui déborde")
    plan.fling = line(FLING, "Jeter ou donner 27 objets", monday)
    return plan
