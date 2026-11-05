"""Méthode FlyLady : petites routines quotidiennes plutôt qu'un grand ménage.

- Routines du matin et du soir (« faire briller l'évier »), éditables.
- 5 zones de la maison, une par semaine du mois ; chaque jour, une mission de
  15 minutes dans la zone de la semaine.
- Chaque jour aussi : un « hot spot » de 2 minutes ; une fois par semaine, la
  « bénédiction de la maison » (1 h en 7 petites tâches) et le « 27 objets ».
Coches partagées par la famille (un parent ou l'autre), une ligne par jour.
"""

from django.db import models


class RoutineKind(models.TextChoices):
    MORNING = "morning", "Routine du matin"
    EVENING = "evening", "Routine du soir"
    BLESSING = "blessing", "Bénédiction de la semaine"


class FlyQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)


class FlyRoutineItem(models.Model):
    """Une ligne d'une routine (matin, soir) ou de la bénédiction hebdomadaire."""

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="fly_routine_items"
    )
    kind = models.CharField("routine", max_length=10, choices=RoutineKind.choices)
    title = models.CharField("intitulé", max_length=120)
    position = models.PositiveSmallIntegerField(default=0)

    objects = FlyQuerySet.as_manager()

    class Meta:
        verbose_name = "étape de routine"
        ordering = ["kind", "position", "pk"]

    def __str__(self):
        return self.title


class FlyZone(models.Model):
    """Zone de la maison (1 à 5), travaillée la n-ième semaine du mois."""

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="fly_zones"
    )
    number = models.PositiveSmallIntegerField("zone")
    name = models.CharField("nom", max_length=60)

    objects = FlyQuerySet.as_manager()

    class Meta:
        verbose_name = "zone"
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["family", "number"], name="unique_fly_zone"),
            models.CheckConstraint(
                condition=models.Q(number__gte=1, number__lte=5), name="fly_zone_number_valid"
            ),
        ]

    def __str__(self):
        return f"Zone {self.number} · {self.name}"


class FlyMission(models.Model):
    """Mission de 15 minutes dans une zone."""

    zone = models.ForeignKey(FlyZone, on_delete=models.CASCADE, related_name="missions")
    title = models.CharField("mission", max_length=120)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "mission"
        ordering = ["position", "pk"]

    def __str__(self):
        return self.title


class FlyCheck(models.Model):
    """« Fait » pour un élément FlyLady à une date (absence de ligne = à faire).

    `key` : `routine:<id>`, `mission:<id>`, `hotspot`, `fling`. La bénédiction et
    le « 27 objets » sont hebdomadaires : leur date est le lundi de la semaine.
    """

    family = models.ForeignKey("families.Family", on_delete=models.CASCADE, related_name="+")
    date = models.DateField()
    key = models.CharField(max_length=30)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "coche FlyLady"
        constraints = [
            models.UniqueConstraint(fields=["family", "date", "key"], name="unique_fly_check"),
        ]

    def __str__(self):
        return f"{self.key} — {self.date:%d/%m/%Y}"
