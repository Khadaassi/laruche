from django.db import models


class StarSpend(models.Model):
    """Une dépense d'étoiles de la famille (ex. activité du samedi).

    Le détail par enfant est dans `StarDebit`. Supprimer la dépense (annulation)
    supprime ses lignes : les étoiles reviennent à leurs propriétaires.
    """

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="star_spends"
    )
    total = models.PositiveIntegerField()
    reason = models.CharField("motif", max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "dépense d'étoiles"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.reason} ({self.total} ★)"


class StarDebit(models.Model):
    """Part d'un enfant dans une dépense."""

    spend = models.ForeignKey(StarSpend, on_delete=models.CASCADE, related_name="debits")
    person = models.ForeignKey(
        "families.Person", on_delete=models.CASCADE, related_name="star_debits"
    )
    amount = models.PositiveIntegerField()

    class Meta:
        verbose_name = "contribution"
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(fields=["spend", "person"], name="unique_debit_per_person"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="debit_positive"),
        ]

    def __str__(self):
        return f"{self.person} : {self.amount} ★"


class DayStar(models.Model):
    """Étoile d'une journée complète : au plus une ligne par enfant et par jour.

    Créée quand toutes les tâches et tout le ménage du jour de l'enfant sont
    cochés (`services.award_day_star`). Jamais supprimée par un décochage :
    une étoile gagnée reste gagnée. `celebrated` passe à vrai quand l'écran
    partagé a montré « Journée terminée ! » (une seule fois).
    """

    person = models.ForeignKey(
        "families.Person", on_delete=models.CASCADE, related_name="day_stars"
    )
    date = models.DateField()
    celebrated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "étoile du jour"
        verbose_name_plural = "étoiles du jour"
        ordering = ["-date", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["person", "date"], name="unique_day_star_per_person"),
        ]

    def __str__(self):
        return f"{self.person} : {self.date:%d/%m/%Y}"


class StarOpeningBalance(models.Model):
    """Solde de départ : étoiles gagnées avant La Ruche (reprise d'une autre application).

    Au plus un par enfant (OneToOne). Compté dans les étoiles **gagnées** (palier compris),
    comme des journées complètes déjà acquises ; jamais recalculé. Créé par
    `services.grant_opening_balance`, pas depuis l'interface.
    """

    person = models.OneToOneField(
        "families.Person", on_delete=models.CASCADE, related_name="star_opening_balance"
    )
    amount = models.PositiveIntegerField("étoiles")
    reason = models.CharField("motif", max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "solde de départ"
        verbose_name_plural = "soldes de départ"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="opening_balance_positive"
            ),
        ]

    def __str__(self):
        return f"{self.person} : {self.amount} ★ ({self.reason})"


class TierCelebration(models.Model):
    """Dernier palier d'étoiles déjà fêté pour un enfant (écran partagé).

    Garantit une seule célébration par palier : l'écran ne la montre que s'il
    réussit à faire avancer ce compteur (mise à jour conditionnelle atomique).
    """

    person = models.OneToOneField(
        "families.Person", on_delete=models.CASCADE, related_name="tier_celebration"
    )
    tier = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "palier fêté"

    def __str__(self):
        return f"{self.person} : palier {self.tier}"
