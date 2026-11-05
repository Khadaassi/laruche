"""Statistiques des enfants, en un petit nombre de requêtes (jamais une par jour).

- Calendrier du mois : étoile (journée complète), partiel (au moins une coche),
  rien, absent, ou à venir. Le « prévu » d'un jour passé n'est pas recalculé :
  les tâches ont pu changer depuis ; l'étoile, elle, est figée au moment gagné.
- Tendance : étoiles par semaine sur les 8 dernières semaines.
- Tâches souvent oubliées : sur 30 jours, jours prévus (hors absence et hors
  jours de vacances où la tâche est facultative) contre jours cochés.
"""

import calendar
import datetime
from dataclasses import dataclass, field

from django.db.models import Count

from apps.absences.selectors import absences_range
from apps.holidays.models import SchoolHoliday
from apps.stars.models import DayStar
from apps.tasks.models import HolidayMode, Task, TaskCompletion

TREND_WEEKS = 8
# Hauteurs de barre par quart du maximum (classes complètes pour Tailwind).
BAR_HEIGHTS = ("h-1", "h-4", "h-8", "h-12", "h-16")
SKIPPED_DAYS = 30


class DayState:
    STAR = "star"
    PARTIAL = "partial"
    EMPTY = "empty"
    ABSENT = "absent"
    FUTURE = "future"


@dataclass
class CalendarDay:
    date: datetime.date | None  # None = case vide avant le 1er du mois
    state: str = DayState.FUTURE
    is_holiday: bool = False


@dataclass
class ChildProgress:
    person: object
    weeks: list[list[CalendarDay]] = field(default_factory=list)
    stars_this_month: int = 0
    trend: list[tuple[datetime.date, int]] = field(default_factory=list)  # (lundi, étoiles)
    skipped: list[tuple[Task, int, int]] = field(default_factory=list)  # (tâche, faites, prévues)

    @property
    def trend_bars(self) -> list[tuple[datetime.date, int, str]]:
        """(lundi, étoiles, classe de hauteur) : pas de style inline (CSP)."""
        top = max((n for _, n in self.trend), default=0) or 1
        return [(monday, n, BAR_HEIGHTS[round(n / top * 4)]) for monday, n in self.trend]


def _holiday_days(family, start, end) -> set[datetime.date]:
    days = set()
    for h in SchoolHoliday.objects.for_family(family).filter(
        start_date__lte=end, end_date__gte=start
    ):
        day = max(h.start_date, start)
        while day <= min(h.end_date, end):
            days.add(day)
            day += datetime.timedelta(days=1)
    return days


def month_calendar(family, children, month: datetime.date, today: datetime.date):
    """{person_id: (semaines de CalendarDay, étoiles du mois)} pour le mois de `month`."""
    first = month.replace(day=1)
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    ids = [c.pk for c in children]
    stars = set(
        DayStar.objects.filter(person_id__in=ids, date__range=(first, last)).values_list(
            "person_id", "date"
        )
    )
    ticked = set(
        TaskCompletion.objects.filter(
            task__person_id__in=ids, date__range=(first, last)
        ).values_list("task__person_id", "date")
    )
    absences = absences_range(family, first, (last - first).days + 1)
    holidays = _holiday_days(family, first, last)
    result = {}
    for child in children:
        cells = [CalendarDay(None)] * first.weekday()
        count = 0
        day = first
        while day <= last:
            if day > today:
                state = DayState.FUTURE
            elif (child.pk, day) in stars:
                state, count = DayState.STAR, count + 1
            elif absences[day].is_absent(child.pk):
                state = DayState.ABSENT
            elif (child.pk, day) in ticked:
                state = DayState.PARTIAL
            else:
                state = DayState.EMPTY
            cells.append(CalendarDay(day, state, day in holidays))
            day += datetime.timedelta(days=1)
        cells += [CalendarDay(None)] * (-len(cells) % 7)
        result[child.pk] = ([cells[i : i + 7] for i in range(0, len(cells), 7)], count)
    return result


def weekly_trend(children, today: datetime.date):
    """{person_id: [(lundi, étoiles)]} sur les `TREND_WEEKS` dernières semaines."""
    monday = today - datetime.timedelta(days=today.weekday())
    mondays = [monday - datetime.timedelta(weeks=i) for i in reversed(range(TREND_WEEKS))]
    trend = {c.pk: dict.fromkeys(mondays, 0) for c in children}
    rows = DayStar.objects.filter(person__in=children, date__gte=mondays[0], date__lte=today)
    for person_id, day in rows.values_list("person_id", "date"):
        trend[person_id][day - datetime.timedelta(days=day.weekday())] += 1
    return {pid: list(weeks.items()) for pid, weeks in trend.items()}


def skipped_tasks(family, children, today: datetime.date, limit=5):
    """{person_id: [(tâche, faites, prévues)]}, les moins bien suivies d'abord.

    Jours comptés : les `SKIPPED_DAYS` derniers jours **avant** aujourd'hui (la
    journée en cours n'est pas finie). Seules les tâches prévues au moins 3 fois.
    """
    end = today - datetime.timedelta(days=1)
    start = today - datetime.timedelta(days=SKIPPED_DAYS)
    tasks = list(Task.objects.for_family(family).filter(person__in=children))
    done = {
        row["task_id"]: row["n"]
        for row in TaskCompletion.objects.filter(task__in=tasks, date__range=(start, end))
        .values("task_id")
        .annotate(n=Count("pk"))
    }
    absences = absences_range(family, start, SKIPPED_DAYS)
    holidays = _holiday_days(family, start, end)
    result = {c.pk: [] for c in children}
    for task in tasks:
        due = 0
        day = start
        while day <= end:
            if (
                task.is_scheduled_on(day)
                and not absences[day].is_absent(task.person_id)
                and not (day in holidays and task.holiday_mode != HolidayMode.REQUIRED)
            ):
                due += 1
            day += datetime.timedelta(days=1)
        if due >= 3:
            result[task.person_id].append((task, min(done.get(task.pk, 0), due), due))
    for pid, rows in result.items():
        rows.sort(key=lambda r: (r[1] / r[2], -r[2], r[0].title))
        result[pid] = [r for r in rows if r[1] < r[2]][:limit]
    return result


def progress_for(family, children, month: datetime.date, today: datetime.date):
    calendars = month_calendar(family, children, month, today)
    trends = weekly_trend(children, today)
    skipped = skipped_tasks(family, children, today)
    return [
        ChildProgress(
            person=child,
            weeks=calendars[child.pk][0],
            stars_this_month=calendars[child.pk][1],
            trend=trends[child.pk],
            skipped=skipped[child.pk],
        )
        for child in children
    ]
