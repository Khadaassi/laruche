"""Maintenance quotidienne, lancée par la tâche planifiée (jamais par l'affichage d'une page).

Tout est idempotent : relancer ne change rien. Les pages restent justes sans elle
(au pire, un rattrapage arrive à la prochaine exécution) :
- samedis passés : plan validé → historique, tirage non validé → supprimé ;
- étoiles oubliées des 7 derniers jours (journée devenue complète autrement) ;
- fêtes annuelles passées reportées à l'année suivante.
"""

import datetime

from apps.celebrations.services import roll_over_recurring
from apps.families.models import Family
from apps.saturday.draw import close_past_plans
from apps.stars.services import award_missing_day_stars


def run_daily(today: datetime.date) -> dict:
    stars = rolled = 0
    families = list(Family.objects.all())
    for family in families:
        close_past_plans(family, today)
        stars += award_missing_day_stars(family, today)
        rolled += len(roll_over_recurring(family, today))
    return {"families": len(families), "stars": stars, "celebrations": rolled}
