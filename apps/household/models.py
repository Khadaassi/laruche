import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.tasks.models import ALL_WEEKDAYS, WEEKDAY_SHORT, mask_to_weekdays


class Frequency(models.TextChoices):
    """Récurrences simples proposées à la création (traduites en jours + intervalle)."""

    DAILY = "daily", "Tous les jours"
    WEEKLY = "weekly", "Chaque semaine"
    BIWEEKLY = "biweekly", "Une semaine sur deux"


def monday_of(day: datetime.date) -> datetime.date:
    return day - datetime.timedelta(days=day.weekday())


class HouseholdChoreQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)


class HouseholdChore(models.Model):
    """Tâche de ménage récurrente, assignée à un membre (parent ou enfant).

    Récurrence = jours de la semaine (masque de bits, comme `Task`) + un
    intervalle en semaines (1 = chaque semaine, 2 = une semaine sur deux,
    compté à partir de la semaine de `start_date`). Pas de rotation :
    l'assignation est fixe.
    """

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="household_chores"
    )
    title = models.CharField("tâche", max_length=120)
    assignee = models.ForeignKey(
        "families.Person", on_delete=models.CASCADE, related_name="household_chores"
    )
    weekdays = models.PositiveSmallIntegerField("jours", default=ALL_WEEKDAYS)
    interval_weeks = models.PositiveSmallIntegerField(
        "toutes les N semaines", default=1, choices=[(1, "Chaque semaine"), (2, "Une sur deux")]
    )
    start_date = models.DateField("à partir du", default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = HouseholdChoreQuerySet.as_manager()

    class Meta:
        verbose_name = "tâche de ménage"
        verbose_name_plural = "tâches de ménage"
        ordering = ["title", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weekdays__gt=0, weekdays__lte=ALL_WEEKDAYS),
                name="chore_weekdays_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(interval_weeks__in=[1, 2]), name="chore_interval_valid"
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        # La personne assignée appartient forcément à la famille de la tâche.
        if self.assignee_id and self.family_id and self.assignee.family_id != self.family_id:
            raise ValidationError({"assignee": "Cette personne n'est pas de la famille."})

    def occurs_on(self, day: datetime.date) -> bool:
        if day < self.start_date or not self.weekdays & (1 << day.weekday()):
            return False
        weeks = (monday_of(day) - monday_of(self.start_date)).days // 7
        return weeks % self.interval_weeks == 0

    @property
    def schedule_display(self) -> str:
        if self.weekdays == ALL_WEEKDAYS and self.interval_weeks == 1:
            return "Tous les jours"
        days = " ".join(WEEKDAY_SHORT[d] for d in mask_to_weekdays(self.weekdays))
        return f"{days} · une semaine sur deux" if self.interval_weeks == 2 else days


class ChoreCompletion(models.Model):
    """« Fait » pour une tâche de ménage à une date (même principe que les tâches)."""

    chore = models.ForeignKey(HouseholdChore, on_delete=models.CASCADE, related_name="completions")
    date = models.DateField()
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ménage fait"
        constraints = [
            models.UniqueConstraint(fields=["chore", "date"], name="unique_chore_completion"),
        ]

    def __str__(self):
        return f"{self.chore} — {self.date:%d/%m/%Y}"
