"""Écritures sur les tâches."""

import datetime

from .models import Task, TaskCompletion


def set_done(task: Task, day: datetime.date, done: bool, *, by=None) -> None:
    """Fixe l'état (idempotent) plutôt que d'inverser : pas de double bascule."""
    if done:
        TaskCompletion.objects.get_or_create(task=task, date=day, defaults={"completed_by": by})
    else:
        TaskCompletion.objects.filter(task=task, date=day).delete()
    task.is_done = done
