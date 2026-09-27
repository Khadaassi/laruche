from django.db import models

from apps.tasks.models import WEEKDAY_LABELS

# Jours d'école proposés dans les réglages (lundi → vendredi). Le samedi et
# le dimanche restent possibles en exception datée.
SCHOOL_WEEKDAYS = range(5)


class Lunch(models.TextChoices):
    """Ce que fait l'enfant le midi."""

    CANTEEN = "canteen", "Cantine"
    PACKED = "packed", "Sandwich (APC)"
    OTHER = "other", "Autre"
    NONE = "none", "Pas d'école"


class SchoolDayFields(models.Model):
    """Champs communs à la semaine type et aux exceptions datées."""

    lunch = models.CharField("midi", max_length=10, choices=Lunch.choices)
    lunch_note = models.CharField(
        "précision",
        max_length=60,
        blank=True,
        help_text="Pour « Autre » : chez mamie, à la maison…",
    )
    study = models.BooleanField("étude le soir", default=False)

    class Meta:
        abstract = True


class SchoolDayScheduleQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(person__family=family)


class SchoolDaySchedule(SchoolDayFields):
    """Semaine type d'un enfant : se répète chaque semaine.

    Pas de ligne pour un jour = rien à afficher ce jour-là.
    """

    person = models.ForeignKey(
        "families.Person", on_delete=models.CASCADE, related_name="school_schedules"
    )
    weekday = models.PositiveSmallIntegerField(
        "jour", choices=list(enumerate(WEEKDAY_LABELS)), help_text="0 = lundi."
    )

    objects = SchoolDayScheduleQuerySet.as_manager()

    class Meta:
        verbose_name = "journée d'école type"
        verbose_name_plural = "semaine d'école type"
        ordering = ["person", "weekday"]
        constraints = [
            models.UniqueConstraint(fields=["person", "weekday"], name="unique_school_weekday"),
            models.CheckConstraint(
                condition=models.Q(weekday__gte=0, weekday__lte=6), name="school_weekday_valid"
            ),
        ]

    def __str__(self):
        return f"{self.person} — {WEEKDAY_LABELS[self.weekday]}"


class SchoolDayOverride(SchoolDayFields):
    """Exception ponctuelle pour une date : remplace la semaine type ce jour-là."""

    person = models.ForeignKey(
        "families.Person", on_delete=models.CASCADE, related_name="school_overrides"
    )
    date = models.DateField()

    objects = SchoolDayScheduleQuerySet.as_manager()

    class Meta:
        verbose_name = "exception d'école"
        ordering = ["date", "person"]
        constraints = [
            models.UniqueConstraint(fields=["person", "date"], name="unique_school_override"),
        ]

    def __str__(self):
        return f"{self.person} — {self.date:%d/%m/%Y}"
