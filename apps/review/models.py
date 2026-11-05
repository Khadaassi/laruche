from django.db import models


class WeeklyReview(models.Model):
    """Revue faite pour la semaine du lundi `week` (une par famille et par semaine)."""

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="weekly_reviews"
    )
    week = models.DateField("semaine du")
    done_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "revue de la semaine"
        verbose_name_plural = "revues de la semaine"
        constraints = [
            models.UniqueConstraint(fields=["family", "week"], name="unique_weekly_review"),
        ]

    def __str__(self):
        return f"Semaine du {self.week:%d/%m/%Y}"
