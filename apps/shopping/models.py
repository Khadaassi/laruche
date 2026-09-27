from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.meals.units import Unit, format_quantity


class Origin(models.TextChoices):
    MENU = "menu", "Menu de la semaine"
    MANUAL = "manual", "Ajouté à la main"


class Status(models.TextChoices):
    TO_BUY = "to_buy", "À acheter"
    BOUGHT = "bought", "Acheté"
    AT_HOME = "at_home", "Déjà à la maison"


class ShoppingItemQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)


class ShoppingItem(models.Model):
    """Article de la liste de courses de la famille (une liste par famille).

    - `origin = menu` : ligne calculée par le transfert du menu (quantités
      additionnées). `merge_key` (nom normalisé + grandeur) la retrouve au
      transfert suivant ; `recipes` rappelle pour quelles recettes.
    - `origin = manual` : produit ajouté à la main ; `recurring` le remet
      « à acheter » quand on retire les achats, au lieu de le supprimer.
    - `status = at_home` : « déjà à la maison », hors de la liste active mais
      conservé (l'ingrédient reste au menu, et le transfert suivant le sait).
    """

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="shopping_items"
    )
    name = models.CharField("article", max_length=80)
    quantity = models.DecimalField(
        "quantité",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    unit = models.CharField("unité", max_length=5, choices=Unit.choices, default=Unit.PIECE)
    origin = models.CharField(max_length=6, choices=Origin.choices, default=Origin.MANUAL)
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.TO_BUY)
    recurring = models.BooleanField(
        "revient chaque semaine",
        default=False,
        help_text="Produit habituel : reste sur la liste quand on retire les achats.",
    )
    merge_key = models.CharField(max_length=120, blank=True)
    recipes = models.CharField("pour", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ShoppingItemQuerySet.as_manager()

    class Meta:
        verbose_name = "article de courses"
        verbose_name_plural = "articles de courses"
        ordering = ["created_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["family", "merge_key"],
                condition=models.Q(origin="menu"),
                name="unique_menu_shopping_item",
            ),
            models.CheckConstraint(
                condition=models.Q(origin="manual") | models.Q(recurring=False),
                name="shopping_recurring_only_manual",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__isnull=True) | models.Q(quantity__gt=0),
                name="shopping_quantity_positive",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def quantity_display(self) -> str:
        return format_quantity(self.quantity, self.unit)

    @property
    def is_from_menu(self) -> bool:
        return self.origin == Origin.MENU


class ShoppingTransfer(models.Model):
    """Dernier transfert menu → courses d'une famille (semaine et date)."""

    family = models.OneToOneField(
        "families.Family", on_delete=models.CASCADE, related_name="shopping_transfer"
    )
    week = models.DateField("semaine (lundi)")
    transferred_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "transfert du menu"

    def __str__(self):
        return f"{self.family} — semaine du {self.week}"
