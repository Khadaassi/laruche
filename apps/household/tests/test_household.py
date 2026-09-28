import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family
from apps.household.forms import ChoreForm
from apps.household.models import ChoreCompletion, ChoreSwap, HouseholdChore
from apps.household.selectors import chores_by_day, rotations, swap_rotation
from apps.stars.models import DayStar
from apps.tasks.models import weekdays_to_mask

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)
MONDAY = datetime.date(2026, 9, 28)


def chore(
    family, assignee, title="Aspirateur", days=(0,), interval=1, start=MONDAY, alternate=None
):
    return HouseholdChore.objects.create(
        family=family,
        assignee=assignee,
        alternate=alternate,
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


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class ChildChoreOnSharedScreenTests(SecureClientMixin, TestCase):
    """Un enfant coche sa tâche de ménage sur sa colonne, comme ses tâches du jour."""

    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        self.own = chore(self.family, self.kid.person, "Vider le lave-vaisselle", days=(0,))
        self.sibling = chore(self.family, self.noah, "Mettre la table", days=(0,))
        self.parents = chore(self.family, self.parent.person, "Lessive", days=(0,))
        self.tomorrow = chore(self.family, self.kid.person, "Poubelles", days=(1,))

    def toggle(self, person, c, done=True):
        url = reverse("display:toggle_chore", args=[person.pk, c.pk])
        return self.htmx_post(url, {"done": "on"} if done else {})

    def test_child_ticks_own_chore(self, _now):
        self.client.force_login(self.kid)
        response = self.toggle(self.kid.person, self.own)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="child-status-{self.kid.person.pk}" hx-swap-oob="true"')
        self.assertTrue(ChoreCompletion.objects.filter(chore=self.own, date=MONDAY).exists())
        self.toggle(self.kid.person, self.own, done=False)
        self.assertFalse(ChoreCompletion.objects.exists())

    def test_child_cannot_tick_sibling_chore(self, _now):
        self.client.force_login(self.kid)
        self.assertEqual(self.toggle(self.noah, self.sibling).status_code, 403)
        # Ni en le faisant passer par sa propre colonne.
        self.assertEqual(self.toggle(self.kid.person, self.sibling).status_code, 404)
        self.assertFalse(ChoreCompletion.objects.exists())

    def test_child_cannot_tick_parent_chore(self, _now):
        self.client.force_login(self.kid)
        self.assertEqual(self.toggle(self.kid.person, self.parents).status_code, 404)
        self.assertEqual(self.toggle(self.parent.person, self.parents).status_code, 404)
        self.assertFalse(ChoreCompletion.objects.exists())

    def test_shared_device_cannot_tick_parent_chore_either(self, _now):
        self.client.force_login(self.parent)
        self.post(reverse("display:activate"), {"name": "Tablette"})
        self.assertEqual(self.toggle(self.parent.person, self.parents).status_code, 404)
        self.assertEqual(self.toggle(self.noah, self.sibling).status_code, 200)

    def test_chore_not_scheduled_today_is_404(self, _now):
        self.client.force_login(self.kid)
        self.assertEqual(self.toggle(self.kid.person, self.tomorrow).status_code, 404)

    def test_other_family_chore_is_404(self, _now):
        stranger = make_child_profile(make_family(name="Voisins"), "Tom")
        intruder = chore(stranger.family, stranger, "Intrus", days=(0,))
        self.client.force_login(self.kid)
        self.assertEqual(self.toggle(stranger, intruder).status_code, 404)

    def test_column_shows_chores_and_counts_them(self, _now):
        self.client.force_login(self.kid)
        response = self.get(reverse("display:board"))
        columns = {c.person.name: c for c in response.context["columns"]}
        self.assertEqual(
            [o.chore.title for o in columns["Lina"].chores], ["Vider le lave-vaisselle"]
        )
        self.assertEqual(columns["Lina"].remaining, 1)
        self.assertNotContains(response, "Lessive")  # ménage des parents : jamais sur l'écran
        own_url = reverse("display:toggle_chore", args=[self.kid.person.pk, self.own.pk])
        sibling_url = reverse("display:toggle_chore", args=[self.noah.pk, self.sibling.pk])
        self.assertContains(response, f'hx-post="{own_url}"')
        self.assertNotContains(response, f'hx-post="{sibling_url}"')


NEXT_MONDAY = MONDAY + datetime.timedelta(weeks=1)
LAST_MONDAY = MONDAY - datetime.timedelta(weeks=1)


class RotationTests(TestCase):
    """Lave-vaisselle / table : les deux enfants échangent leurs rôles chaque semaine."""

    def setUp(self):
        self.family = make_family()
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        self.dishes = chore(
            self.family, self.lina, "Remplir le lave-vaisselle", days=range(7),
            start=LAST_MONDAY, alternate=self.noah,
        )  # fmt: skip
        self.table = chore(
            self.family, self.noah, "Mettre la table", days=range(7),
            start=LAST_MONDAY, alternate=self.lina,
        )  # fmt: skip

    def who(self, c, day):
        return HouseholdChore.objects.get(pk=c.pk).person_on(day).name

    def test_alternates_every_monday(self):
        weeks = [LAST_MONDAY + datetime.timedelta(weeks=w) for w in range(4)]
        self.assertEqual(
            [self.who(self.dishes, d) for d in weeks], ["Lina", "Noah", "Lina", "Noah"]
        )
        self.assertEqual([self.who(self.table, d) for d in weeks], ["Noah", "Lina", "Noah", "Lina"])
        # Toute la semaine, du lundi au dimanche.
        self.assertEqual(self.who(self.dishes, MONDAY + datetime.timedelta(days=6)), "Noah")

    def test_without_alternate_always_assignee(self):
        fixed = chore(self.family, self.lina, "Poubelles", days=range(7), start=LAST_MONDAY)
        self.assertEqual(fixed.person_on(NEXT_MONDAY), self.lina)

    def test_swap_inverts_from_this_week_only(self):
        swap_rotation([self.dishes, self.table], MONDAY + datetime.timedelta(days=3))
        self.assertEqual(ChoreSwap.objects.get(chore=self.dishes).week, MONDAY)
        self.assertEqual(self.who(self.dishes, LAST_MONDAY), "Lina")  # passé inchangé
        self.assertEqual(self.who(self.dishes, MONDAY), "Lina")
        self.assertEqual(self.who(self.dishes, NEXT_MONDAY), "Noah")  # puis l'alternance reprend
        self.assertEqual(self.who(self.table, MONDAY), "Noah")

    def test_swap_twice_same_week_cancels(self):
        swap_rotation([self.dishes], MONDAY)
        swap_rotation([self.dishes], MONDAY + datetime.timedelta(days=2))
        self.assertFalse(ChoreSwap.objects.exists())
        self.assertEqual(self.who(self.dishes, MONDAY), "Noah")

    def test_occurrences_go_to_person_of_the_week(self):
        week = chores_by_day(self.family, MONDAY, 1)[MONDAY]
        self.assertEqual(
            {(o.chore.title, o.person.name) for o in week},
            {("Remplir le lave-vaisselle", "Noah"), ("Mettre la table", "Lina")},
        )

    def test_absence_checks_person_of_the_week(self):
        from apps.absences.models import Absence

        Absence.objects.create(
            family=self.family, person=self.noah, start_date=MONDAY, end_date=MONDAY
        )
        week = chores_by_day(self.family, MONDAY, 1)[MONDAY]
        self.assertEqual([o.chore.title for o in week], ["Mettre la table"])

    def test_rotations_grouped_by_pair(self):
        [rotation] = rotations(self.family, MONDAY)
        self.assertEqual([p.name for p in rotation.people], ["Lina", "Noah"])
        self.assertEqual(
            {(c.title, p.name) for c, p in rotation.chores},
            {("Remplir le lave-vaisselle", "Noah"), ("Mettre la table", "Lina")},
        )

    def test_alternate_must_differ_and_be_weekly(self):
        from django.db import IntegrityError, transaction

        for fields in ({"alternate": self.lina}, {"alternate": self.noah, "interval_weeks": 2}):
            with (
                self.subTest(fields=fields),
                transaction.atomic(),
                self.assertRaises(IntegrityError),
            ):
                HouseholdChore.objects.filter(pk=self.dishes.pk).update(**fields)


class RotationFormTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")

    def form(self, **data):
        base = {"title": "Table", "assignee": self.lina.pk, "frequency": "daily"}
        base.update(data)
        return ChoreForm(base, family=self.family)

    def test_alternate_saved(self):
        form = self.form(alternate=self.noah.pk)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().alternate, self.noah)

    def test_alternate_is_optional(self):
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().alternate)

    def test_same_person_rejected(self):
        self.assertIn("alternate", self.form(alternate=self.lina.pk).errors)

    def test_biweekly_rejected(self):
        form = self.form(alternate=self.noah.pk, frequency="biweekly", weekday_choices=["1"])
        self.assertIn("alternate", form.errors)

    def test_other_family_rejected(self):
        stranger = make_child_profile(make_family(name="Voisins"), "Tom")
        self.assertIn("alternate", self.form(alternate=stranger.pk).errors)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class RotationViewsTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        # Semaine de départ = semaine dernière : cette semaine, c'est à Noah.
        self.dishes = chore(
            self.family, self.kid.person, "Remplir le lave-vaisselle", days=range(7),
            start=LAST_MONDAY, alternate=self.noah,
        )  # fmt: skip
        self.table = chore(
            self.family, self.noah, "Mettre la table", days=range(7),
            start=LAST_MONDAY, alternate=self.kid.person,
        )  # fmt: skip

    def swap(self, *chores):
        return self.post(reverse("household:swap"), {"chore": [c.pk for c in chores]})

    def toggle_shared(self, person, c):
        url = reverse("display:toggle_chore", args=[person.pk, c.pk])
        return self.htmx_post(url, {"done": "on"})

    def test_manage_page_shows_who_does_what(self, _now):
        self.client.force_login(self.parent)
        response = self.get(reverse("household:manage"))
        self.assertContains(response, "Alternances de la semaine")
        self.assertContains(response, "Lina et Noah en alternance")
        self.assertEqual(len(response.context["rotations"]), 1)

    def test_parent_swaps_roles(self, _now):
        self.client.force_login(self.parent)
        self.assertRedirects(
            self.swap(self.dishes, self.table),
            reverse("household:manage"),
            fetch_redirect_response=False,
        )
        self.assertEqual(ChoreSwap.objects.filter(week=MONDAY).count(), 2)
        [rotation] = rotations(self.family, MONDAY)
        self.assertIn((self.dishes, self.kid.person), rotation.chores)

    def test_child_cannot_swap(self, _now):
        self.client.force_login(self.kid)
        self.assertEqual(self.swap(self.dishes).status_code, 403)
        self.assertFalse(ChoreSwap.objects.exists())

    def test_swap_other_family_chore_is_404(self, _now):
        other = make_family(name="Voisins")
        a, b = make_child_profile(other, "Tom"), make_child_profile(other, "Zoé")
        intruder = chore(other, a, "Intrus", days=range(7), alternate=b)
        fixed = chore(self.family, self.noah, "Poubelles", days=range(7))
        self.client.force_login(self.parent)
        self.assertEqual(self.swap(intruder).status_code, 404)
        self.assertEqual(self.swap(fixed).status_code, 404)  # sans alternance
        self.assertFalse(ChoreSwap.objects.exists())

    def test_shared_screen_follows_the_week(self, _now):
        self.client.force_login(self.kid)
        # Cette semaine, le lave-vaisselle est à Noah : Lina ne le coche pas.
        self.assertEqual(self.toggle_shared(self.kid.person, self.dishes).status_code, 404)
        self.assertEqual(self.toggle_shared(self.kid.person, self.table).status_code, 200)
        columns = {c.person.name: c for c in self.get(reverse("display:board")).context["columns"]}
        self.assertEqual([o.chore.title for o in columns["Lina"].chores], ["Mettre la table"])
        self.assertEqual(
            [o.chore.title for o in columns["Noah"].chores], ["Remplir le lave-vaisselle"]
        )

    def test_parent_tick_awards_star_to_person_of_the_week(self, _now):
        self.client.force_login(self.parent)
        url = reverse("household:toggle", args=[self.table.pk, MONDAY.isoformat()])
        self.htmx_post(url, {"done": "on"})
        self.assertTrue(DayStar.objects.filter(person=self.kid.person, date=MONDAY).exists())
        self.assertFalse(DayStar.objects.filter(person=self.noah).exists())
