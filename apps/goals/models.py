"""Objectifs personnels de l'année (vision board), **privés** : rattachés à un compte.

Jamais visibles par l'autre parent ni sur la tablette ; chaque requête filtre sur
`request.user` (voir `GoalQuerySet.mine`). Un objectif se décline en **petits pas**
(`Step`) cochés ou chiffrés chaque jour, avec un journal (`Entry` : victoires,
souvenirs, versements d'épargne) et, au besoin, des proches à appeler (`Contact`).
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class GoalQuerySet(models.QuerySet):
    def mine(self, user, year=None):
        qs = self.filter(user=user)
        return qs.filter(year=year) if year else qs


class Goal(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="goals"
    )
    year = models.PositiveSmallIntegerField("année")
    title = models.CharField("objectif", max_length=80)
    icon = models.CharField("illustration", max_length=20, default="star")
    position = models.PositiveSmallIntegerField(default=0)
    journal_label = models.CharField(
        "journal", max_length=60, blank=True, help_text="Ex. « Une petite victoire »."
    )
    savings_target = models.DecimalField(
        "objectif d'épargne (€)",
        max_digits=9,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("1"))],
    )
    has_contacts = models.BooleanField("proches à appeler", default=False)

    objects = GoalQuerySet.as_manager()

    class Meta:
        verbose_name = "objectif"
        ordering = ["year", "position", "pk"]

    def __str__(self):
        return f"{self.year} · {self.title}"


class StepQuerySet(models.QuerySet):
    def mine(self, user):
        return self.filter(goal__user=user)


class Step(models.Model):
    """Petit pas : fait si la valeur du jour atteint `daily_target` ; visé `days_per_week` fois."""

    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="steps")
    title = models.CharField("petit pas", max_length=80)
    unit = models.CharField(
        "unité", max_length=20, blank=True, help_text="Vide = simple case à cocher."
    )
    daily_target = models.PositiveSmallIntegerField(
        "objectif du jour", default=1, validators=[MinValueValidator(1)]
    )
    days_per_week = models.PositiveSmallIntegerField(
        "jours par semaine", default=7, validators=[MinValueValidator(1), MaxValueValidator(7)]
    )
    position = models.PositiveSmallIntegerField(default=0)

    objects = StepQuerySet.as_manager()

    class Meta:
        verbose_name = "petit pas"
        verbose_name_plural = "petits pas"
        ordering = ["position", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(days_per_week__gte=1, days_per_week__lte=7),
                name="goal_step_days_valid",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def is_counted(self) -> bool:
        return bool(self.unit)

    @property
    def is_daily(self) -> bool:
        return self.days_per_week >= 5


class StepLog(models.Model):
    step = models.ForeignKey(Step, on_delete=models.CASCADE, related_name="logs")
    date = models.DateField()
    value = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["step", "date"], name="unique_step_log"),
        ]

    def __str__(self):
        return f"{self.step} — {self.date:%d/%m/%Y} : {self.value}"


class Entry(models.Model):
    """Ligne de journal d'un objectif (victoire, souvenir) ou versement (`amount`)."""

    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="entries")
    date = models.DateField()
    text = models.CharField("note", max_length=200, blank=True)
    amount = models.DecimalField(
        "montant (€)", max_digits=9, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "note"
        ordering = ["-date", "-pk"]

    def __str__(self):
        return self.text or f"{self.amount} €"


class Contact(models.Model):
    """Proche à appeler régulièrement (objectif « Entretenir les liens »)."""

    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField("proche", max_length=60)
    every_days = models.PositiveSmallIntegerField(
        "tous les (jours)", default=14, validators=[MinValueValidator(1)]
    )
    last_contact = models.DateField("dernier contact", null=True, blank=True)

    class Meta:
        verbose_name = "proche"
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name
