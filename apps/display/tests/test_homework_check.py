import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_child_profile, make_family
from apps.school.models import Lunch, SchoolDaySchedule
from apps.stars.models import DayStar
from apps.tasks.models import HomeworkCheck, Task, TaskCompletion
from apps.tasks.periods import Period

MONDAY = datetime.date(2026, 9, 28)
MONDAY_6PM = datetime.datetime(2026, 9, 28, 16, 0, tzinfo=datetime.UTC)  # 18 h à Paris


class IsHomeworkTests(TestCase):
    def test_title_detection_ignores_case_and_accents(self):
        family = make_family()
        lina = make_child_profile(family)
        for title, expected in (("Devoirs", True), ("DEVOIR de maths", True), ("Bain", False)):
            task = Task(person=lina, title=title, period=Period.EVENING)
            self.assertEqual(task.is_homework, expected, title)


@mock.patch("django.utils.timezone.now", return_value=MONDAY_6PM)
class HomeworkCheckTests(SecureClientMixin, TestCase):
    """Jour d'étude : « As-tu fini tes devoirs à l'étude ? » avant la routine du soir."""

    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.kid = join(self.family, "Lina")
        self.lina = self.kid.person
        self.noah = make_child_profile(self.family, "Noah")
        self.bath = Task.objects.create(person=self.lina, title="Bain", period=Period.EVENING)
        self.homework = Task.objects.create(
            person=self.lina, title="Devoirs", period=Period.EVENING
        )
        self.school = SchoolDaySchedule.objects.create(
            person=self.lina, weekday=0, lunch=Lunch.CANTEEN, study=True
        )

    def board(self):
        response = self.get(reverse("display:board"))
        return response, {c.person.name: c for c in response.context["columns"]}

    def answer(self, person, finished):
        url = reverse("display:homework_check", args=[person.pk])
        return self.post(url, {"finished": finished})

    def test_study_day_asks_and_puts_homework_first(self, _now):
        self.client.force_login(self.kid)
        response, columns = self.board()
        self.assertContains(response, "As-tu fini tes devoirs à l'étude ?")
        self.assertEqual([t.title for t in columns["Lina"].tasks], ["Devoirs", "Bain"])

    def test_no_question_without_study(self, _now):
        self.school.study = False
        self.school.save()
        self.client.force_login(self.kid)
        response, columns = self.board()
        self.assertNotContains(response, "devoirs à l'étude")
        self.assertEqual([t.title for t in columns["Lina"].tasks], ["Bain", "Devoirs"])
        self.assertEqual(self.answer(self.lina, "oui").status_code, 404)

    def test_yes_ticks_homework_and_does_not_ask_again(self, _now):
        self.client.force_login(self.kid)
        self.assertRedirects(
            self.answer(self.lina, "oui"), reverse("display:board"), fetch_redirect_response=False
        )
        self.assertTrue(TaskCompletion.objects.filter(task=self.homework, date=MONDAY).exists())
        self.assertFalse(TaskCompletion.objects.filter(task=self.bath).exists())
        self.assertNotContains(self.board()[0], "devoirs à l'étude")

    def test_no_leaves_homework_unticked(self, _now):
        self.client.force_login(self.kid)
        self.answer(self.lina, "non")
        self.assertFalse(TaskCompletion.objects.exists())
        self.assertFalse(HomeworkCheck.objects.get(person=self.lina).finished)
        response, columns = self.board()
        self.assertNotContains(response, "devoirs à l'étude")
        self.assertEqual(columns["Lina"].tasks[0].title, "Devoirs")  # toujours en tête
        # Une seule réponse par jour : un « oui » ensuite ne coche rien.
        self.answer(self.lina, "oui")
        self.assertFalse(TaskCompletion.objects.exists())

    def test_yes_completing_the_day_awards_the_star(self, _now):
        TaskCompletion.objects.create(task=self.bath, date=MONDAY)
        self.client.force_login(self.kid)
        self.answer(self.lina, "oui")
        self.assertTrue(DayStar.objects.filter(person=self.lina, date=MONDAY).exists())

    def test_child_answers_only_for_self(self, _now):
        SchoolDaySchedule.objects.create(
            person=self.noah, weekday=0, lunch=Lunch.CANTEEN, study=True
        )
        self.client.force_login(self.kid)
        self.assertEqual(self.answer(self.noah, "oui").status_code, 403)
        self.assertFalse(HomeworkCheck.objects.exists())

    def test_other_family_child_is_404(self, _now):
        stranger = make_child_profile(make_family(name="Voisins"), "Tom")
        self.client.force_login(self.kid)
        self.assertEqual(self.answer(stranger, "oui").status_code, 404)

    def test_parent_preview_can_answer_and_anonymous_cannot(self, _now):
        response = self.answer(self.lina, "oui")
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertFalse(HomeworkCheck.objects.exists())
        self.client.force_login(self.parent)
        self.answer(self.lina, "oui")
        self.assertTrue(HomeworkCheck.objects.get(person=self.lina).finished)
