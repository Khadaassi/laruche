"""Calcul des tâches du jour, par personne et par période."""

import datetime
from dataclasses import dataclass, field

from django.db.models import Exists, OuterRef

from .models import Task, TaskCompletion
from .periods import Period


def tasks_for_day(family, day: datetime.date, *, people=None, period=None) -> list[Task]:
    """Tâches prévues ce jour-là pour la famille, annotées `is_done`.

    `people` restreint à certaines personnes (déjà filtrées par famille par
    l'appelant) ; `period` à une période.
    """
    tasks = (
        Task.objects.for_family(family)
        .scheduled_on(day)
        .select_related("person")
        .annotate(is_done=Exists(TaskCompletion.objects.filter(task=OuterRef("pk"), date=day)))
        .order_by("person__created_at", "person__pk", "position", "created_at", "pk")
    )
    if people is not None:
        tasks = tasks.filter(person__in=people)
    if period is not None:
        tasks = tasks.filter(period=period)
    return list(tasks)


def count_remaining(tasks) -> int:
    return sum(1 for task in tasks if not task.is_done)


@dataclass
class PeriodGroup:
    period: Period
    tasks: list[Task] = field(default_factory=list)
    is_current: bool = False

    @property
    def remaining(self) -> int:
        return count_remaining(self.tasks)


def group_by_period(tasks, current: Period) -> list[PeriodGroup]:
    """Toujours les trois périodes, dans l'ordre de la journée."""
    groups = {p: PeriodGroup(period=p, is_current=p == current) for p in Period}
    for task in tasks:
        groups[task.period].tasks.append(task)
    return list(groups.values())


@dataclass
class PersonColumn:
    """Colonne d'une personne : ses tâches, et (écran partagé) son ménage du jour.

    `chores` contient des occurrences de ménage (`is_done`), comptées comme
    les tâches dans « X tâches restantes » et dans la progression.
    """

    person: object
    tasks: list[Task] = field(default_factory=list)
    chores: list = field(default_factory=list)

    @property
    def progress(self) -> list[bool]:
        return [t.is_done for t in self.tasks] + [c.is_done for c in self.chores]

    @property
    def total(self) -> int:
        return len(self.progress)

    @property
    def remaining(self) -> int:
        return self.progress.count(False)

    @property
    def done(self) -> int:
        return self.total - self.remaining


def group_by_person(people, tasks) -> list[PersonColumn]:
    """Une colonne par personne, même sans tâche, dans l'ordre de `people`."""
    columns = {person.pk: PersonColumn(person=person) for person in people}
    for task in tasks:
        if task.person_id in columns:
            columns[task.person_id].tasks.append(task)
    return list(columns.values())
