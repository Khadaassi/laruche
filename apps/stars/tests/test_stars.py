import datetime

from django.test import TestCase

from apps.families.tests.factories import join, make_child_profile, make_family
from apps.household.models import ChoreCompletion, HouseholdChore
from apps.stars.models import StarDebit, StarSpend
from apps.stars.selectors import STAR_TIER, balances, pot
from apps.stars.services import NotEnoughStars, refund, spend_from_pot, split_cost
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period

DAY = datetime.date(2026, 9, 28)


def earn(person, n, start=DAY):
    """Donne n étoiles à une personne : n validations de tâche sur n jours."""
    task = Task.objects.create(person=person, title=f"Tâche {person.name}", period=Period.MORNING)
    for i in range(n):
        TaskCompletion.objects.create(task=task, date=start - datetime.timedelta(days=i))


class BalanceTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")

    def test_one_star_per_completed_task_and_child_chore(self):
        earn(self.lina, 3)
        chore = HouseholdChore.objects.create(
            family=self.family, title="Table", assignee=self.lina, start_date=DAY
        )
        ChoreCompletion.objects.create(chore=chore, date=DAY)
        self.assertEqual(balances(self.family)[self.lina.pk].earned, 4)

    def test_unticking_removes_the_star(self):
        earn(self.lina, 2)
        TaskCompletion.objects.filter(task__person=self.lina).first().delete()
        self.assertEqual(balances(self.family)[self.lina.pk].balance, 1)

    def test_parents_do_not_earn_stars(self):
        earn(self.parent.person, 5)
        self.assertNotIn(self.parent.person.pk, balances(self.family))
        self.assertEqual(pot(self.family), 0)

    def test_tier_counts_earned_stars_and_never_goes_back(self):
        earn(self.lina, STAR_TIER + 3)
        spend_from_pot(self.family, 12, "Cirque")
        balance = balances(self.family)[self.lina.pk]
        self.assertEqual((balance.balance, balance.tier, balance.to_next_tier), (1, 1, 7))

    def test_other_family_isolated(self):
        stranger = make_child_profile(make_family(name="Voisins"), "Tom")
        earn(stranger, 20)
        self.assertEqual(pot(self.family), 0)
        self.assertNotIn(stranger.pk, balances(self.family))


class SplitCostTests(TestCase):
    def test_proportional_to_balances(self):
        self.assertEqual(split_cost({1: 10, 2: 5, 3: 0}, 6), {1: 4, 2: 2})

    def test_sum_is_exact_and_never_above_balance(self):
        for available, cost in [
            ({1: 7, 2: 3, 3: 1}, 10),
            ({1: 1, 2: 1, 3: 1}, 2),
            ({1: 33, 2: 17}, 29),
        ]:
            shares = split_cost(available, cost)
            self.assertEqual(sum(shares.values()), cost)
            self.assertTrue(all(shares[p] <= available[p] for p in shares))

    def test_whole_pot(self):
        self.assertEqual(split_cost({1: 4, 2: 6}, 10), {1: 4, 2: 6})

    def test_zero_or_negative_balance_never_contributes(self):
        self.assertEqual(split_cost({1: 5, 2: 0, 3: -2}, 5), {1: 5})

    def test_not_enough(self):
        with self.assertRaises(NotEnoughStars):
            split_cost({1: 3, 2: 2}, 6)

    def test_deterministic_tie_break(self):
        self.assertEqual(split_cost({1: 1, 2: 1}, 1), {1: 1})


class SpendTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        earn(self.lina, 10)
        earn(self.noah, 5)

    def test_spend_debits_each_child(self):
        spend = spend_from_pot(self.family, 6, "Cirque")
        self.assertEqual(
            {d.person.name: d.amount for d in spend.debits.all()}, {"Lina": 4, "Noah": 2}
        )
        self.assertEqual(pot(self.family), 9)

    def test_cannot_spend_more_than_pot(self):
        with self.assertRaises(NotEnoughStars):
            spend_from_pot(self.family, 16, "Trop cher")
        self.assertFalse(StarSpend.objects.exists())

    def test_refund_gives_back_exact_shares(self):
        spend = spend_from_pot(self.family, 6, "Cirque")
        refund(spend)
        self.assertFalse(StarDebit.objects.exists())
        self.assertEqual(pot(self.family), 15)
