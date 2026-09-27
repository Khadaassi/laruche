import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family
from apps.household.forms import ChoreForm
from apps.household.models import ChoreCompletion, HouseholdChore
from apps.household.selectors import chores_by_day
from apps.tasks.models import weekdays_to_mask

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)
MONDAY = datetime.date(2026, 9, 28)


def chore(family, assignee, title="Aspirateur", days=(0,), interval=1, start=MONDAY):
    return HouseholdChore.objects.create(
        family=family,
        assignee=assignee,
        title=title,
        weekdays=weekdays_to_mask(days),
        interval_weeks=interval,
        start_date=start,
    )


class RecurrenceTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.person = make_child_profile(self.family)

    def test_daily(self):
        c = chore(self.family, self.person, days=range(7))
        self.assertTrue(all(c.occurs_on(MONDAY + datetime.timedelta(days=d)) for d in range(14)))

    def test_weekly_on_given_days(self):
        c = chore(self.family, self.person, days=(0, 3))
        occurring = [d for d in range(7) if c.occurs_on(MONDAY + datetime.timedelta(days=d))]
        self.assertEqual(occurring, [0, 3])

    def test_every_other_week_counts_from_start_week(self):
        # Démarrée un mercredi : la semaine de départ compte, pas la suivante.
        c = chore(
            self.family,
            self.person,
            days=(5,),
            interval=2,
            start=MONDAY + datetime.timedelta(days=2),
        )
        saturdays = [MONDAY + datetime.timedelta(days=5, weeks=w) for w in range(4)]
        self.assertEqual([c.occurs_on(s) for s in saturdays], [True, False, True, False])

    def test_never_before_start_date(self):
        c = chore(self.family, self.person, days=range(7), start=MONDAY)
        self.assertFalse(c.occurs_on(MONDAY - datetime.timedelta(days=1)))

    def test_chores_by_day_with_done_state_and_family_scope(self):
        c = chore(self.family, self.person, days=(0, 1))
        ChoreCompletion.objects.create(chore=c, date=MONDAY)
        chore(
            make_family(name="Voisins"),
            make_child_profile(make_family(name="X")),
            "Intrus",
            days=range(7),
        )
        week = chores_by_day(self.family, MONDAY, 7)
        self.assertEqual([(o.chore.title, o.is_done) for o in week[MONDAY]], [("Aspirateur", True)])
        self.assertEqual([o.is_done for o in week[MONDAY + datetime.timedelta(days=1)]], [False])
        self.assertEqual(week[MONDAY + datetime.timedelta(days=2)], [])


class ChoreFormTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")

    def form(self, **data):
        base = {"title": "Poubelles", "assignee": self.parent.person.pk, "frequency": "weekly"}
        base.update(data)
        return ChoreForm(base, family=self.family)

    def test_parent_can_be_assigned(self):
        form = self.form(weekday_choices=["1", "4"])
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(
            (saved.family, saved.assignee, saved.weekdays),
            (self.family, self.parent.person, weekdays_to_mask([1, 4])),
        )

    def test_daily_ignores_days(self):
        form = self.form(frequency="daily")
        self.assertTrue(form.is_valid())
        saved = form.save()
        self.assertEqual((saved.weekdays, saved.interval_weeks), (0b1111111, 1))

    def test_biweekly(self):
        form = self.form(frequency="biweekly", weekday_choices=["5"])
        self.assertTrue(form.is_valid())
        self.assertEqual(form.save().interval_weeks, 2)

    def test_weekly_requires_days(self):
        self.assertIn("weekday_choices", self.form().errors)

    def test_assignee_of_another_family_rejected(self):
        stranger = make_child_profile(make_family(name="Voisins"), "Tom")
        form = self.form(assignee=stranger.pk, weekday_choices=["1"])
        self.assertIn("assignee", form.errors)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class HouseholdViewsTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.chore = chore(self.family, self.parent.person, "Lessive", days=(0,))
        self.stranger_chore = chore(
            make_family(name="Voisins"),
            make_child_profile(make_family(name="Autre"), "Tom"),
            "Intrus",
            days=(0,),
        )

    def toggle(self, c, day=MONDAY, done=True):
        url = reverse("household:toggle", args=[c.pk, day.isoformat()])
        return self.htmx_post(url, {"done": "on"} if done else {})

    def test_week_page_lists_chores(self, _now):
        self.client.force_login(self.parent)
        response = self.get(reverse("household:week"))
        self.assertContains(response, "Lessive")
        self.assertNotContains(response, "Intrus")
        self.assertContains(response, 'aria-current="page"')

    def test_other_week_via_parameter(self, _now):
        self.client.force_login(self.parent)
        response = self.get(reverse("household:week"), {"semaine": "2026-10-07"})
        self.assertEqual(response.context["monday"], datetime.date(2026, 10, 5))
        self.assertEqual(self.get(reverse("household:week"), {"semaine": "nope"}).status_code, 404)

    def test_parent_toggles_chore(self, _now):
        self.client.force_login(self.parent)
        self.assertEqual(self.toggle(self.chore).status_code, 204)
        self.assertTrue(ChoreCompletion.objects.filter(chore=self.chore, date=MONDAY).exists())
        self.toggle(self.chore, done=False)
        self.assertFalse(ChoreCompletion.objects.exists())

    def test_toggle_other_family_chore_is_404(self, _now):
        self.client.force_login(self.parent)
        self.assertEqual(self.toggle(self.stranger_chore).status_code, 404)

    def test_toggle_on_unscheduled_day_is_404(self, _now):
        self.client.force_login(self.parent)
        tuesday = MONDAY + datetime.timedelta(days=1)
        self.assertEqual(self.toggle(self.chore, day=tuesday).status_code, 404)

    def test_child_has_no_access_to_household_pages(self, _now):
        self.client.force_login(self.kid)
        self.assertEqual(self.get(reverse("household:week")).status_code, 403)
        self.assertEqual(self.get(reverse("household:manage")).status_code, 403)
        self.assertEqual(self.toggle(self.chore).status_code, 403)
        delete = reverse("household:delete", args=[self.chore.pk])
        self.assertEqual(self.post(delete).status_code, 403)
        self.assertFalse(ChoreCompletion.objects.exists())
        self.assertTrue(HouseholdChore.objects.filter(pk=self.chore.pk).exists())

    def test_parent_creates_and_deletes(self, _now):
        self.client.force_login(self.parent)
        self.post(
            reverse("household:manage"),
            {
                "title": "Poussière",
                "assignee": self.kid.person.pk,
                "frequency": "weekly",
                "weekday_choices": ["2"],
            },
        )
        created = HouseholdChore.objects.get(title="Poussière")
        self.assertEqual(created.family, self.family)
        self.post(reverse("household:delete", args=[created.pk]))
        self.assertFalse(HouseholdChore.objects.filter(pk=created.pk).exists())

    def test_delete_other_family_chore_is_404(self, _now):
        self.client.force_login(self.parent)
        response = self.post(reverse("household:delete", args=[self.stranger_chore.pk]))
        self.assertEqual(response.status_code, 404)

    def test_shared_week_is_read_only_for_child(self, _now):
        self.client.force_login(self.kid)
        response = self.get(reverse("display:week"))
        self.assertContains(response, "Lessive")
        self.assertNotContains(response, "Intrus")
        self.assertNotContains(response, "hx-post")

    def test_anonymous_redirected(self, _now):
        for url in (reverse("household:week"), reverse("display:week")):
            response = self.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("accounts:login"), response["Location"])
