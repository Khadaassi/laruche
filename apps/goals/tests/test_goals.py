"""Mon année : vision board privé, petits pas, journal, tirelire, proches."""

import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.services import promote_to_parent
from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.goals.models import Contact, Entry, Goal, Step, StepLog
from apps.goals.selectors import goal_states, year_calendar
from apps.goals.services import default_year, ensure_vision

TODAY = datetime.date(2026, 11, 5)  # jeudi
NOW = datetime.datetime(2026, 11, 5, 9, 0, tzinfo=datetime.UTC)


@mock.patch("django.utils.timezone.now", return_value=NOW)
class GoalsTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.me = join(self.family, "Khadija")
        self.partner = join(self.family, "Lhousseine")
        promote_to_parent(self.partner.membership)  # deux parents dans la famille
        self.client.force_login(self.me)

    def goal(self, title):
        return Goal.objects.get(user=self.me, title=title)

    def test_default_year_and_seed(self, _now):
        self.assertEqual(default_year(TODAY), 2027)
        self.assertEqual(default_year(datetime.date(2027, 3, 1)), 2027)
        page = self.get(reverse("goals:board"))
        self.assertContains(page, "Vision board 2027")
        self.assertContains(page, "Économiser pour la Omra")
        self.assertEqual(Goal.objects.filter(user=self.me, year=2027).count(), 9)
        self.get(reverse("goals:board"))
        self.assertEqual(Goal.objects.filter(user=self.me).count(), 9)

    def test_private_to_each_parent(self, _now):
        ensure_vision(self.me, 2027)
        mine = self.goal("Bouger chaque jour")
        self.client.force_login(self.partner)
        self.assertEqual(self.get(reverse("goals:detail", args=[mine.pk])).status_code, 404)
        step = mine.steps.first()
        self.assertEqual(
            self.post(reverse("goals:log_step", args=[step.pk]), {"value": "30"}).status_code, 404
        )
        self.assertNotContains(self.get(reverse("tasks:home")), "Lire le Coran")

    def test_children_have_no_access(self, _now):
        kid = join(self.family, "Aliyah")
        self.client.force_login(kid)
        self.assertNotEqual(self.get(reverse("goals:board")).status_code, 200)

    def test_check_and_count_steps(self, _now):
        ensure_vision(self.me, 2027)
        move = self.goal("Bouger chaque jour").steps.get()
        water = self.goal("Prendre soin de ma santé").steps.get(title__startswith="Boire")
        self.htmx_post(reverse("goals:log_step", args=[move.pk]), {"value": "20"})
        self.htmx_post(reverse("goals:log_step", args=[water.pk]), {"done": "on"})
        states = {s.goal.title: s for s in goal_states(Goal.objects.mine(self.me, 2027), TODAY)}
        move_state = states["Bouger chaque jour"].steps[0]
        self.assertEqual(move_state.today_value, 20)
        self.assertFalse(move_state.done_today)  # 20 < 30 minutes
        self.htmx_post(reverse("goals:log_step", args=[move.pk]), {"value": "35"})
        self.assertEqual(StepLog.objects.get(step=move).value, 35)
        self.htmx_post(reverse("goals:log_step", args=[water.pk]), {})
        self.assertFalse(StepLog.objects.filter(step=water).exists())

    def test_weekly_step_disappears_once_reached(self, _now):
        ensure_vision(self.me, 2027)
        me_time = self.goal("Me réserver du temps").steps.get()
        StepLog.objects.create(step=me_time, date=TODAY - datetime.timedelta(days=2))
        state = goal_states([me_time.goal], TODAY)[0].steps[0]
        self.assertTrue(state.week_ok)
        self.assertFalse(state.show_today)

    def test_savings_and_journal(self, _now):
        ensure_vision(self.me, 2027)
        omra = self.goal("Économiser pour la Omra")
        omra.savings_target = Decimal("4000")
        omra.save()
        self.post(reverse("goals:add_entry", args=[omra.pk]), {"text": "Virement", "amount": "400"})
        state = goal_states([omra], TODAY)[0]
        self.assertEqual(state.saved, Decimal("400"))
        self.assertEqual(state.savings_percent, 10)
        self.assertContains(self.get(reverse("goals:detail", args=[omra.pk])), "400 € sur 4000 €")
        work = self.goal("M'épanouir au travail")
        self.post(reverse("goals:add_entry", args=[work.pk]), {"text": "Démo réussie"})
        self.assertTrue(Entry.objects.filter(goal=work, text="Démo réussie").exists())

    def test_contacts(self, _now):
        ensure_vision(self.me, 2027)
        links = self.goal("Entretenir les liens")
        self.post(
            reverse("goals:add_contact", args=[links.pk]), {"name": "Mamie", "every_days": "7"}
        )
        contact = Contact.objects.get(name="Mamie")
        self.post(reverse("goals:contact_done", args=[contact.pk]))
        contact.refresh_from_db()
        self.assertEqual(contact.last_contact, TODAY)
        self.assertTrue(StepLog.objects.filter(step__goal=links, date=TODAY).exists())

    def test_edit_steps(self, _now):
        ensure_vision(self.me, 2027)
        goal = self.goal("Me rapprocher d'Allah")
        url = reverse("goals:edit", args=[goal.pk])
        self.post(
            url,
            {
                "action": "add_step",
                "new-title": "Écouter une sourate",
                "new-unit": "",
                "new-daily_target": "1",
                "new-days_per_week": "3",
            },
        )
        self.assertTrue(Step.objects.filter(goal=goal, title="Écouter une sourate").exists())
        step = Step.objects.get(title="Écouter une sourate")
        self.post(url, {"action": "delete_step", "pk": step.pk})
        self.assertFalse(Step.objects.filter(pk=step.pk).exists())

    def test_year_calendar_starts_now_when_year_is_ahead(self, _now):
        ensure_vision(self.me, 2027)
        months = year_calendar(self.goal("Bouger chaque jour"), TODAY)
        self.assertEqual(months[0].month, datetime.date(2026, 11, 1))
        self.assertEqual(months[-1].month, datetime.date(2027, 12, 1))

    def test_home_card_and_review(self, _now):
        ensure_vision(self.me, 2027)
        home = self.get(reverse("tasks:home"))
        self.assertContains(home, "Mes petits pas du jour")
        self.assertContains(home, "Lire le Coran")
        review = self.get(reverse("review:week"))
        self.assertContains(review, "Mes objectifs (privé)")
