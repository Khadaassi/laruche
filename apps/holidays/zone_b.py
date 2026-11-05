"""Calendrier officiel des vacances scolaires, zone B (académie de Lille).

Source : arrêté du 22 octobre 2025 (JO du 23 octobre 2025), calendrier 2026-2027.
Bornes **incluses** : du samedi après la classe à la veille de la reprise.
À compléter chaque année quand le calendrier suivant est publié.
"""

import datetime

D = datetime.date

ZONE_B = (
    ("Vacances d'automne", D(2026, 10, 17), D(2026, 11, 1)),
    ("Vacances de fin d'année", D(2026, 12, 19), D(2027, 1, 3)),
    ("Vacances d'hiver", D(2027, 2, 20), D(2027, 3, 7)),
    ("Vacances de printemps", D(2027, 4, 17), D(2027, 5, 2)),
    ("Pont de l'Ascension", D(2027, 5, 6), D(2027, 5, 9)),
    ("Vacances d'été", D(2027, 7, 3), D(2027, 9, 1)),
)
