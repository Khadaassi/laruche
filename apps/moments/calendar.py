"""Calendrier : saisons, vendredi, Ramadan et Aïd (dates hégiriennes Umm al-Qura).

Aucune base : tout se calcule. Les dates islamiques sont **estimées** (calcul
astronomique) ; le réglage `hijri_shift` de la famille les décale si besoin.
"""

import datetime
from dataclasses import dataclass

from hijridate import Gregorian, Hijri

FRIDAY = 4

AUTUMN, WINTER, SPRING, SUMMER = "autumn", "winter", "spring", "summer"
SEASON_LABELS = {AUTUMN: "Automne", WINTER: "Hiver", SPRING: "Printemps", SUMMER: "Été"}

EID_FITR = "Aïd al-Fitr"
EID_ADHA = "Aïd al-Adha"


def season_of(day: datetime.date) -> str:
    """Saison astronomique approchée (21 mars, 21 juin, 23 septembre, 21 décembre)."""
    md = (day.month, day.day)
    if (3, 21) <= md < (6, 21):
        return SPRING
    if (6, 21) <= md < (9, 23):
        return SUMMER
    if (9, 23) <= md < (12, 21):
        return AUTUMN
    return WINTER


@dataclass(frozen=True)
class Ramadan:
    start: datetime.date
    end: datetime.date  # dernier jour de jeûne (veille de l'Aïd al-Fitr)

    @property
    def length(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class Eid:
    name: str
    date: datetime.date


def _greg(hy, hm, hd) -> datetime.date:
    return Hijri(hy, hm, hd).to_gregorian()


def _hijri_year(day: datetime.date) -> int:
    return Gregorian(day.year, day.month, day.day).to_hijri().year


def ramadans_around(day: datetime.date, shift: int = 0) -> list[Ramadan]:
    shift_days = datetime.timedelta(days=shift)
    year = _hijri_year(day)
    result = []
    for hy in (year - 1, year, year + 1):
        start = _greg(hy, 9, 1) + shift_days
        fitr = _greg(hy, 10, 1) + shift_days
        result.append(Ramadan(start, fitr - datetime.timedelta(days=1)))
    return result


def eids_around(day: datetime.date, shift: int = 0) -> list[Eid]:
    shift_days = datetime.timedelta(days=shift)
    year = _hijri_year(day)
    eids = []
    for hy in (year - 1, year, year + 1):
        eids.append(Eid(EID_FITR, _greg(hy, 10, 1) + shift_days))
        eids.append(Eid(EID_ADHA, _greg(hy, 12, 10) + shift_days))
    return sorted(eids, key=lambda e: e.date)


def ramadan_on(day: datetime.date, shift: int = 0) -> tuple[Ramadan, int] | None:
    """(Ramadan, n° du jour) si `day` est un jour de Ramadan, sinon None."""
    for ramadan in ramadans_around(day, shift):
        if ramadan.start <= day <= ramadan.end:
            return ramadan, (day - ramadan.start).days + 1
    return None


def eid_on(day: datetime.date, shift: int = 0, days: int = 1) -> Eid | None:
    """L'Aïd fêté ce jour-là (sur `days` jours à partir du premier), sinon None."""
    for eid in eids_around(day, shift):
        if eid.date <= day < eid.date + datetime.timedelta(days=days):
            return eid
    return None


def next_eid(day: datetime.date, shift: int = 0) -> Eid | None:
    """Prochain Aïd strictement après `day`."""
    return next((e for e in eids_around(day, shift) if e.date > day), None)
