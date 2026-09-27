"""Menu d'une semaine, jour par jour (déjeuner, dîner).

Partagé par la vue parent (mobile) et l'écran partagé (lecture seule).
"""

import datetime
from dataclasses import dataclass

from django.utils import timezone

from .models import Meal, MealSlot


@dataclass
class MenuDay:
    date: datetime.date
    is_today: bool
    lunch: MealSlot | None = None
    dinner: MealSlot | None = None

    @property
    def meals(self):
        """[(Meal, repas ou None)], déjeuner puis dîner."""
        return [(Meal.LUNCH, self.lunch), (Meal.DINNER, self.dinner)]


def build_menu_week(family, monday: datetime.date) -> dict:
    today = timezone.localdate()
    days = {
        monday + datetime.timedelta(days=offset): MenuDay(
            date=monday + datetime.timedelta(days=offset),
            is_today=monday + datetime.timedelta(days=offset) == today,
        )
        for offset in range(7)
    }
    for slot in (
        MealSlot.objects.for_family(family).filter(date__in=days.keys()).select_related("recipe")
    ):
        setattr(days[slot.date], "lunch" if slot.meal == Meal.LUNCH else "dinner", slot)
    return {
        "monday": monday,
        "sunday": monday + datetime.timedelta(days=6),
        "days": list(days.values()),
        "previous_monday": monday - datetime.timedelta(days=7),
        "next_monday": monday + datetime.timedelta(days=7),
        "is_current_week": monday <= today < monday + datetime.timedelta(days=7),
    }


def dinner_of(family, day: datetime.date) -> MealSlot | None:
    """Le dîner prévu ce jour-là (carte « Ce soir » de l'accueil parent)."""
    return (
        MealSlot.objects.for_family(family)
        .filter(date=day, meal=Meal.DINNER)
        .select_related("recipe")
        .first()
    )
