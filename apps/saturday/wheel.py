"""Géométrie SVG de la roue (calculée côté serveur : aucun style inline, CSP stricte).

La roue est centrée sur l'origine (viewBox -100 -100 200 200), 0° en haut, sens
horaire. Le pointeur est en haut : la rotation finale amène le milieu du
secteur tiré sous le pointeur, après plusieurs tours complets.
"""

import math
import secrets
from dataclasses import dataclass

RADIUS = 95
LABEL_RADIUS = 56
MAX_SEGMENTS = 8
FULL_TURNS = 5
FILLS = ("fill-honey", "fill-surface-0", "fill-honey-dark", "fill-surface-0")


@dataclass(frozen=True)
class Segment:
    path: str
    label: str
    fill: str
    label_transform: str


def _point(angle_deg: float, radius: float) -> str:
    rad = math.radians(angle_deg)
    return f"{radius * math.sin(rad):.2f} {-radius * math.cos(rad):.2f}"


def _short(name: str, limit: int = 16) -> str:
    return name if len(name) <= limit else name[: limit - 1].rstrip() + "…"


def _label_transform(middle: float) -> str:
    """Libellé le long du rayon, jamais à l'envers (moitié gauche retournée)."""
    if 180 < middle < 360:
        return f"rotate({middle + 90:.2f}) translate({-LABEL_RADIUS} 0)"
    return f"rotate({middle - 90:.2f}) translate({LABEL_RADIUS} 0)"


def _fill(index: int, count: int) -> str:
    """Alternance de tokens ; le dernier secteur ne reprend pas la couleur du premier."""
    fill = FILLS[index % len(FILLS)]
    if index == count - 1 and index and fill == FILLS[0]:
        return "fill-honey-dark"
    return fill


def build_wheel(candidates, chosen, rng=None, decor=()) -> dict:
    """Secteurs (jusqu'à 8, dont une seule fois l'activité tirée) et rotation finale.

    `decor` : autres activités de la saison, pour garnir la roue quand peu
    d'activités sont éligibles. Purement visuel : le résultat est déjà tiré.
    """
    rng = rng or secrets.SystemRandom()
    others = [a.name for a in candidates if a.name != chosen.name]
    rng.shuffle(others)
    fillers = [a.name for a in decor if a.name != chosen.name and a.name not in others]
    rng.shuffle(fillers)
    names = list(dict.fromkeys(others + fillers))[: MAX_SEGMENTS - 1] + [chosen.name]
    rng.shuffle(names)
    # Au moins 4 secteurs pour que la roue ressemble à une roue.
    while len(names) < 4:
        names = names + names
    step = 360 / len(names)
    segments = []
    for i, name in enumerate(names):
        start, end = i * step, (i + 1) * step
        large = 1 if step > 180 else 0
        path = (
            f"M0 0 L{_point(start, RADIUS)} A{RADIUS} {RADIUS} 0 {large} 1 {_point(end, RADIUS)} Z"
        )
        middle = start + step / 2
        segments.append(
            Segment(
                path=path,
                label=_short(name),
                fill=_fill(i, len(names)),
                label_transform=_label_transform(middle),
            )
        )
    index = names.index(chosen.name)
    middle = index * step + step / 2
    rotation = FULL_TURNS * 360 + (360 - middle) % 360
    return {"segments": segments, "rotation": round(rotation, 2)}
