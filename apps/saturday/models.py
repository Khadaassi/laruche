import datetime

from django.core.exceptions import ValidationError
from django.db import models


class Season(models.TextChoices):
    ALL = "all", "Toutes saisons"
    SPRING = "spring", "Printemps"
    SUMMER = "summer", "Été"
    AUTUMN = "autumn", "Automne"
    WINTER = "winter", "Hiver"


# Saisons météorologiques (hémisphère nord) : mois → saison.
SEASON_OF_MONTH = {
    3: Season.SPRING, 4: Season.SPRING, 5: Season.SPRING,
    6: Season.SUMMER, 7: Season.SUMMER, 8: Season.SUMMER,
    9: Season.AUTUMN, 10: Season.AUTUMN, 11: Season.AUTUMN,
    12: Season.WINTER, 1: Season.WINTER, 2: Season.WINTER,
}  # fmt: skip


def season_of(day: datetime.date) -> Season:
    return SEASON_OF_MONTH[day.month]


class Place(models.TextChoices):
    OUTING = "outing", "Sortie"
    HOME = "home", "Maison"


class SaturdayActivityQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)

    def in_season(self, season):
        return self.filter(season__in=[Season.ALL, season])


class SaturdayActivity(models.Model):
    """Activité du catalogue de la famille, candidate au tirage du samedi."""

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="saturday_activities"
    )
    name = models.CharField("activité", max_length=80)
    season = models.CharField("saison", max_length=10, choices=Season.choices, default=Season.ALL)
    place = models.CharField("lieu", max_length=10, choices=Place.choices)
    is_free = models.BooleanField("gratuite", default=True)
    price = models.DecimalField(
        "prix indicatif (€)", max_digits=6, decimal_places=2, null=True, blank=True
    )
    star_cost = models.PositiveSmallIntegerField(
        "coût en étoiles",
        default=0,
        help_text="0 = pas besoin d'étoiles. Sinon, payé par le pot commun des enfants.",
    )
    last_done_on = models.DateField("dernière fois", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = SaturdayActivityQuerySet.as_manager()

    class Meta:
        verbose_name = "activité du samedi"
        verbose_name_plural = "activités du samedi"
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.is_free and self.price:
            raise ValidationError({"price": "Une activité gratuite n'a pas de prix."})

    @property
    def needs_stars(self) -> bool:
        return self.star_cost > 0

    @property
    def is_fully_free(self) -> bool:
        """« Gratuit » au sens du filtre : ni prix, ni étoiles."""
        return self.is_free and not self.needs_stars

    @property
    def cost_label(self) -> str:
        if self.is_free:
            return "Gratuit"
        return f"Payant · ~{self.price:.0f} €" if self.price else "Payant"


class PlanStatus(models.TextChoices):
    DRAWING = "drawing", "Tirage en cours"
    PLANNED = "planned", "Prévu"
    DONE = "done", "Fait"


class SaturdayPlanQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)


class SaturdayPlan(models.Model):
    """Le samedi d'une famille : tirage en cours, puis plan validé, puis historique.

    Une seule ligne par famille et par samedi : elle porte aussi le compteur de
    tirages (3 au maximum : le premier + 2 relances).
    """

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="saturday_plans"
    )
    date = models.DateField("samedi")
    status = models.CharField(max_length=10, choices=PlanStatus.choices, default=PlanStatus.DRAWING)
    activity = models.ForeignKey(
        SaturdayActivity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plans",
        help_text="Proposition en cours, puis activité validée.",
    )
    activity_name = models.CharField(
        max_length=80, blank=True, help_text="Copie du nom : l'historique survit au catalogue."
    )
    spins = models.PositiveSmallIntegerField("tirages effectués", default=0)
    star_spend = models.OneToOneField(
        "stars.StarSpend", on_delete=models.SET_NULL, null=True, blank=True, related_name="plan"
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    done_at = models.DateTimeField(null=True, blank=True)

    objects = SaturdayPlanQuerySet.as_manager()

    class Meta:
        verbose_name = "samedi"
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["family", "date"], name="unique_plan_per_saturday"),
        ]

    def __str__(self):
        return f"{self.date:%d/%m/%Y} — {self.activity_name or '…'}"
