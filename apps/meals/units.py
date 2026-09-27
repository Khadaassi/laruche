"""Unités des ingrédients, conversion simple et normalisation des noms.

Partagé par les recettes (saisie) et la liste de courses (addition des
quantités). Conversion seulement à l'intérieur d'une même grandeur :
masse (g, kg) et volume (ml, cl, l). Les autres unités (pièce, cuillère,
paquet, boîte) ne se convertissent pas : une cuillère de farine n'a pas de
poids fiable, on garde alors deux lignes séparées.
"""

import unicodedata
from decimal import Decimal

from django.db import models


class Unit(models.TextChoices):
    PIECE = "piece", "pièce(s)"
    GRAM = "g", "g"
    KILOGRAM = "kg", "kg"
    MILLILITRE = "ml", "ml"
    CENTILITRE = "cl", "cl"
    LITRE = "l", "l"
    TABLESPOON = "tbsp", "c. à soupe"
    TEASPOON = "tsp", "c. à café"
    PACK = "pack", "paquet(s)"
    CAN = "can", "boîte(s)"


MASS, VOLUME = "mass", "volume"

# Unité → (grandeur, facteur vers l'unité de base : g ou ml).
CONVERTIBLE = {
    Unit.GRAM: (MASS, 1),
    Unit.KILOGRAM: (MASS, 1000),
    Unit.MILLILITRE: (VOLUME, 1),
    Unit.CENTILITRE: (VOLUME, 10),
    Unit.LITRE: (VOLUME, 1000),
}

# Libellés courts après un nombre (singulier, pluriel).
SHORT_LABELS = {
    Unit.TABLESPOON: ("c. à soupe", "c. à soupe"),
    Unit.TEASPOON: ("c. à café", "c. à café"),
    Unit.PACK: ("paquet", "paquets"),
    Unit.CAN: ("boîte", "boîtes"),
}


def normalize_name(name: str) -> str:
    """Clé de regroupement d'un ingrédient : sans accents, casse ni espaces en trop.

    « Crème fraîche », « creme  fraiche » et « CRÈME FRAÎCHE » se regroupent.
    Pas de gestion des pluriels (« tomate » ≠ « tomates ») : trop de mots
    invariables (ananas, pois, radis) pour une règle simple.
    """
    text = (name or "").replace("œ", "oe").replace("Œ", "oe").replace("æ", "ae")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.casefold().split())


def dimension(unit: str) -> str:
    """Grandeur d'une unité : masse, volume, ou l'unité elle-même si non convertible."""
    return CONVERTIBLE[unit][0] if unit in CONVERTIBLE else unit


def to_base(quantity: Decimal, unit: str) -> Decimal:
    """Quantité dans l'unité de base de sa grandeur (g, ml, ou inchangée)."""
    factor = CONVERTIBLE[unit][1] if unit in CONVERTIBLE else 1
    return quantity * factor


def from_base(total: Decimal, dim: str, units: set) -> tuple[Decimal, str]:
    """Exprime une somme (en unité de base) dans une unité lisible.

    Toutes les lignes dans la même unité : on la garde (20 cl + 25 cl = 45 cl).
    Unités mélangées : kg / l à partir de 1000, cl pour un volume rond, sinon g / ml.
    """
    if len(units) == 1:
        unit = next(iter(units))
        factor = CONVERTIBLE[unit][1] if unit in CONVERTIBLE else 1
        return total / factor, unit
    if dim == MASS:
        return (total / 1000, Unit.KILOGRAM) if total >= 1000 else (total, Unit.GRAM)
    if dim == VOLUME:
        if total >= 1000:
            return total / 1000, Unit.LITRE
        if total % 10 == 0:
            return total / 10, Unit.CENTILITRE
        return total, Unit.MILLILITRE
    return total, dim


def format_number(value: Decimal) -> str:
    """1.50 → « 1,5 » ; 2.00 → « 2 »."""
    text = format(value.quantize(Decimal("0.01")).normalize(), "f")
    return text.replace(".", ",")


def format_quantity(quantity, unit: str) -> str:
    """« 3 », « 250 g », « 1,5 kg », « 2 c. à soupe », « 1 paquet » ; vide sans quantité."""
    if quantity is None:
        return ""
    number = format_number(Decimal(quantity))
    if unit == Unit.PIECE:
        return number
    if unit in SHORT_LABELS:
        singular, plural = SHORT_LABELS[unit]
        return f"{number} {plural if Decimal(quantity) > 1 else singular}"
    return f"{number} {unit}"
