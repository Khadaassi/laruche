import datetime

from django.db import IntegrityError
from django.test import TestCase

from apps.families.models import Person
from apps.families.tests.factories import join, make_child_profile, make_family
from apps.tasks.models import Task, TaskCompletion, mask_to_weekdays, weekdays_to_mask
from apps.tasks.periods import Period
from apps.tasks.selectors import count_remaining, group_by_period, group_by_person, tasks_for_day
from apps.tasks.services import set_done

MONDAY = datetime.date(2026, 9, 28)
SATURDAY = datetime.date(2026, 10, 3)
WEEKDAYS = weekdays_to_mask(range(5))
WEEKEND = weekdays_to_mask([5, 6])


class WeekdayMaskTests(TestCase):
    def test_round_trip(self):
        self.assertEqual(mask_to_weekdays(weekdays_to_mask([0, 2, 6])), [0, 2, 6])

    def test_empty_mask_is_rejected_by_database(self):
        family = make_family()
        person = make_child_profile(family)
        with self.assertRaises(IntegrityError):
            Task.objects.create(person=person, title="x", period=Period.MORNING, weekdays=0)


class TasksForDayTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        self.teeth = Task.objects.create(person=self.lina, title="Dents", period=Period.MORNING)
        self.school_bag = Task.objects.create(
            person=self.lina, title="Cartable", period=Period.EVENING, weekdays=WEEKDAYS
        )
        self.market = Task.objects.create(
            person=self.noah, title="Marché", period=Period.MORNING, weekdays=WEEKEND
        )
        self.table = Task.objects.create(person=self.noah, title="Table", period=Period.NOON)

    def test_only_tasks_scheduled_that_day(self):
        monday = {t.title for t in tasks_for_day(self.family, MONDAY)}
        saturday = {t.title for t in tasks_for_day(self.family, SATURDAY)}
        self.assertEqual(monday, {"Dents", "Cartable", "Table"})
        self.assertEqual(saturday, {"Dents", "Marché", "Table"})

    def test_filter_by_person_and_period(self):
        tasks = tasks_for_day(self.family, MONDAY, people=[self.lina], period=Period.MORNING)
        self.assertEqual([t.title for t in tasks], ["Dents"])

    def test_other_family_tasks_never_included(self):
        other = make_family(name="Voisins")
        Task.objects.create(
            person=make_child_profile(other, "Tom"), title="Intrus", period=Period.MORNING
        )
        titles = {t.title for t in tasks_for_day(self.family, MONDAY)}
        self.assertNotIn("Intrus", titles)

    def test_done_state_is_per_date(self):
        TaskCompletion.objects.create(task=self.teeth, date=MONDAY)
        monday = {t.title: t.is_done for t in tasks_for_day(self.family, MONDAY)}
        tuesday = {
            t.title: t.is_done
            for t in tasks_for_day(self.family, MONDAY + datetime.timedelta(days=1))
        }
        self.assertTrue(monday["Dents"])
        self.assertFalse(tuesday["Dents"])

    def test_remaining_count_per_person(self):
        TaskCompletion.objects.create(task=self.teeth, date=MONDAY)
        people = Person.objects.for_family(self.family)
        columns = group_by_person(people, tasks_for_day(self.family, MONDAY))
        self.assertEqual(
            [(c.person.name, c.remaining) for c in columns], [("Lina", 1), ("Noah", 1)]
        )

    def test_person_without_task_still_has_a_column(self):
        make_child_profile(self.family, "Zoé")
        people = Person.objects.for_family(self.family)
        columns = group_by_person(people, tasks_for_day(self.family, MONDAY))
        self.assertEqual(columns[-1].person.name, "Zoé")
        self.assertEqual(columns[-1].tasks, [])

    def test_group_by_period_keeps_day_order(self):
        groups = group_by_period(tasks_for_day(self.family, MONDAY), current=Period.NOON)
        self.assertEqual([g.period for g in groups], [Period.MORNING, Period.NOON, Period.EVENING])
        self.assertEqual([g.is_current for g in groups], [False, True, False])
        self.assertEqual([g.remaining for g in groups], [1, 1, 1])


class SetDoneTests(TestCase):
    def setUp(self):
        parent = join(make_family())
        self.task = Task.objects.create(person=parent.person, title="Dents", period=Period.MORNING)
        self.user = parent

    def test_set_done_is_idempotent(self):
        set_done(self.task, MONDAY, True, by=self.user)
        set_done(self.task, MONDAY, True, by=self.user)
        self.assertEqual(TaskCompletion.objects.count(), 1)
        set_done(self.task, MONDAY, False)
        set_done(self.task, MONDAY, False)
        self.assertEqual(TaskCompletion.objects.count(), 0)

    def test_count_remaining(self):
        set_done(self.task, MONDAY, True)
        tasks = tasks_for_day(self.task.person.family, MONDAY)
        self.assertEqual(count_remaining(tasks), 0)
