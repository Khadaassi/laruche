"""Écritures sur les tâches."""

import datetime

from django.db import IntegrityError, transaction

from .models import HomeworkCheck, Task, TaskCompletion


def set_done(task: Task, day: datetime.date, done: bool, *, by=None) -> None:
    """Fixe l'état (idempotent) plutôt que d'inverser : pas de double bascule."""
    if done:
        TaskCompletion.objects.get_or_create(task=task, date=day, defaults={"completed_by": by})
    else:
        TaskCompletion.objects.filter(task=task, date=day).delete()
    task.is_done = done


def answer_homework_check(person, day: datetime.date, finished: bool, *, by=None) -> bool:
    """Enregistre la réponse du jour d'étude ; « oui » coche les devoirs du jour.

    Une seule réponse par enfant et par jour (la première compte, y compris
    entre deux requêtes simultanées). Renvoie True si cette réponse a été prise.
    """
    try:
        with transaction.atomic():
            HomeworkCheck.objects.create(person=person, date=day, finished=finished)
    except IntegrityError:
        return False
    if finished:
        for task in person.tasks.scheduled_on(day):
            if task.is_homework:
                set_done(task, day, True, by=by)
    return True
