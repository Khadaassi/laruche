from django.core.exceptions import ValidationError
from django.db import models


class SchoolHolidayQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)

    def covering(self, day):
        return self.filter(start_date__lte=day, end_date__gte=day)


class SchoolHoliday(models.Model):
    """Période de vacances scolaires de la famille (bornes incluses).

    Contrairement à une absence, les enfants sont à la maison : la tablette reste
    active en **mode vacances**. Seules les tâches « obligatoires en vacances »
    comptent pour l'étoile du jour ; les autres deviennent des bonus. Voir
    domain-model, section « Mode vacances ».
    """

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="school_holidays"
    )
    name = models.CharField("nom", max_length=60)
    start_date = models.DateField("du")
    end_date = models.DateField("au")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = SchoolHolidayQuerySet.as_manager()

    class Meta:
        verbose_name = "vacances scolaires"
        verbose_name_plural = "vacances scolaires"
        ordering = ["start_date", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="holiday_dates_ordered",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "La fin doit être après le début."})

    @property
    def dates_display(self) -> str:
        return f"du {self.start_date:%d/%m/%Y} au {self.end_date:%d/%m/%Y}"
