from django.db import models


class MomentSettings(models.Model):
    """Réglages de la famille pour les moments particuliers (une ligne au plus).

    Les dates du Ramadan et de l'Aïd sont calculées (calendrier Umm al-Qura) ;
    l'observation de la lune peut les décaler d'un jour en France : `hijri_shift`
    ajuste toutes les dates islamiques de la famille.
    """

    family = models.OneToOneField(
        "families.Family", on_delete=models.CASCADE, related_name="moment_settings"
    )
    hijri_shift = models.SmallIntegerField(
        "décalage des dates islamiques (jours)",
        default=0,
        help_text="+1 si le Ramadan commence un jour plus tard que prévu chez vous.",
    )
    eid_days = models.PositiveSmallIntegerField(
        "jours de fête pour chaque Aïd", default=1, help_text="Jours « fête » : tâches allégées."
    )
    ramadan_light = models.BooleanField(
        "rythme allégé pendant le Ramadan",
        default=True,
        help_text="Seules les tâches « obligatoires » comptent pour l'étoile, comme en vacances.",
    )

    class Meta:
        verbose_name = "réglages des moments"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(hijri_shift__gte=-2, hijri_shift__lte=2),
                name="moments_hijri_shift_range",
            ),
            models.CheckConstraint(
                condition=models.Q(eid_days__gte=1, eid_days__lte=3),
                name="moments_eid_days_range",
            ),
        ]

    def __str__(self):
        return f"Moments de {self.family}"


class PersonBirthday(models.Model):
    """Date de naissance d'une personne : message d'anniversaire le jour J."""

    person = models.OneToOneField(
        "families.Person", on_delete=models.CASCADE, related_name="birthday"
    )
    birth_date = models.DateField("date de naissance")

    class Meta:
        verbose_name = "anniversaire"

    def __str__(self):
        return f"{self.person} : {self.birth_date:%d/%m}"

    def age_on(self, day) -> int:
        return day.year - self.birth_date.year

    def next_on_or_after(self, day):
        """Prochain anniversaire (aujourd'hui compris). 29 février → 28 hors bissextile."""
        for year in (day.year, day.year + 1):
            try:
                candidate = self.birth_date.replace(year=year)
            except ValueError:
                candidate = self.birth_date.replace(year=year, day=28)
            if candidate >= day:
                return candidate
        return None
