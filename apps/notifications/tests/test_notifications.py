"""Notifications push : abonnement, préférences, rappels programmés, journée terminée."""

import datetime
import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.meals.models import Meal, MealKind, MealSlot
from apps.notifications.keys import public_key_b64
from apps.notifications.models import (
    Delivery,
    NotificationPrefs,
    PushSubscription,
    ScheduledRun,
    SentNotification,
)
from apps.notifications.services import deliver_pending, enqueue, run_scheduled
from apps.review.models import WeeklyReview
from apps.stars.services import award_day_star
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period

SUB = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "BPkey", "auth": "authkey"}}
THURSDAY_4PM = datetime.datetime(2026, 11, 5, 15, 0, tzinfo=datetime.UTC)  # 16 h Paris
SUNDAY_6PM = datetime.datetime(2026, 11, 8, 17, 0, tzinfo=datetime.UTC)  # 18 h Paris


@mock.patch("apps.notifications.services.webpush")
class NotificationTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.client.force_login(self.parent)

    def subscribe(self):
        return self.client.post(
            reverse("notifications:subscribe"),
            data=json.dumps(SUB),
            content_type="application/json",
            secure=True,
        )

    def test_public_key_is_a_p256_point(self, _push):
        self.assertEqual(len(public_key_b64()), 87)  # 65 octets en base64url

    def test_subscribe_test_and_unsubscribe(self, push):
        self.assertEqual(self.subscribe().status_code, 204)
        self.assertEqual(PushSubscription.objects.get().user, self.parent)
        self.assertEqual(self.post(reverse("notifications:test")).json(), {"delivered": 1})
        payload = json.loads(push.call_args.args[1])
        self.assertEqual(payload["title"], "La Ruche")
        self.client.post(
            reverse("notifications:unsubscribe"),
            data=json.dumps({"endpoint": SUB["endpoint"]}),
            content_type="application/json",
            secure=True,
        )
        self.assertFalse(PushSubscription.objects.exists())

    def test_bad_subscription_and_children_refused(self, _push):
        bad = self.client.post(
            reverse("notifications:subscribe"),
            data="{}",
            content_type="application/json",
            secure=True,
        )
        self.assertEqual(bad.status_code, 400)
        self.client.force_login(self.kid)
        self.subscribe()
        self.assertFalse(PushSubscription.objects.exists())

    def test_expired_subscription_is_removed(self, push):
        from pywebpush import WebPushException

        self.subscribe()
        push.side_effect = WebPushException("gone", response=mock.Mock(status_code=410))
        self.assertEqual(self.post(reverse("notifications:test")).json(), {"delivered": 0})
        self.assertFalse(PushSubscription.objects.exists())

    def test_dinner_reminder_once_and_only_if_missing(self, push):
        self.subscribe()
        with mock.patch("django.utils.timezone.now", return_value=THURSDAY_4PM):
            self.assertEqual(run_scheduled()["dinner"], 1)
            self.assertEqual(run_scheduled()["dinner"], 0)  # pas de doublon
        push.reset_mock()
        SentNotification.objects.all().delete()
        MealSlot.objects.create(
            family=self.family,
            date=datetime.date(2026, 11, 5),
            meal=Meal.DINNER,
            kind=MealKind.LEFTOVERS,
        )
        with mock.patch("django.utils.timezone.now", return_value=THURSDAY_4PM):
            self.assertEqual(run_scheduled()["dinner"], 0)
        push.assert_not_called()

    def test_preferences_are_respected(self, push):
        self.subscribe()
        self.post(reverse("notifications:manage"), {"review": "on"})  # dîner décoché
        self.assertFalse(NotificationPrefs.objects.get(user=self.parent).dinner)
        with mock.patch("django.utils.timezone.now", return_value=THURSDAY_4PM):
            self.assertEqual(run_scheduled()["dinner"], 0)

    def test_sunday_review_until_done(self, _push):
        self.subscribe()
        with mock.patch("django.utils.timezone.now", return_value=SUNDAY_6PM):
            self.assertEqual(run_scheduled()["review"], 1)
        SentNotification.objects.all().delete()
        WeeklyReview.objects.create(family=self.family, week=datetime.date(2026, 11, 9))
        with mock.patch("django.utils.timezone.now", return_value=SUNDAY_6PM):
            self.assertEqual(run_scheduled()["review"], 0)

    @override_settings(PUSH_INLINE=True)
    def test_day_done_notifies_parents(self, push):
        self.subscribe()
        task = Task.objects.create(person=self.kid.person, title="Lit", period=Period.MORNING)
        with mock.patch("django.utils.timezone.now", return_value=THURSDAY_4PM):
            TaskCompletion.objects.create(task=task, date=datetime.date(2026, 11, 5))
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                self.assertTrue(award_day_star(self.kid.person, datetime.date(2026, 11, 5)))
            push.assert_not_called()  # le cochage n'attend pas le service push
            for callback in callbacks:
                callback()
        payload = json.loads(push.call_args.args[1])
        self.assertEqual(payload["title"], "Lina a terminé sa journée")
        self.assertEqual(SentNotification.objects.get().status, Delivery.ACCEPTED)

    def test_failed_push_is_retried_then_given_up(self, push):
        from pywebpush import WebPushException

        self.subscribe()
        push.side_effect = WebPushException("indisponible", response=mock.Mock(status_code=503))
        enqueue(self.parent, "test", "k", title="T", body="B")
        start = timezone.now()
        deliver_pending(start)
        row = SentNotification.objects.get()
        self.assertEqual((row.status, row.attempts), (Delivery.PENDING, 1))
        self.assertEqual(row.last_error, "Service push : 503")
        self.assertEqual(deliver_pending(start)[Delivery.PENDING], 0)  # pas encore l'heure
        push.side_effect = None
        deliver_pending(start + datetime.timedelta(minutes=6))
        row.refresh_from_db()
        self.assertEqual((row.status, row.attempts), (Delivery.ACCEPTED, 2))
        # Échecs répétés : abandon après MAX_ATTEMPTS.
        push.side_effect = WebPushException("indisponible", response=mock.Mock(status_code=503))
        enqueue(self.parent, "test", "k2", title="T", body="B")
        moment = timezone.now()
        for _ in range(6):
            deliver_pending(moment)
            moment += datetime.timedelta(hours=3)
        self.assertEqual(SentNotification.objects.get(key="k2").status, Delivery.FAILED)

    def test_expired_and_deviceless_notifications(self, push):
        enqueue(self.parent, "test", "late", expires_at=timezone.now(), title="T", body="B")
        enqueue(self.parent, "test", "nodevice", title="T", body="B")
        deliver_pending()
        self.assertEqual(SentNotification.objects.get(key="nodevice").status, Delivery.NO_DEVICE)
        self.assertEqual(SentNotification.objects.get(key="late").status, Delivery.EXPIRED)
        push.assert_not_called()

    @override_settings(CRON_TOKEN="jeton-secret")
    def test_cron_endpoint_requires_the_token(self, _push):
        url = reverse("notifications:cron")
        self.client.logout()
        self.assertEqual(self.post(url).status_code, 404)
        self.assertEqual(self.post(url, headers={"Authorization": "Bearer faux"}).status_code, 404)
        self.assertFalse(ScheduledRun.objects.exists())
        ok = self.post(url, headers={"Authorization": "Bearer jeton-secret"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(set(ok.json()), {"dinner", "review", "delivery", "maintenance"})
        self.assertTrue(ScheduledRun.objects.filter(name="daily").exists())
        self.client.force_login(self.parent)
        self.assertContains(self.get(reverse("notifications:manage")), "Dernière exécution réussie")
        self.assertEqual(ok.json()["maintenance"]["families"], 1)
        old_url = self.post(
            "/taches-planifiees/notifications/", headers={"Authorization": "Bearer jeton-secret"}
        )
        self.assertEqual(old_url.status_code, 200)

    def test_cron_disabled_without_token(self, _push):
        self.assertEqual(self.post(reverse("notifications:cron")).status_code, 404)
        self.assertContains(self.get(reverse("notifications:manage")), "Configuration incomplète")
