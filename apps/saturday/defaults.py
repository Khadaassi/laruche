"""Catalogue de départ : la roue n'est pas vide à la création d'une famille.

Types d'activités génériques (pas d'adresse), pensés pour une famille de la
région lilloise : musées, parcs, marchés de Noël, stade, ducasse…
Les coûts en étoiles concernent quelques sorties « événement ».
"""

from decimal import Decimal

from .models import Place, SaturdayActivity, Season

DEFAULT_ACTIVITIES = [
    # (nom, saison, lieu, gratuit, prix indicatif, étoiles)
    ("Visite d'un musée", Season.ALL, Place.OUTING, False, Decimal("10"), 0),
    ("Médiathèque et heure du conte", Season.ALL, Place.OUTING, True, None, 0),
    ("Après-midi jeux de société", Season.ALL, Place.HOME, True, None, 0),
    ("Soirée ciné à la maison", Season.ALL, Place.HOME, True, None, 0),
    ("Atelier pâtisserie", Season.ALL, Place.HOME, True, None, 0),
    ("Chasse au trésor à la maison", Season.ALL, Place.HOME, True, None, 0),
    ("Piscine", Season.ALL, Place.OUTING, False, Decimal("12"), 0),
    ("Pique-nique au parc", Season.SPRING, Place.OUTING, True, None, 0),
    ("Ferme pédagogique", Season.SPRING, Place.OUTING, False, Decimal("8"), 0),
    ("Fête foraine", Season.SPRING, Place.OUTING, False, Decimal("20"), 20),
    ("Balade à vélo sur une voie verte", Season.SUMMER, Place.OUTING, True, None, 0),
    ("Parc d'attractions", Season.SUMMER, Place.OUTING, False, Decimal("40"), 50),
    ("Balade en forêt et ramassage de feuilles", Season.AUTUMN, Place.OUTING, True, None, 0),
    ("Match de foot au stade", Season.AUTUMN, Place.OUTING, False, Decimal("30"), 40),
    ("Cirque", Season.WINTER, Place.OUTING, False, Decimal("25"), 30),
    ("Marché de Noël", Season.WINTER, Place.OUTING, True, None, 0),
    ("Patinoire", Season.WINTER, Place.OUTING, False, Decimal("10"), 15),
    ("Cabane en couvertures et lecture", Season.WINTER, Place.HOME, True, None, 0),
]


def seed_default_activities(family, model=SaturdayActivity) -> int:
    """Ajoute le catalogue de départ si la famille n'a encore aucune activité.

    `model` permet l'appel depuis une migration de données (modèle historique).
    """
    if model.objects.filter(family_id=family.pk).exists():
        return 0
    model.objects.bulk_create(
        model(
            family_id=family.pk,
            name=name,
            season=season,
            place=place,
            is_free=is_free,
            price=price,
            star_cost=stars,
        )
        for name, season, place, is_free, price, stars in DEFAULT_ACTIVITIES
    )
    return len(DEFAULT_ACTIVITIES)
