from django.core.exceptions import ValidationError
from django.db import models


class CelebrationQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)


class Celebration(models.Model):
    """Une fête datée (Aïd, anniversaire…).

    `recurs_yearly` : la fête se recrée l'année suivante, même jour et même
    mois, une fois sa date passée (voir services.roll_over_recurring). À
    laisser décoché pour les fêtes religieuses, dont la date change.
    """

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="celebrations"
    )
    name = models.CharField("nom", max_length=80)
    date = models.DateField("date")
    recurs_yearly = models.BooleanField(
        "chaque année",
        default=False,
        help_text="Anniversaire… (pas l'Aïd, dont la date change chaque année).",
    )
    previous = models.OneToOneField(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="next_occurrence",
        help_text="Occurrence de l'année précédente dont celle-ci est la suite.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CelebrationQuerySet.as_manager()

    class Meta:
        verbose_name = "fête"
        ordering = ["date", "pk"]

    def __str__(self):
        return self.name


class CelebrationItemQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(celebration__family=family)


class CelebrationItem(models.Model):
    """Élément rattaché à une fête. La famille est portée par la fête."""

    celebration = models.ForeignKey(Celebration, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CelebrationItemQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ["created_at", "pk"]

    def _check_person(self, field):
        person = getattr(self, field)
        if person is not None and person.family_id != self.celebration.family_id:
            raise ValidationError({field: "Cette personne n'est pas de la famille."})


class CelebrationTodo(CelebrationItem):
    """Préparatif à faire, coché une fois pour toutes (pas de récurrence).

    Modèle dédié plutôt que `tasks.Task` : une tâche enfant est récurrente
    (jours, période) avec une validation par jour ; un préparatif est unique.
    """

    celebration = models.ForeignKey(Celebration, on_delete=models.CASCADE, related_name="todos")
    title = models.CharField("à faire", max_length=120)
    assignee = models.ForeignKey(
        "families.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="celebration_todos",
        verbose_name="qui s'en occupe",
    )
    done = models.BooleanField(default=False)

    class Meta(CelebrationItem.Meta):
        verbose_name = "préparatif"

    def __str__(self):
        return self.title

    def clean(self):
        self._check_person("assignee")


class GiftItem(CelebrationItem):
    """Cadeau : pour qui, qui l'apporte. Personne de la famille, ou nom libre
    (grand-mère, cousin…) quand la personne n'est pas dans l'app."""

    celebration = models.ForeignKey(Celebration, on_delete=models.CASCADE, related_name="gifts")
    item = models.CharField("cadeau", max_length=120)
    recipient = models.ForeignKey(
        "families.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gifts_received",
        verbose_name="pour",
    )
    recipient_name = models.CharField("pour (autre)", max_length=60, blank=True)
    buyer = models.ForeignKey(
        "families.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gifts_bought",
        verbose_name="apporté par",
    )
    buyer_name = models.CharField("apporté par (autre)", max_length=60, blank=True)
    done = models.BooleanField("acheté", default=False)

    class Meta(CelebrationItem.Meta):
        verbose_name = "cadeau"

    def __str__(self):
        return self.item

    def clean(self):
        self._check_person("recipient")
        self._check_person("buyer")

    @property
    def recipient_display(self) -> str:
        return self.recipient.name if self.recipient else self.recipient_name

    @property
    def buyer_display(self) -> str:
        return self.buyer.name if self.buyer else self.buyer_name

    @property
    def detail(self) -> str:
        """« Pour Lina · apporté par Tata Nora » (parties absentes omises)."""
        parts = []
        if self.recipient_display:
            parts.append(f"Pour {self.recipient_display}")
        if self.buyer_display:
            parts.append(f"apporté par {self.buyer_display}")
        text = " · ".join(parts)
        return text[:1].upper() + text[1:]


class RecipeIdea(CelebrationItem):
    """Idée de recette, texte libre (pas encore d'ingrédients structurés)."""

    celebration = models.ForeignKey(Celebration, on_delete=models.CASCADE, related_name="recipes")
    name = models.CharField("recette", max_length=120)
    notes = models.TextField("notes", blank=True)

    class Meta(CelebrationItem.Meta):
        verbose_name = "idée de recette"
        verbose_name_plural = "idées de recettes"

    def __str__(self):
        return self.name
