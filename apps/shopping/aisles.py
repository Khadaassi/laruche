"""Rayons du magasin : devinés depuis le nom de l'article, modifiables.

Ordre = parcours habituel d'un supermarché (frais d'abord, surgelés à la fin).
Devinette par mots-clés (nom normalisé : sans accents ni casse) ; rien trouvé → « Autres ».
"""

import functools
import re

from django.db import models

from apps.meals.units import normalize_name


class Aisle(models.TextChoices):
    PRODUCE = "produce", "Fruits et légumes"
    BAKERY = "bakery", "Boulangerie"
    MEAT_FISH = "meat", "Viande et poisson"
    DAIRY = "dairy", "Crèmerie et œufs"
    SAVORY = "savory", "Épicerie salée"
    SWEET = "sweet", "Épicerie sucrée"
    DRINKS = "drinks", "Boissons"
    FROZEN = "frozen", "Surgelés"
    HYGIENE = "hygiene", "Hygiène"
    CLEANING = "cleaning", "Entretien"
    OTHER = "other", "Autres"


STORE_ORDER = list(Aisle.values)

KEYWORDS = {
    Aisle.FROZEN: ("surgele", "glace", "congele"),
    Aisle.PRODUCE: (
        "tomate",
        "oignon",
        "ail",
        "carotte",
        "courgette",
        "aubergine",
        "poivron",
        "pomme de terre",
        "patate",
        "poireau",
        "celeri",
        "salade",
        "concombre",
        "citron",
        "orange",
        "pomme",
        "poire",
        "banane",
        "raisin",
        "fraise",
        "avocat",
        "brocoli",
        "chou",
        "navet",
        "potiron",
        "butternut",
        "courge",
        "epinard",
        "haricots verts",
        "champignon",
        "persil",
        "coriandre",
        "menthe",
        "basilic",
        "aneth",
        "ciboulette",
        "thym",
        "laurier",
        "gingembre frais",
        "echalote",
        "fruit",
        "legume",
        "clementine",
        "kiwi",
        "melon",
        "pasteque",
        "grenade",
        "radis",
        "betterave",
    ),
    Aisle.BAKERY: ("pain", "baguette", "brioche", "croissant", "viennoiserie", "pate a pizza"),
    Aisle.MEAT_FISH: (
        "poulet",
        "dinde",
        "boeuf",
        "agneau",
        "veau",
        "viande",
        "hache",
        "kefta",
        "merguez",
        "saumon",
        "cabillaud",
        "colin",
        "poisson",
        "crevette",
        "thon frais",
        "escalope",
        "cuisse",
    ),
    Aisle.DAIRY: (
        "lait",
        "yaourt",
        "fromage",
        "beurre",
        "creme",
        "oeuf",
        "mozzarella",
        "parmesan",
        "emmental",
        "feta",
        "chevre",
        "skyr",
        "fromage blanc",
    ),
    Aisle.DRINKS: ("eau", "jus", "sirop", "the", "cafe", "boisson", "soda", "infusion"),
    Aisle.HYGIENE: (
        "dentifrice",
        "brosse a dents",
        "shampooing",
        "gel douche",
        "savon",
        "deodorant",
        "coton",
        "couche",
        "mouchoir",
        "papier toilette",
        "serviette hygienique",
        "creme solaire",
    ),
    Aisle.CLEANING: (
        "lessive",
        "liquide vaisselle",
        "eponge",
        "javel",
        "nettoyant",
        "sac poubelle",
        "sacs poubelle",
        "adoucissant",
        "pastille lave",
        "essuie-tout",
        "sopalin",
        "film alimentaire",
        "aluminium",
    ),
    Aisle.SWEET: (
        "sucre",
        "chocolat",
        "biscuit",
        "gateau",
        "confiture",
        "miel",
        "datte",
        "cereale",
        "compote",
        "levure",
        "vanille",
        "cacao",
        "pate a tartiner",
        "farine",
        "maizena",
        "fecule",
    ),
    Aisle.SAVORY: (
        "pate",
        "spaghetti",
        "penne",
        "lasagne",
        "tagliatelle",
        "fusilli",
        "riz",
        "semoule",
        "quinoa",
        "lentille",
        "pois chiche",
        "haricot",
        "feve",
        "conserve",
        "boite",
        "thon",
        "sardine",
        "huile",
        "vinaigre",
        "moutarde",
        "sel",
        "poivre",
        "epice",
        "cumin",
        "paprika",
        "curcuma",
        "curry",
        "ras el hanout",
        "cannelle",
        "gingembre",
        "bouillon",
        "coulis",
        "concentre",
        "sauce",
        "olive",
        "mais",
        "vermicelle",
        "gnocchi",
        "nouille",
        "pesto",
        "noix",
        "amande",
        "chips",
        "soja",
        "sesame",
        "origan",
        "herbes de provence",
        "muscade",
        "safran",
    ),
}

# Ordre de test : les cas particuliers (surgelés, « pâte à pizza », « crème solaire »…)
# avant les catégories larges.
CHECK_ORDER = [
    Aisle.FROZEN,
    Aisle.HYGIENE,
    Aisle.CLEANING,
    Aisle.BAKERY,
    Aisle.MEAT_FISH,
    Aisle.DAIRY,
    Aisle.DRINKS,
    Aisle.SWEET,
    Aisle.PRODUCE,
    Aisle.SAVORY,
]


# Cas où le mot-clé tromperait (« lait de coco » n'est pas au rayon crèmerie).
EXCEPTIONS = {
    "lait de coco": Aisle.SAVORY,
    "lait vegetal": Aisle.DAIRY,
    "creme vegetale": Aisle.DAIRY,
    "noix de coco": Aisle.SWEET,
    # Conserves et bouillons : rayon épicerie, même avec « tomate », « légumes » ou « bœuf ».
    "bouillon": Aisle.SAVORY,
    "concentre": Aisle.SAVORY,
    "coulis": Aisle.SAVORY,
    "concassee": Aisle.SAVORY,
    "en boite": Aisle.SAVORY,
    "piment": Aisle.SAVORY,
}


@functools.cache
def _pattern(keyword: str) -> re.Pattern:
    # En début de mot : « eau » ne doit pas trouver « poireau » ni « gâteau ».
    return re.compile(r"(?<![a-z])" + re.escape(keyword))


def guess_aisle(name: str) -> str:
    text = normalize_name(name)
    for words, aisle in EXCEPTIONS.items():
        if _pattern(words).search(text):
            return aisle
    for aisle in CHECK_ORDER:
        if any(_pattern(keyword).search(text) for keyword in KEYWORDS[aisle]):
            return aisle
    return Aisle.OTHER
