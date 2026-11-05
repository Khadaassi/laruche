"""Pré-remplissage du calendrier officiel."""

from django.db import transaction

from .models import SchoolHoliday
from .zone_b import ZONE_B


@transaction.atomic
def add_zone_b(family) -> int:
    """Ajoute les vacances zone B absentes (mêmes dates = déjà là). Renvoie le nombre ajouté."""
    existing = set(SchoolHoliday.objects.for_family(family).values_list("start_date", "end_date"))
    new = [
        SchoolHoliday(family=family, name=name, start_date=start, end_date=end)
        for name, start, end in ZONE_B
        if (start, end) not in existing
    ]
    SchoolHoliday.objects.bulk_create(new)
    return len(new)
