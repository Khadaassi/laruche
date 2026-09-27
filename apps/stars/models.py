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
