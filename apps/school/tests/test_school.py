import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.celebrations.models import Celebration, CelebrationTodo
from apps.core.preparation import tomorrow_items
from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family
from apps.school.models import Lunch, SchoolDayOverride, SchoolDaySchedule
from apps.school.selectors import school_day, school_days_for, school_days_range

# Lundi 28 septembre 2026, 08:00 à Paris.
MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)
MONDAY = datetime.date(2026, 9, 28)
TUESDAY = MONDAY + datetime.timedelta(days=1)
WEDNESDAY = MONDAY + datetime.timedelta(days=2)


def weekly(person, weekday, lunch, study=False, note=""):
    return SchoolDaySchedule.objects.create(
        person=person, weekday=weekday, lunch=lunch, study=study, lunch_note=note
    )


class SchoolDayResolutionTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        weekly(self.lina, 0, Lunch.CANTEEN, study=True)
        weekly(self.lina, 1, Lunch.PACKED)
        weekly(self.lina, 2, Lunch.NONE)

    def test_weekly_schedule_repeats_every_week(self):
        for monday in (MONDAY, MONDAY + datetime.timedelta(weeks=5)):
            day = school_day(self.lina, monday)
            self.assertEqual((day.lunch, day.study, day.is_override), (Lunch.CANTEEN, True, False))

    def test_nothing_configured_means_nothing_displayed(self):
        self.assertIsNone(school_day(self.lina, MONDAY + datetime.timedelta(days=3)))
        self.assertNotIn(self.noah.pk, school_days_for(self.family, MONDAY))

    def test_override_replaces_weekly_for_that_date_only(self):
        SchoolDayOverride.objects.create(
            person=self.lina, date=MONDAY, lunch=Lunch.OTHER, lunch_note="Chez mamie"
        )
        today = school_day(self.lina, MONDAY)
        self.assertEqual(
            (today.lunch_label, today.study, today.is_override), ("Chez mamie", False, True)
        )
        next_monday = school_day(self.lina, MONDAY + datetime.timedelta(weeks=1))
        self.assertEqual(next_monday.lunch, Lunch.CANTEEN)

    def test_override_without_weekly_row(self):
        SchoolDayOverride.objects.create(person=self.noah, date=MONDAY, lunch=Lunch.CANTEEN)
        self.assertEqual(school_day(self.noah, MONDAY).lunch_label, "Cantine")

    def test_labels(self):
        self.assertEqual(school_day(self.lina, TUESDAY).lunch_label, "Sandwich (APC)")
        self.assertFalse(school_day(self.lina, WEDNESDAY).has_school)

    def test_range_over_a_week(self):
        SchoolDayOverride.objects.create(person=self.lina, date=TUESDAY, lunch=Lunch.CANTEEN)
        week = school_days_range(self.family, MONDAY, 7)
        self.assertEqual(len(week), 7)
        self.assertEqual(week[TUESDAY][self.lina.pk].lunch, Lunch.CANTEEN)
        self.assertEqual(week[MONDAY + datetime.timedelta(days=4)], {})

    def test_other_family_never_included(self):
        other = make_child_profile(make_family(name="Voisins"), "Tom")
        weekly(other, 0, Lunch.CANTEEN)
        self.assertNotIn(other.pk, school_days_for(self.family, MONDAY))


class TomorrowItemsTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")

    def texts(self, people=None):
        return [i.text for i in tomorrow_items(self.family, MONDAY, people=people)]

    def test_packed_lunch_tomorrow_reminds_sandwich(self):
        weekly(self.lina, 1, Lunch.PACKED)
        weekly(self.noah, 1, Lunch.CANTEEN)
        self.assertEqual(self.texts(), ["Préparer le sandwich de Lina (APC)"])

    def test_packed_lunch_today_is_not_a_reminder(self):
        weekly(self.lina, 0, Lunch.PACKED)
        self.assertEqual(self.texts(), [])

    def test_override_to_packed_tomorrow(self):
        weekly(self.lina, 1, Lunch.CANTEEN)
        SchoolDayOverride.objects.create(person=self.lina, date=TUESDAY, lunch=Lunch.PACKED)
        self.assertEqual(self.texts(), ["Préparer le sandwich de Lina (APC)"])

    def test_no_school_only_announced_when_exceptional(self):
        weekly(self.lina, 1, Lunch.NONE)  # mardi habituellement sans école : rien à dire
        SchoolDayOverride.objects.create(person=self.noah, date=TUESDAY, lunch=Lunch.NONE)
        self.assertEqual(self.texts(), ["Pas d'école pour Noah"])

    def test_lunch_elsewhere(self):
        weekly(self.lina, 1, Lunch.OTHER, note="chez mamie")
        self.assertEqual(self.texts(), ["Midi de Lina : chez mamie"])

    def test_celebration_tomorrow_with_remaining_todos(self):
        eid = Celebration.objects.create(family=self.family, name="Aïd", date=TUESDAY)
        CelebrationTodo.objects.create(celebration=eid, title="Gâteaux")
        CelebrationTodo.objects.create(celebration=eid, title="Nappe")
        CelebrationTodo.objects.create(celebration=eid, title="Invitations", done=True)
        self.assertEqual(self.texts(), ["Aïd demain — 2 préparatifs restants"])

    def test_filtered_by_selected_person(self):
        weekly(self.lina, 1, Lunch.PACKED)
        weekly(self.noah, 1, Lunch.PACKED)
        self.assertEqual(self.texts(people=[self.noah]), ["Préparer le sandwich de Noah (APC)"])

    def test_other_family_excluded(self):
        other = make_family(name="Voisins")
        weekly(make_child_profile(other, "Tom"), 1, Lunch.PACKED)
        Celebration.objects.create(family=other, name="Fête voisine", date=TUESDAY)
        self.assertEqual(self.texts(), [])


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class SchoolDisplayTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.lina = make_child_profile(self.family, "Lina")
        weekly(self.lina, 0, Lunch.CANTEEN, study=True)
        weekly(self.lina, 1, Lunch.PACKED)

    def test_parent_home_shows_today_badges_and_tomorrow(self, _now):
        self.client.force_login(self.parent)
        response = self.get(reverse("tasks:home"))
        self.assertContains(response, "Aujourd'hui à l'école")
        self.assertContains(response, "Cantine")
        self.assertContains(response, "Étude ce soir")
        self.assertContains(response, "À préparer pour demain")
        self.assertContains(response, "Préparer le sandwich de Lina (APC)")

    def test_shared_column_shows_badges_and_tomorrow_hint(self, _now):
        self.client.force_login(self.parent)
        response = self.get(reverse("display:board"))
        column = response.context["columns"][0]
        self.assertEqual(column.school.lunch, Lunch.CANTEEN)
        self.assertEqual(column.tomorrow, "Demain : sandwich")
        self.assertContains(response, "Étude ce soir")


class SchoolManagePermissionTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        self.stranger = make_child_profile(make_family(name="Voisins"), "Tom")

    def week_data(self, person, days=None):
        data = {}
        for day in range(5):
            prefix = f"child-{person.pk}-"
            lunch, study = (days or {}).get(day, ("", False))
            data[f"{prefix}lunch_{day}"] = lunch
            data[f"{prefix}note_{day}"] = ""
            if study:
                data[f"{prefix}study_{day}"] = "on"
        return data

    def test_parent_saves_weekly_schedule(self):
        self.client.force_login(self.parent)
        url = reverse("school:save_week", args=[self.noah.pk])
        self.post(
            url, self.week_data(self.noah, {0: (Lunch.CANTEEN, True), 2: (Lunch.NONE, False)})
        )
        rows = {r.weekday: (r.lunch, r.study) for r in self.noah.school_schedules.all()}
        self.assertEqual(rows, {0: (Lunch.CANTEEN, True), 2: (Lunch.NONE, False)})
        # « — » supprime le jour.
        self.post(url, self.week_data(self.noah, {0: (Lunch.PACKED, False)}))
        rows = {r.weekday: r.lunch for r in self.noah.school_schedules.all()}
        self.assertEqual(rows, {0: Lunch.PACKED})

    def test_cannot_edit_child_of_another_family(self):
        self.client.force_login(self.parent)
        url = reverse("school:save_week", args=[self.stranger.pk])
        response = self.post(url, self.week_data(self.stranger, {0: (Lunch.CANTEEN, False)}))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(SchoolDaySchedule.objects.exists())

    def test_parent_person_has_no_school_schedule(self):
        self.client.force_login(self.parent)
        url = reverse("school:save_week", args=[self.parent.person.pk])
        self.assertEqual(self.post(url, {}).status_code, 404)

    def test_override_for_another_family_child_is_rejected(self):
        self.client.force_login(self.parent)
        response = self.post(
            reverse("school:add_override"),
            {"person": self.stranger.pk, "date": "2026-10-01", "lunch": Lunch.PACKED},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SchoolDayOverride.objects.exists())

    def test_override_replaces_existing_one_for_same_date(self):
        self.client.force_login(self.parent)
        url = reverse("school:add_override")
        self.post(url, {"person": self.noah.pk, "date": "2026-10-01", "lunch": Lunch.PACKED})
        self.post(url, {"person": self.noah.pk, "date": "2026-10-01", "lunch": Lunch.NONE})
        self.assertEqual(SchoolDayOverride.objects.get().lunch, Lunch.NONE)

    def test_delete_override_of_another_family_is_404(self):
        override = SchoolDayOverride.objects.create(
            person=self.stranger, date=MONDAY, lunch=Lunch.NONE
        )
        self.client.force_login(self.parent)
        url = reverse("school:delete_override", args=[override.pk])
        self.assertEqual(self.post(url).status_code, 404)
        self.assertTrue(SchoolDayOverride.objects.exists())

    def test_child_account_has_no_access(self):
        self.client.force_login(self.kid)
        self.assertEqual(self.get(reverse("school:manage")).status_code, 403)
        url = reverse("school:save_week", args=[self.kid.person.pk])
        self.assertEqual(self.post(url, {}).status_code, 403)
        self.assertEqual(self.post(reverse("school:add_override"), {}).status_code, 403)

    def test_anonymous_redirected(self):
        response = self.get(reverse("school:manage"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
