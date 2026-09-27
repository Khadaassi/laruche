import re
import secrets

from django.conf import settings
from django.db import models

# Alphabet des codes générés : sans 0/O ni 1/I/L, pour être dicté sans erreur.
INVITE_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
INVITE_CODE_LENGTH = 10


def normalize_invite_code(raw: str) -> str:
    """Majuscules, sans espaces ni tirets : « abcd-1234 » == « ABCD 1234 »."""
    return re.sub(r"[\s\-]", "", raw or "").upper()


def generate_invite_code() -> str:
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


class Role(models.TextChoices):
    """Rôle d'un membre. Pilote les permissions (voir permissions/SKILL.md)."""

    PARENT = "parent", "Parent"
    CHILD = "child", "Enfant"


class AvatarColor(models.TextChoices):
    """Couleurs d'avatar, toutes issues des tokens de la charte.

    `sage` est exclu : il signifie « validé » et ne doit pas servir d'identité.
    """

    TERRACOTTA = "terracotta", "Terracotta"
    HONEY = "honey", "Miel"
    HONEY_DARK = "honey_dark", "Miel foncé"
    INK_SOFT = "ink_soft", "Brun"


# Classes complètes (et non construites) pour que Tailwind les détecte.
# Couple fond/texte conforme aux contrastes de design-system/SKILL.md.
AVATAR_CLASSES = {
    AvatarColor.TERRACOTTA: "bg-terracotta text-surface-0",
    AvatarColor.HONEY: "bg-honey text-ink",
    AvatarColor.HONEY_DARK: "bg-honey-dark text-ink",
    AvatarColor.INK_SOFT: "bg-ink-soft text-surface-0",
}


class Family(models.Model):
    name = models.CharField("nom", max_length=80)
    invite_code = models.CharField("code d'invitation", max_length=32, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "famille"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.invite_code = normalize_invite_code(self.invite_code) or generate_invite_code()
        super().save(*args, **kwargs)


class FamilyMembership(models.Model):
    """Rattache un compte à sa famille, avec son rôle.

    Un compte appartient à une seule famille (OneToOne) : la famille de la
    requête est donc toujours non ambiguë.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership"
    )
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField("rôle", max_length=10, choices=Role.choices)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "appartenance"
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} → {self.family} ({self.get_role_display()})"

    @property
    def is_parent(self) -> bool:
        return self.role == Role.PARENT


class PersonQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)

    def children(self):
        return self.filter(role=Role.CHILD)


class Person(models.Model):
    """Un membre tel qu'affiché dans l'app (colonne, avatar, tâches).

    Lié à un compte s'il se connecte, ou non (jeune enfant sans compte).
    """

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="people")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="person",
    )
    name = models.CharField("prénom", max_length=40)
    avatar_color = models.CharField("couleur d'avatar", max_length=20, choices=AvatarColor.choices)
    role = models.CharField("rôle affiché", max_length=10, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PersonQuerySet.as_manager()

    class Meta:
        verbose_name = "personne"
        ordering = ["created_at", "pk"]

    def __str__(self):
        return self.name

    @property
    def initial(self) -> str:
        return self.name[:1].upper()

    @property
    def avatar_classes(self) -> str:
        return AVATAR_CLASSES.get(self.avatar_color, AVATAR_CLASSES[AvatarColor.TERRACOTTA])

    @property
    def is_child(self) -> bool:
        return self.role == Role.CHILD


def next_avatar_color(family) -> str:
    """Couleur suivante dans le cycle, pour distinguer les membres d'office."""
    colors = list(AvatarColor.values)
    return colors[family.people.count() % len(colors)]
