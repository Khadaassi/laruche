import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F

from .periods import Period

# Jours de la semaine, lundi = 0 comme `date.weekday()`.
WEEKDAY_LABELS = ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")
WEEKDAY_SHORT = ("Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di")
ALL_WEEKDAYS = 0b1111111


def weekdays_to_mask(days) -> int:
    """[0, 2, 4] → masque de bits (bit n = jour n)."""
    mask = 0
    for day in days:
        mask |= 1 << int(day)
    return mask


def mask_to_weekdays(mask: int) -> list[int]:
    return [day for day in range(7) if mask & (1 << day)]


class TaskQuerySet(models.QuerySet):
    def for_family(self, family):
        """Point d'entrée obligatoire des vues : tâches de la famille uniquement."""
        return self.filter(person__family=family)

    def on_weekday(self, weekday: int):
        return self.alias(_day=F("weekdays").bitand(1 << weekday)).filter(_day__gt=0)


class Task(models.Model):
    """Tâche récurrente d'une personne, pour une période et certains jours.

    Version minimale de la Phase 1 : pas encore de routines personnalisables.
    La famille est portée par la personne (pas de champ `family` en double
    qui pourrait diverger).
    """

    person = models.ForeignKey("families.Person", on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField("intitulé", max_length=120)
    period = models.CharField("période", max_length=10, choices=Period.choices)
    weekdays = models.PositiveSmallIntegerField(
        "jours", default=ALL_WEEKDAYS, help_text="Masque de bits, bit 0 = lundi."
    )
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TaskQuerySet.as_manager()

    class Meta:
        verbose_name = "tâche"
        ordering = ["position", "created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weekdays__gt=0, weekdays__lte=ALL_WEEKDAYS),
                name="task_weekdays_valid",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if not 0 < self.weekdays <= ALL_WEEKDAYS:
            raise ValidationError({"weekdays": "Choisissez au moins un jour."})

    @property
    def weekday_list(self) -> list[int]:
        return mask_to_weekdays(self.weekdays)

    @property
    def weekdays_display(self) -> str:
        if self.weekdays == ALL_WEEKDAYS:
            return "Tous les jours"
        if self.weekdays == 0b0011111:
            return "En semaine"
        if self.weekdays == 0b1100000:
            return "Le week-end"
        return " ".join(WEEKDAY_SHORT[d] for d in self.weekday_list)

    def is_scheduled_on(self, day: datetime.date) -> bool:
        return bool(self.weekdays & (1 << day.weekday()))


class TaskCompletion(models.Model):
    """« Fait » pour une tâche à une date. Absence de ligne = à faire.

    Une ligne par jour : l'historique reste disponible pour les paliers
    d'étoiles à venir.
    """

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="completions")
    date = models.DateField()
    completed_at = models.DateTimeField(auto_now_add=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Vide si coché depuis l'affichage partagé.",
    )

    class Meta:
        verbose_name = "validation"
        constraints = [
            models.UniqueConstraint(fields=["task", "date"], name="unique_completion_per_day"),
        ]

    def __str__(self):
        return f"{self.task} — {self.date:%d/%m/%Y}"
