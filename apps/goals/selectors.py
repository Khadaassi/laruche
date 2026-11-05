"""Lectures de « Mon année » : état du jour, semaine, calendrier, épargne."""

import calendar
import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Sum

from .models import Entry, Goal, Step, StepLog


def monday_of(day):
    return day - datetime.timedelta(days=day.weekday())


@dataclass
class StepState:
    step: Step
    today_value: int = 0
    week_days: int = 0  # jours où le pas est atteint depuis lundi

    @property
    def done_today(self) -> bool:
        return self.today_value >= self.step.daily_target

    @property
    def week_target(self) -> int:
        return self.step.days_per_week

    @property
    def week_ok(self) -> bool:
        return self.week_days >= self.week_target

    @property
    def show_today(self) -> bool:
        """À proposer aujourd'hui : quotidien, ou hebdo pas encore atteint (ou fait aujourd'hui)."""
        return self.step.is_daily or not self.week_ok or self.done_today


@dataclass
class GoalState:
    goal: Goal
    steps: list[StepState] = field(default_factory=list)
    saved: Decimal | None = None

    @property
    def week_ratio(self) -> float:
        target = sum(s.week_target for s in self.steps)
        done = sum(min(s.week_days, s.week_target) for s in self.steps)
        return done / target if target else 0.0

    @property
    def week_percent(self) -> int:
        return round(self.week_ratio * 100)

    @property
    def week_bar(self) -> str:
        """Largeur de barre en classe (pas de style inline, CSP)."""
        return WIDTHS[min(round(self.week_ratio * 10), 10)]

    @property
    def savings_percent(self) -> int | None:
        target = self.goal.savings_target
        if not target:
            return None
        return min(round((self.saved or 0) / target * 100), 100)

    @property
    def savings_bar(self) -> str:
        return WIDTHS[min(round((self.savings_percent or 0) / 10), 10)]


WIDTHS = (
    "w-0",
    "w-1/12",
    "w-2/12",
    "w-3/12",
    "w-4/12",
    "w-5/12",
    "w-6/12",
    "w-8/12",
    "w-9/12",
    "w-11/12",
    "w-full",
)


def goal_states(goals, today: datetime.date) -> list[GoalState]:
    goals = list(goals)
    steps = list(Step.objects.filter(goal__in=goals))
    monday = monday_of(today)
    logs = StepLog.objects.filter(step__in=steps, date__gte=monday, date__lte=today)
    by_step: dict[int, list] = {}
    for log in logs:
        by_step.setdefault(log.step_id, []).append(log)
    states = {g.pk: GoalState(goal=g) for g in goals}
    for step in steps:
        rows = by_step.get(step.pk, [])
        state = StepState(
            step=step,
            today_value=next((r.value for r in rows if r.date == today), 0),
            week_days=sum(1 for r in rows if r.value >= step.daily_target),
        )
        states[step.goal_id].steps.append(state)
    saved = dict(
        Entry.objects.filter(goal__in=goals, amount__isnull=False)
        .values_list("goal_id")
        .annotate(total=Sum("amount"))
    )
    for state in states.values():
        state.steps.sort(key=lambda s: (s.step.position, s.step.pk))
        if state.goal.savings_target:
            state.saved = saved.get(state.goal.pk, Decimal("0"))
    return [states[g.pk] for g in goals]


# Classes complètes (définies dans app.css) : visibles par Tailwind dans ce fichier.
LEVELS = ("vision-level-empty", "vision-level-low", "vision-level-mid", "vision-level-full")


@dataclass
class MonthGrid:
    month: datetime.date
    weeks: list  # [[(date|None, niveau)]]


def year_calendar(goal: Goal, today: datetime.date) -> list[MonthGrid]:
    """Calendrier par mois : niveau du jour = part des pas quotidiens atteints (4 niveaux).

    Les mois de l'année de l'objectif, précédés des mois en cours si l'année n'a pas
    encore commencé (on peut démarrer en avance).
    """
    start = min(datetime.date(goal.year, 1, 1), today.replace(day=1))
    end = datetime.date(goal.year, 12, 31)
    steps = list(goal.steps.all())
    daily = [s for s in steps if s.is_daily] or steps
    logs = StepLog.objects.filter(step__in=steps, date__range=(start, end))
    done: dict[datetime.date, int] = {}
    targets = {s.pk: s.daily_target for s in steps}
    for log in logs:
        if log.value >= targets[log.step_id]:
            done[log.date] = done.get(log.date, 0) + 1
    months = []
    month = start
    while month <= end:
        last = calendar.monthrange(month.year, month.month)[1]
        cells = [(None, "")] * month.weekday()
        for d in range(1, last + 1):
            day = month.replace(day=d)
            if day > today:
                level = "vision-level-future"
            else:
                ratio = done.get(day, 0) / len(daily) if daily else 0
                level = LEVELS[0 if ratio == 0 else 1 if ratio < 0.5 else 2 if ratio < 1 else 3]
            cells.append((day, level))
        cells += [(None, "")] * (-len(cells) % 7)
        months.append(MonthGrid(month, [cells[i : i + 7] for i in range(0, len(cells), 7)]))
        month = (month.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return months
