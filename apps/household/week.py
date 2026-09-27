"""Assemblage du semainier : rendez-vous (grille horaire), puis, pour la
journée : fêtes, absences, école, ménage et dîner.

Partagé par la vue parent et l'écran partagé (lecture seule).
"""

import datetime
from dataclasses import dataclass, field

from django.utils import timezone

from apps.absences.selectors import absences_range
from apps.agenda.grid import HOURS, SLOTS, events_by_day, layout_day
from apps.celebrations.models import Celebration
from apps.celebrations.services import roll_over_recurring
from apps.families.models import Person
from apps.meals.models import Meal, MealSlot
from apps.school.selectors import school_days_range

from .selectors import chores_by_day


@dataclass
class DayPlan:
    date: datetime.date
    is_today: bool
    chores: list = field(default_factory=list)
    school: list = field(default_factory=list)  # [(enfant, SchoolDay)]
    celebrations: list = field(default_factory=list)
    absences: list = field(default_factory=list)  # [Absence] (famille puis personnes)
    blocks: list = field(default_factory=list)  # [agenda.grid.Block], ordre horaire
    lanes: int = 1
    dinner: object = None  # meals.MealSlot du soir
    is_selected: bool = False

    @property
    def is_empty(self) -> bool:
        return not (self.chores or self.school or self.celebrations or self.absences or self.blocks)

    @property
    def has_all_day(self) -> bool:
        """Quelque chose à montrer dans le bandeau « journée » (hors rendez-vous)."""
        return bool(self.chores or self.celebrations or self.absences)


def build_week(family, monday: datetime.date, selected: datetime.date | None = None) -> dict:
    """Semaine du lundi `monday`. `selected` : jour détaillé (défaut : aujourd'hui
    s'il est dans la semaine, sinon le lundi)."""
    today = timezone.localdate()
    week_days = [monday + datetime.timedelta(days=i) for i in range(7)]
    if selected not in week_days:
        selected = today if today in week_days else monday
    roll_over_recurring(family, today)
    children = list(Person.objects.for_family(family).children())
    chores = chores_by_day(family, monday, 7)
    school = school_days_range(family, monday, 7, people=children)
    celebrations = {}
    for celebration in Celebration.objects.for_family(family).filter(
        date__gte=monday, date__lt=monday + datetime.timedelta(days=7)
    ):
        celebrations.setdefault(celebration.date, []).append(celebration)
    absences = absences_range(family, monday, 7)
    events = events_by_day(family, monday, 7)
    dinners = {
        slot.date: slot
        for slot in MealSlot.objects.for_family(family)
        .filter(date__in=week_days, meal=Meal.DINNER)
        .select_related("recipe")
    }

    days = []
    for offset in range(7):
        day = monday + datetime.timedelta(days=offset)
        blocks, lanes = layout_day(events[day])
        absent = absences[day]
        days.append(
            DayPlan(
                date=day,
                is_today=day == today,
                chores=chores[day],
                school=[(c, school[day][c.pk]) for c in children if c.pk in school[day]],
                celebrations=celebrations.get(day, []),
                absences=[a for a in [absent.family_wide, *absent.people.values()] if a],
                blocks=blocks,
                lanes=lanes,
                dinner=dinners.get(day),
                is_selected=day == selected,
            )
        )
    return {
        "monday": monday,
        "sunday": monday + datetime.timedelta(days=6),
        "days": days,
        "previous_monday": monday - datetime.timedelta(days=7),
        "next_monday": monday + datetime.timedelta(days=7),
        "is_current_week": monday <= today < monday + datetime.timedelta(days=7),
        "selected_day": next(d for d in days if d.is_selected),
        "hours": HOURS,
        "slots": SLOTS,
    }
