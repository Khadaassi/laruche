from django.core.exceptions import ValidationError
from django.db import models


class AbsenceKind(models.TextChoices):
    VACATION = "vacation", "Vacances"
    SICK = "sick", "Malade"
    OTHER = "other", "Absent"


class AbsenceQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)

    def overlapping(self, start, end):
        """Absences qui touchent au moins un jour de [start, end]."""
        return self.filter(start_date__lte=end, end_date__gte=start)


class Absence(models.Model):
    """Période où une personne (ou toute la famille) est absente.

    `person` vide = toute la famille (vacances). Ces jours-là, les tâches du
    quotidien et le ménage de la personne sont suspendus (masqués, non
    cochables, rien de perdu côté étoiles) et l'école affiche l'absence.
    """

    family = models.ForeignKey("families.Family", on_delete=models.CASCADE, related_name="absences")
    person = models.ForeignKey(
        "families.Person",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="absences",
        verbose_name="qui",
        help_text="Vide = toute la famille.",
    )
    kind = models.CharField("motif", max_length=10, choices=AbsenceKind.choices)
    note = models.CharField("précision", max_length=80, blank=True)
    start_date = models.DateField("du")
    end_date = models.DateField("au")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AbsenceQuerySet.as_manager()

    class Meta:
        verbose_name = "absence"
        ordering = ["start_date", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="absence_dates_ordered",
            ),
        ]

    def __str__(self):
        return f"{self.who} — {self.get_kind_display()}"

    def clean(self):
        if self.person_id and self.person.family_id != self.family_id:
            raise ValidationError({"person": "Cette personne n'est pas de la famille."})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "La fin doit être après le début."})

    @property
    def who(self) -> str:
        return self.person.name if self.person_id else "Toute la famille"

    @property
    def label(self) -> str:
        """« Malade », « Vacances · chez mamie »."""
        base = self.get_kind_display()
        return f"{base} · {self.note}" if self.note else base

    @property
    def dates_display(self) -> str:
        if self.start_date == self.end_date:
            return f"le {self.start_date:%d/%m}"
        return f"du {self.start_date:%d/%m} au {self.end_date:%d/%m}"
