import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class SharedDisplayDeviceQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)

    def active(self):
        return self.filter(revoked_at__isnull=True)


class SharedDisplayDevice(models.Model):
    """Appareil commun (tablette) autorisé par un parent à afficher la famille.

    Le jeton brut ne vit que dans le cookie de l'appareil ; la base n'en garde
    que l'empreinte SHA-256 (une fuite de la base ne donne accès à aucun écran).
    """

    family = models.ForeignKey(
        "families.Family", on_delete=models.CASCADE, related_name="display_devices"
    )
    name = models.CharField("nom de l'appareil", max_length=60)
    token_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = SharedDisplayDeviceQuerySet.as_manager()

    class Meta:
        verbose_name = "appareil partagé"
        verbose_name_plural = "appareils partagés"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.family})"

    @classmethod
    def create_for(cls, *, family, name, created_by) -> tuple["SharedDisplayDevice", str]:
        """Crée l'appareil et renvoie le jeton brut, à poser en cookie une seule fois."""
        raw = secrets.token_urlsafe(32)
        device = cls.objects.create(
            family=family, name=name, token_hash=hash_token(raw), created_by=created_by
        )
        return device, raw

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def revoke(self) -> None:
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])
