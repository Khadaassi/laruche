from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """Un appareil abonné aux notifications (navigateur ou appli installée) d'un parent."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.URLField(max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    last_success_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "appareil abonné"

    def __str__(self):
        return f"{self.user} · {self.endpoint[:40]}…"

    def as_subscription_info(self) -> dict:
        return {"endpoint": self.endpoint, "keys": {"p256dh": self.p256dh, "auth": self.auth}}


class NotificationPrefs(models.Model):
    """Ce que le parent veut recevoir (tout activé par défaut, sans ligne)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_prefs"
    )
    dinner = models.BooleanField("dîner pas encore prévu (15 h)", default=True)
    review = models.BooleanField("revue de la semaine (dimanche, 17 h)", default=True)
    day_done = models.BooleanField("un enfant a terminé sa journée", default=True)

    class Meta:
        verbose_name = "préférences de notification"

    def __str__(self):
        return f"Préférences de {self.user}"


class Delivery(models.TextChoices):
    PENDING = "pending", "En attente"
    ACCEPTED = "accepted", "Acceptée par le service push"  # pas la preuve d'un affichage
    FAILED = "failed", "Échec"
    NO_DEVICE = "no_device", "Aucun appareil"
    EXPIRED = "expired", "Trop tard"


class SentNotification(models.Model):
    """File d'envoi et trace anti-doublon : une notification d'un type par clé et par parent.

    La ligne est créée **en attente** avec son contenu ; l'envoi a lieu ensuite (en
    tâche de fond après un cochage, ou pendant la tâche planifiée), avec de nouvelles
    tentatives espacées si le service push échoue, jusqu'à `expires_at`.
    « Acceptée » signifie que le service push a pris le message, pas que le
    téléphone l'a affiché.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=20)
    key = models.CharField(max_length=40)
    sent_at = models.DateTimeField(auto_now_add=True)  # mise en file
    status = models.CharField(
        max_length=10, choices=Delivery.choices, default=Delivery.PENDING, db_index=True
    )
    payload = models.JSONField(default=dict, blank=True)  # title, body, url, tag
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "kind", "key"], name="unique_sent_notification"
            ),
        ]

    def __str__(self):
        return f"{self.kind} · {self.key} · {self.get_status_display()}"


class ScheduledRun(models.Model):
    """Dernière exécution réussie de la tâche planifiée (une ligne par tâche)."""

    name = models.CharField(max_length=30, unique=True)
    last_success_at = models.DateTimeField()

    def __str__(self):
        return f"{self.name} · {self.last_success_at:%d/%m %H:%M}"
