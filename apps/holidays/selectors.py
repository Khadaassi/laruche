"""Vacances scolaires en cours."""

import datetime

from .models import SchoolHoliday


def holiday_on(family, day: datetime.date) -> SchoolHoliday | None:
    """Vacances scolaires de la famille couvrant ce jour, ou None."""
    return SchoolHoliday.objects.for_family(family).covering(day).first()
