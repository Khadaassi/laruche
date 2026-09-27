"""Vacances et absences : tâches et ménage suspendus, école remplacée, permissions."""

import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.absences.models import Absence, AbsenceKind
from apps.absences.selectors import absences_range
from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family
from apps.household.models import HouseholdChore
from apps.household.selectors import chores_by_day
from apps.school.models import Lunch, SchoolDaySchedule
from apps.school.selectors import school_days_for
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period
from apps.tasks.selectors import tasks_for_day

MONDAY_8AM = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.UTC)  # 08:00 Paris
MONDAY = datetime.date(2026, 9, 28)
TUESDAY = MONDAY + datetime.timedelta(days=1)


class AbsenceFixture:
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        self.lina_task = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.noah_task = Task.objects.create(person=self.noah, title="Lit", period=Period.MORNING)

    def absent(self, person, start=MONDAY, end=MONDAY, kind=AbsenceKind.SICK, note=""):
        return Absence.objects.create(
            family=self.family, person=person, kind=kind, start_date=start, end_date=end, note=note
        )


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class AbsenceEffectsTests(AbsenceFixture, SecureClientMixin, TestCase):
    def titles(self, day=MONDAY):
        return sorted(t.title for t in tasks_for_day(self.family, day))

    def test_sick_child_tasks_are_suspended_for_the_period_only(self, _now):
        self.absent(self.lina, MONDAY, TUESDAY)
        self.assertEqual(self.titles(MONDAY), ["Lit"])
        self.assertEqual(self.titles(TUESDAY), ["Lit"])
        self.assertEqual(self.titles(TUESDAY + datetime.timedelta(days=1)), ["Dents", "Lit"])

    def test_family_vacation_suspends_everyone(self, _now):
        self.absent(None, kind=AbsenceKind.VACATION)
        self.assertEqual(self.titles(), [])

    def test_other_family_absence_has_no_effect(self, _now):
        Absence.objects.create(
            family=make_family(name="Autre"),
            kind=AbsenceKind.VACATION,
            start_date=MONDAY,
            end_date=MONDAY,
        )
        self.assertEqual(self.titles(), ["Dents", "Lit"])

    def test_chores_of_absent_person_are_hidden(self, _now):
        chore = HouseholdChore.objects.create(
            family=self.family, title="Poubelles", assignee=self.lina, start_date=MONDAY
        )
        self.absent(self.lina)
        self.assertEqual(chores_by_day(self.family, MONDAY, 2)[MONDAY], [])
        self.assertEqual([o.chore for o in chores_by_day(self.family, MONDAY, 2)[TUESDAY]], [chore])

    def test_school_shows_the_absence(self, _now):
        SchoolDaySchedule.objects.create(person=self.lina, weekday=0, lunch=Lunch.PACKED)
        self.absent(self.lina, kind=AbsenceKind.SICK)
        day = school_days_for(self.family, MONDAY, people=[self.lina, self.noah])
        self.assertEqual(day[self.lina.pk].lunch_label, "Malade")
        self.assertFalse(day[self.lina.pk].has_school)
        self.assertNotIn(self.noah.pk, day)

    def test_no_packed_lunch_reminder_when_absent_tomorrow(self, _now):
        from apps.core.preparation import tomorrow_items

        SchoolDaySchedule.objects.create(person=self.lina, weekday=1, lunch=Lunch.PACKED)
        self.assertEqual(len(tomorrow_items(self.family, MONDAY)), 1)
        self.absent(self.lina, TUESDAY, TUESDAY)
        self.assertEqual(tomorrow_items(self.family, MONDAY), [])

    def test_ranges_spanning_the_window(self, _now):
        self.absent(
            self.lina, MONDAY - datetime.timedelta(days=3), MONDAY + datetime.timedelta(days=1)
        )
        days = absences_range(self.family, MONDAY, 3)
        self.assertEqual([d.is_absent(self.lina.pk) for d in days.values()], [True, True, False])

    def test_toggling_a_suspended_task_is_refused_and_stars_are_kept(self, _now):
        TaskCompletion.objects.create(task=self.lina_task, date=MONDAY)
        self.absent(self.lina)
        self.client.force_login(self.parent)
        response = self.htmx_post(reverse("tasks:toggle", args=[self.lina_task.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(TaskCompletion.objects.filter(task=self.lina_task).exists())
        shared = self.htmx_post(
            reverse("display:toggle", args=[self.lina.pk, self.lina_task.pk]), {"done": "on"}
        )
        self.assertEqual(shared.status_code, 404)

    def test_home_and_shared_display_show_the_absence(self, _now):
        self.absent(self.lina, note="gastro")
        self.client.force_login(self.parent)
        home = self.get(reverse("tasks:home"))
        self.assertContains(home, "Malade · gastro")
        self.assertNotContains(home, "Dents")
        board = self.get(reverse("display:board"))
        self.assertContains(board, "Malade · gastro : pas de tâches aujourd'hui.")
        self.assertContains(board, "Lit")


@mock.patch("django.utils.timezone.now", return_value=MONDAY_8AM)
class AbsenceManageTests(AbsenceFixture, SecureClientMixin, TestCase):
    URL = reverse("absences:manage")

    def data(self, **overrides):
        base = {
            "scope": "people",
            "people": [self.lina.pk],
            "kind": "sick",
            "start_date": "2026-09-28",
            "end_date": "2026-09-29",
            "note": "",
        }
        return base | overrides

    def test_create_for_several_people(self, _now):
        self.client.force_login(self.parent)
        self.post(self.URL, self.data(people=[self.lina.pk, self.noah.pk]))
        self.assertEqual(
            sorted(Absence.objects.values_list("person__name", flat=True)), ["Lina", "Noah"]
        )

    def test_create_for_the_whole_family(self, _now):
        self.client.force_login(self.parent)
        self.post(self.URL, self.data(scope="family", people=[], kind="vacation"))
        absence = Absence.objects.get()
        self.assertIsNone(absence.person)
        self.assertEqual(absence.who, "Toute la famille")
        self.assertContains(self.get(self.URL), "Toute la famille · Vacances")

    def test_validation(self, _now):
        self.client.force_login(self.parent)
        self.assertEqual(self.post(self.URL, self.data(people=[])).status_code, 400)
        response = self.post(self.URL, self.data(end_date="2026-09-01"))
        self.assertIn("end_date", response.context["form"].errors)
        stranger = make_child_profile(make_family(name="Autre"), "Tom")
        self.assertEqual(self.post(self.URL, self.data(people=[stranger.pk])).status_code, 400)
        self.assertFalse(Absence.objects.exists())

    def test_delete(self, _now):
        absence = self.absent(self.lina)
        self.client.force_login(self.parent)
        self.post(reverse("absences:delete", args=[absence.pk]))
        self.assertFalse(Absence.objects.exists())

    def test_permissions(self, _now):
        absence = self.absent(self.lina)
        other = make_family(name="Autre")
        foreign = Absence.objects.create(
            family=other, kind="sick", start_date=MONDAY, end_date=MONDAY
        )
        # Anonyme : connexion.
        self.assertEqual(self.get(self.URL).status_code, 302)
        # Compte enfant : refusé.
        self.client.force_login(join(self.family, "Lina"))
        self.assertEqual(self.get(self.URL).status_code, 403)
        self.assertEqual(self.post(self.URL, self.data()).status_code, 403)
        self.assertEqual(self.post(reverse("absences:delete", args=[absence.pk])).status_code, 403)
        # Autre famille : 404.
        self.client.force_login(self.parent)
        self.assertEqual(self.post(reverse("absences:delete", args=[foreign.pk])).status_code, 404)
        self.assertEqual(Absence.objects.count(), 2)
        self.assertNotContains(self.get(self.URL), "Toute la famille · Malade")
