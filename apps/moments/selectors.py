"""Moments du jour d'une famille (bannières, thème, tâches allégées)."""

import datetime
from dataclasses import dataclass, field

from . import calendar as cal
from .content import FRIDAY_REMINDERS, RAMADAN_GOOD_DEEDS
from .models import MomentSettings, PersonBirthday

EID_COUNTDOWN_DAYS = 30
BIRTHDAY_SOON_DAYS = 7


def settings_for(family) -> MomentSettings:
    """Réglages de la famille (valeurs par défaut si jamais enregistrés, sans écrire)."""
    found = MomentSettings.objects.filter(family=family).first()
    return found or MomentSettings(family=family)


@dataclass
class DayMoments:
    day: datetime.date
    season: str
    is_friday: bool = False
    eid: cal.Eid | None = None
    ramadan_day: int | None = None
    ramadan_length: int | None = None
    next_eid: cal.Eid | None = None
    eid_in_days: int | None = None  # compte à rebours (Ramadan ou 30 derniers jours)
    good_deed: str = ""
    birthdays_today: list = field(default_factory=list)  # [(Person, âge)]
    birthdays_soon: list = field(default_factory=list)  # [(Person, date, jours, âge)]

    @property
    def season_label(self) -> str:
        return cal.SEASON_LABELS[self.season]

    @property
    def friday_reminders(self):
        return FRIDAY_REMINDERS

    @property
    def theme(self) -> str:
        """Ambiance de la page : aïd > ramadan > vendredi > rien (la saison est à part)."""
        if self.eid:
            return "eid"
        if self.ramadan_day:
            return "ramadan"
        if self.is_friday:
            return "friday"
        return ""

    def birthday_of(self, person_id):
        return next((age for p, age in self.birthdays_today if p.pk == person_id), None)


def moments_for(family, day: datetime.date, settings: MomentSettings | None = None) -> DayMoments:
    settings = settings or settings_for(family)
    shift = settings.hijri_shift
    moments = DayMoments(day=day, season=cal.season_of(day), is_friday=day.weekday() == cal.FRIDAY)
    moments.eid = cal.eid_on(day, shift, settings.eid_days)
    ramadan = cal.ramadan_on(day, shift)
    if ramadan:
        period, number = ramadan
        moments.ramadan_day, moments.ramadan_length = number, period.length
        moments.good_deed = RAMADAN_GOOD_DEEDS[(number - 1) % len(RAMADAN_GOOD_DEEDS)]
    if not moments.eid:
        upcoming = cal.next_eid(day, shift)
        if upcoming:
            days_left = (upcoming.date - day).days
            if ramadan or days_left <= EID_COUNTDOWN_DAYS:
                moments.next_eid, moments.eid_in_days = upcoming, days_left
    for birthday in PersonBirthday.objects.filter(person__family=family).select_related("person"):
        when = birthday.next_on_or_after(day)
        if when is None:
            continue
        days_left = (when - day).days
        if days_left == 0:
            moments.birthdays_today.append((birthday.person, birthday.age_on(when)))
        elif days_left <= BIRTHDAY_SOON_DAYS:
            moments.birthdays_soon.append((birthday.person, when, days_left, birthday.age_on(when)))
    moments.birthdays_soon.sort(key=lambda row: row[2])
    return moments


def relaxed_reason(family, day: datetime.date) -> str:
    """Jour « allégé » (seules les tâches obligatoires comptent) : Aïd, ou Ramadan si activé."""
    settings = settings_for(family)
    if cal.eid_on(day, settings.hijri_shift, settings.eid_days):
        return "eid"
    if settings.ramadan_light and cal.ramadan_on(day, settings.hijri_shift):
        return "ramadan"
    return ""
