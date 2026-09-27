"""Récurrence annuelle des fêtes.

Pas de tâche planifiée (l'offre gratuite de Render n'en a pas) : le report
est paresseux. `roll_over_recurring` est appelé par les vues qui listent des
fêtes (accueil, fêtes, semainier, écran partagé). Il est idempotent : une
occurrence n'a qu'une seule suite (`previous` est un OneToOne).
"""

import datetime

from django.db import IntegrityError, transaction

from .models import Celebration, RecipeIdea


def same_day_in_year(day: datetime.date, year: int) -> datetime.date:
    """Même jour/mois l'année `year` ; un 29 février devient le 28 hors bissextile."""
    try:
        return day.replace(year=year)
    except ValueError:
        return day.replace(year=year, day=28)


def next_date(day: datetime.date, today: datetime.date) -> datetime.date:
    """Prochaine date anniversaire strictement après `day` et au plus tôt aujourd'hui.

    Si l'app n'a pas été ouverte depuis plus d'un an, on saute les années
    manquées plutôt que de créer des fêtes déjà passées.
    """
    year = day.year + 1
    candidate = same_day_in_year(day, year)
    while candidate < today:
        year += 1
        candidate = same_day_in_year(day, year)
    return candidate


def roll_over_recurring(family, today: datetime.date) -> list[Celebration]:
    """Crée l'occurrence suivante de chaque fête annuelle passée qui n'en a pas.

    Ce qui est repris : nom, récurrence et **idées de recettes** (souvent les
    mêmes d'une année sur l'autre, utiles comme point de départ). Ce qui
    repart de zéro : **préparatifs** (nouvelle liste vierge) et **cadeaux**
    (propres à chaque année).
    """
    created = []
    due = Celebration.objects.for_family(family).filter(
        recurs_yearly=True, date__lt=today, next_occurrence__isnull=True
    )
    for past in due:
        try:
            with transaction.atomic():
                following = Celebration.objects.create(
                    family=past.family,
                    name=past.name,
                    date=next_date(past.date, today),
                    recurs_yearly=True,
                    previous=past,
                )
                RecipeIdea.objects.bulk_create(
                    RecipeIdea(celebration=following, name=r.name, notes=r.notes)
                    for r in past.recipes.all()
                )
        except IntegrityError:
            continue  # déjà reportée par une requête concurrente
        created.append(following)
    return created
