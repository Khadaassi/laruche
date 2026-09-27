from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction

from .units import Unit, format_quantity, normalize_name


class RecipeQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)


class Recipe(models.Model):
    """Recette de la famille : ingrédients quantifiés et étapes ordonnées."""

    family = models.ForeignKey("families.Family", on_delete=models.CASCADE, related_name="recipes")
    name = models.CharField("nom", max_length=120)
    prep_minutes = models.PositiveSmallIntegerField("préparation (minutes)", null=True, blank=True)
    is_favorite = models.BooleanField("favori", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = RecipeQuerySet.as_manager()

    class Meta:
        verbose_name = "recette"
        ordering = ["-is_favorite", "name", "pk"]

    def __str__(self):
        return self.name

    @transaction.atomic
    def replace_steps(self, texts):
        """Remplace toutes les étapes par `texts`, dans l'ordre (1, 2, 3…)."""
        self.steps.all().delete()
        RecipeStep.objects.bulk_create(
            RecipeStep(recipe=self, position=index, text=text)
            for index, text in enumerate(texts, start=1)
        )


class RecipeItemQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(recipe__family=family)


class RecipeIngredient(models.Model):
    """Ingrédient d'une recette, avec quantité et unité (addition des courses).

    Quantité vide = « à convenance » (sel, poivre) : l'ingrédient part aux
    courses sans quantité.
    """

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="ingredients")
    name = models.CharField("ingrédient", max_length=80)
    quantity = models.DecimalField(
        "quantité",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    unit = models.CharField("unité", max_length=5, choices=Unit.choices, default=Unit.PIECE)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = RecipeItemQuerySet.as_manager()

    class Meta:
        verbose_name = "ingrédient"
        ordering = ["created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__isnull=True) | models.Q(quantity__gt=0),
                name="ingredient_quantity_positive",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def name_key(self) -> str:
        return normalize_name(self.name)

    @property
    def quantity_display(self) -> str:
        return format_quantity(self.quantity, self.unit)


class RecipeStep(models.Model):
    """Étape numérotée d'une recette (liste ordonnée, pas un bloc de texte libre)."""

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="steps")
    position = models.PositiveSmallIntegerField("n°")
    text = models.CharField("étape", max_length=500)

    objects = RecipeItemQuerySet.as_manager()

    class Meta:
        verbose_name = "étape"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["recipe", "position"], name="unique_recipe_step"),
        ]

    def __str__(self):
        return f"{self.position}. {self.text}"


class Meal(models.TextChoices):
    LUNCH = "lunch", "Déjeuner"
    DINNER = "dinner", "Dîner"


class MealKind(models.TextChoices):
    RECIPE = "recipe", "Une recette"
    LEFTOVERS = "leftovers", "Restes"
    OUTSIDE = "outside", "Extérieur"
    FREE = "free", "Autre"


class MealSlotQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)


class MealSlot(models.Model):
    """Un repas du menu (jour + déjeuner/dîner) : une recette ou un repas libre.

    Pas de ligne = rien de prévu. Une recette supprimée disparaît du menu.
    """

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="meal_slots"
    )
    date = models.DateField()
    meal = models.CharField("repas", max_length=6, choices=Meal.choices)
    kind = models.CharField("au menu", max_length=10, choices=MealKind.choices)
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="meal_slots",
        verbose_name="recette",
    )
    note = models.CharField(
        "précision",
        max_length=80,
        blank=True,
        help_text="Restes du couscous, chez mamie, pizza…",
    )

    objects = MealSlotQuerySet.as_manager()

    class Meta:
        verbose_name = "repas du menu"
        verbose_name_plural = "menu"
        ordering = ["date", "-meal"]  # déjeuner (lunch) avant dîner (dinner)
        constraints = [
            models.UniqueConstraint(fields=["family", "date", "meal"], name="unique_meal_slot"),
            models.CheckConstraint(
                condition=(
                    models.Q(kind=MealKind.RECIPE, recipe__isnull=False)
                    | (~models.Q(kind=MealKind.RECIPE) & models.Q(recipe__isnull=True))
                ),
                name="meal_slot_recipe_iff_kind_recipe",
            ),
        ]

    def __str__(self):
        return f"{self.date} {self.get_meal_display()} : {self.label}"

    def clean(self):
        if self.recipe_id and self.recipe.family_id != self.family_id:
            raise ValidationError({"recipe": "Cette recette n'est pas de la famille."})

    @property
    def label(self) -> str:
        """Ce qu'on affiche : le nom de la recette, ou le repas libre et sa précision."""
        if self.kind == MealKind.RECIPE:
            return self.recipe.name
        if self.kind == MealKind.FREE:
            return self.note
        base = self.get_kind_display()
        return f"{base} · {self.note}" if self.note else base
