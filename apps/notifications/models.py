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


class SentNotification(models.Model):
    """Trace anti-doublon : une notification d'un type par clé (jour, semaine…) et par parent."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=20)
    key = models.CharField(max_length=40)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "kind", "key"], name="unique_sent_notification"
            ),
        ]

    def __str__(self):
        return f"{self.kind} · {self.key}"
