import datetime
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F

from .periods import Period

# Jours de la semaine, lundi = 0 comme `date.weekday()`.
WEEKDAY_LABELS = ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")
WEEKDAY_SHORT = ("Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di")
ALL_WEEKDAYS = 0b1111111
# Raccourcis de jours proposés dans les formulaires (voir domain-model).
SCHOOL_DAYS = 0b0011011  # lundi, mardi, jeudi, vendredi (mercredi sans école)
WEEKEND = 0b1100000


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

    def scheduled_on(self, day: datetime.date):
        """Tâches prévues ce jour-là : bon jour de la semaine, et dans la période
        (`start_date` / `end_date`) si elle est bornée."""
        return (
            self.on_weekday(day.weekday())
            .filter(models.Q(start_date__isnull=True) | models.Q(start_date__lte=day))
            .filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=day))
        )


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
    start_date = models.DateField(
        "du", null=True, blank=True, help_text="Vide = sans date de début."
    )
    end_date = models.DateField("au", null=True, blank=True, help_text="Vide = sans date de fin.")
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
            models.CheckConstraint(
                condition=models.Q(start_date__isnull=True)
                | models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="task_dates_ordered",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if not 0 < self.weekdays <= ALL_WEEKDAYS:
            raise ValidationError({"weekdays": "Choisissez au moins un jour."})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "La fin doit être après le début."})

    @property
    def weekday_list(self) -> list[int]:
        return mask_to_weekdays(self.weekdays)

    @property
    def weekdays_display(self) -> str:
        if self.weekdays == ALL_WEEKDAYS:
            return "Tous les jours"
        if self.weekdays == 0b0011111:
            return "En semaine"
        if self.weekdays == SCHOOL_DAYS:
            return "Jours d'école"
        if self.weekdays == WEEKEND:
            return "Le week-end"
        return " ".join(WEEKDAY_SHORT[d] for d in self.weekday_list)

    @property
    def dates_display(self) -> str:
        """« du 12 oct. au 16 oct. », « à partir du… », « jusqu'au… », ou vide."""
        fmt = "%d/%m"
        if self.start_date and self.end_date:
            if self.start_date == self.end_date:
                return f"le {self.start_date:{fmt}}"
            return f"du {self.start_date:{fmt}} au {self.end_date:{fmt}}"
        if self.start_date:
            return f"à partir du {self.start_date:{fmt}}"
        if self.end_date:
            return f"jusqu'au {self.end_date:{fmt}}"
        return ""

    @property
    def is_homework(self) -> bool:
        """Tâche « devoirs », reconnue à son intitulé (accents et casse ignorés).

        Sert les jours d'étude : question « As-tu fini tes devoirs à l'étude ? »
        et devoirs en tête de liste. Aucun réglage en plus pour les parents.
        """
        plain = unicodedata.normalize("NFKD", self.title).encode("ascii", "ignore").decode()
        return "devoir" in plain.lower()

    def is_scheduled_on(self, day: datetime.date) -> bool:
        in_range = (not self.start_date or self.start_date <= day) and (
            not self.end_date or day <= self.end_date
        )
        return in_range and bool(self.weekdays & (1 << day.weekday()))


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


class HomeworkCheck(models.Model):
    """Réponse d'un enfant, un jour d'étude, à « As-tu fini tes devoirs à l'étude ? ».

    Une seule par enfant et par jour : la question n'est posée qu'une fois.
    « Oui » coche ses tâches devoirs du jour ; « Non » ne change rien.
    """

    person = models.ForeignKey(
        "families.Person", on_delete=models.CASCADE, related_name="homework_checks"
    )
    date = models.DateField()
    finished = models.BooleanField("devoirs finis à l'étude")
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "devoirs à l'étude"
        verbose_name_plural = "devoirs à l'étude"
        constraints = [
            models.UniqueConstraint(fields=["person", "date"], name="unique_homework_check"),
        ]

    def __str__(self):
        return f"{self.person} — {self.date:%d/%m/%Y} — {'oui' if self.finished else 'non'}"
