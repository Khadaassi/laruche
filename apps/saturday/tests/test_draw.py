import datetime
import random
from collections import Counter
from decimal import Decimal

from django.test import TestCase

from apps.families.models import Family
from apps.families.services import create_family
from apps.families.tests.factories import join, make_child_profile, make_family, make_user
from apps.saturday.defaults import DEFAULT_ACTIVITIES, seed_default_activities
from apps.saturday.draw import (
    MAX_SPINS,
    CostFilter,
    DrawError,
    PlaceFilter,
    accept,
    cancel,
    close_past_plans,
    draw,
    eligible_activities,
    pick,
    recency_weight,
    target_saturday,
)
from apps.saturday.models import (
    Place,
    PlanStatus,
    SaturdayActivity,
    SaturdayPlan,
    Season,
    season_of,
)
from apps.stars.selectors import pot
from apps.stars.tests.test_stars import earn

MONDAY = datetime.date(2026, 9, 28)  # automne
SATURDAY = datetime.date(2026, 10, 3)


def activity(family, name, season=Season.ALL, place=Place.OUTING, is_free=True, stars=0, last=None):
    return SaturdayActivity.objects.create(
        family=family,
        name=name,
        season=season,
        place=place,
        is_free=is_free,
        price=None if is_free else Decimal("10"),
        star_cost=stars,
        last_done_on=last,
    )


class CalendarTests(TestCase):
    def test_target_saturday(self):
        for offset in range(7):
            day = MONDAY + datetime.timedelta(days=offset)
            expected = SATURDAY if day <= SATURDAY else SATURDAY + datetime.timedelta(days=7)
            self.assertEqual(target_saturday(day), expected, day)

    def test_saturday_targets_itself(self):
        self.assertEqual(target_saturday(SATURDAY), SATURDAY)

    def test_meteorological_seasons(self):
        cases = {
            1: Season.WINTER,
            3: Season.SPRING,
            6: Season.SUMMER,
            9: Season.AUTUMN,
            12: Season.WINTER,
        }
        for month, season in cases.items():
            self.assertEqual(season_of(datetime.date(2026, month, 15)), season)


class EligibilityTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.museum = activity(self.family, "Musée", is_free=False)
        self.games = activity(self.family, "Jeux", place=Place.HOME)
        self.forest = activity(self.family, "Forêt", season=Season.AUTUMN)
        self.beach = activity(self.family, "Plage", season=Season.SUMMER)
        self.circus = activity(self.family, "Cirque", is_free=False, stars=30)

    def names(self, cost=CostFilter.ANY, place=PlaceFilter.ANY, stars=0):
        return sorted(
            a.name for a in eligible_activities(self.family, SATURDAY, cost, place, stars)
        )

    def test_out_of_season_excluded(self):
        self.assertNotIn("Plage", self.names())
        self.assertIn("Forêt", self.names())

    def test_place_filter(self):
        self.assertEqual(self.names(place=PlaceFilter.HOME), ["Jeux"])
        self.assertNotIn("Jeux", self.names(place=PlaceFilter.OUTING))

    def test_free_filter_excludes_paid_and_star_activities(self):
        self.assertEqual(self.names(cost=CostFilter.FREE, stars=100), ["Forêt", "Jeux"])

    def test_star_activity_only_when_pot_can_pay(self):
        self.assertNotIn("Cirque", self.names(stars=29))
        self.assertIn("Cirque", self.names(stars=30))
        self.assertEqual(self.names(cost=CostFilter.STARS, stars=30), ["Cirque"])
        self.assertEqual(self.names(cost=CostFilter.STARS, stars=5), [])

    def test_other_family_catalog_never_drawn(self):
        activity(make_family(name="Voisins"), "Intrus")
        self.assertNotIn("Intrus", self.names())


class RecencyTests(TestCase):
    def setUp(self):
        self.family = make_family()

    def test_weights(self):
        never = activity(self.family, "A")
        last_week = activity(self.family, "B", last=SATURDAY - datetime.timedelta(weeks=1))
        four_weeks = activity(self.family, "C", last=SATURDAY - datetime.timedelta(weeks=4))
        long_ago = activity(self.family, "D", last=SATURDAY - datetime.timedelta(weeks=12))
        yesterday = activity(self.family, "E", last=SATURDAY - datetime.timedelta(days=1))
        self.assertEqual(recency_weight(never, SATURDAY), 1)
        self.assertAlmostEqual(recency_weight(last_week, SATURDAY), 0.125)
        self.assertAlmostEqual(recency_weight(four_weeks, SATURDAY), 0.5)
        self.assertEqual(recency_weight(long_ago, SATURDAY), 1)
        self.assertEqual(recency_weight(yesterday, SATURDAY), 0.1)

    def test_recent_activity_is_drawn_much_less_often(self):
        fresh = activity(self.family, "Jamais faite")
        recent = activity(
            self.family, "Faite la semaine dernière", last=SATURDAY - datetime.timedelta(weeks=1)
        )
        rng = random.Random(42)
        counts = Counter(pick([fresh, recent], SATURDAY, rng).name for _ in range(3000))
        # Poids 1 contre 0,125 : ~89 % / ~11 %.
        self.assertGreater(counts["Jamais faite"], 5 * counts["Faite la semaine dernière"])
        self.assertGreater(counts["Faite la semaine dernière"], 0)

    def test_only_candidate_is_still_drawn(self):
        recent = activity(self.family, "Seule", last=SATURDAY - datetime.timedelta(days=7))
        self.assertEqual(pick([recent], SATURDAY, random.Random(1)), recent)


class DrawLifecycleTests(TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.lina = make_child_profile(self.family, "Lina")
        self.noah = make_child_profile(self.family, "Noah")
        self.games = activity(self.family, "Jeux", place=Place.HOME)
        self.park = activity(self.family, "Parc")

    def spin(self, cost=CostFilter.ANY, place=PlaceFilter.ANY, today=MONDAY):
        return draw(self.family, self.parent, today, cost, place, random.Random(7))

    def test_first_draw_creates_plan_for_next_saturday(self):
        plan = self.spin()
        self.assertEqual((plan.date, plan.status, plan.spins), (SATURDAY, PlanStatus.DRAWING, 1))
        self.assertIn(plan.activity, [self.games, self.park])

    def test_at_most_two_rerolls(self):
        for expected in range(1, MAX_SPINS + 1):
            self.assertEqual(self.spin().spins, expected)
        with self.assertRaisesMessage(DrawError, "Plus de relance"):
            self.spin()
        self.assertEqual(SaturdayPlan.objects.get().spins, MAX_SPINS)

    def test_changing_filters_does_not_reset_the_limit(self):
        self.spin(place=PlaceFilter.HOME)
        self.spin(place=PlaceFilter.OUTING)
        self.spin(cost=CostFilter.FREE)
        with self.assertRaises(DrawError):
            self.spin(place=PlaceFilter.HOME)

    def test_nothing_eligible_does_not_consume_a_spin(self):
        self.spin()
        with self.assertRaisesMessage(DrawError, "Aucune activité"):
            self.spin(cost=CostFilter.STARS)
        self.assertEqual(SaturdayPlan.objects.get().spins, 1)

    def test_accept_free_activity(self):
        plan = accept(self.spin(place=PlaceFilter.HOME))
        self.assertEqual((plan.status, plan.star_spend), (PlanStatus.PLANNED, None))
        with self.assertRaisesMessage(DrawError, "déjà prévu"):
            self.spin()

    def test_accept_star_activity_debits_pot_proportionally(self):
        earn(self.lina, 20)
        earn(self.noah, 10)
        activity(self.family, "Cirque", is_free=False, stars=15)
        plan = accept(self.spin(cost=CostFilter.STARS))
        self.assertEqual(plan.activity.name, "Cirque")
        debits = {d.person.name: d.amount for d in plan.star_spend.debits.all()}
        self.assertEqual(debits, {"Lina": 10, "Noah": 5})
        self.assertEqual(pot(self.family), 15)

    def test_cannot_accept_without_enough_stars(self):
        earn(self.lina, 15)
        activity(self.family, "Cirque", is_free=False, stars=15)
        plan = self.spin(cost=CostFilter.STARS)
        # Entre le tirage et la validation, une étoile est décochée.
        from apps.tasks.models import TaskCompletion

        TaskCompletion.objects.filter(task__person=self.lina).first().delete()
        with self.assertRaisesMessage(DrawError, "Pas assez d'étoiles"):
            accept(plan)
        plan.refresh_from_db()
        self.assertEqual(plan.status, PlanStatus.DRAWING)
        self.assertEqual(pot(self.family), 14)

    def test_cancel_refunds_and_reopens(self):
        earn(self.lina, 20)
        activity(self.family, "Cirque", is_free=False, stars=15)
        plan = accept(self.spin(cost=CostFilter.STARS))
        cancel(plan)
        self.assertEqual(pot(self.family), 20)
        self.assertFalse(SaturdayPlan.objects.exists())
        self.assertEqual(self.spin().spins, 1)

    def test_drawing_plan_cannot_be_cancelled(self):
        with self.assertRaisesMessage(DrawError, "Seul un plan validé"):
            cancel(self.spin())

    def test_past_saturday_goes_to_history(self):
        plan = accept(self.spin(place=PlaceFilter.HOME))
        close_past_plans(self.family, SATURDAY)  # le samedi même : rien ne bouge
        plan.refresh_from_db()
        self.assertEqual(plan.status, PlanStatus.PLANNED)
        close_past_plans(self.family, SATURDAY + datetime.timedelta(days=1))
        plan.refresh_from_db()
        self.games.refresh_from_db()
        self.assertEqual(plan.status, PlanStatus.DONE)
        self.assertEqual(self.games.last_done_on, SATURDAY)

    def test_unvalidated_draw_is_abandoned_after_saturday(self):
        self.spin()
        close_past_plans(self.family, SATURDAY + datetime.timedelta(days=1))
        self.assertFalse(SaturdayPlan.objects.exists())


class SeedTests(TestCase):
    def test_new_family_gets_default_catalog(self):
        family = create_family(user=make_user(), name="Les Martin").family
        self.assertEqual(
            SaturdayActivity.objects.for_family(family).count(), len(DEFAULT_ACTIVITIES)
        )

    def test_default_catalog_is_varied(self):
        family = create_family(user=make_user(), name="X").family
        activities = SaturdayActivity.objects.for_family(family)
        self.assertEqual(
            set(activities.values_list("place", flat=True)), {Place.OUTING, Place.HOME}
        )
        self.assertEqual(len(set(activities.values_list("season", flat=True))), 5)
        self.assertTrue(
            activities.filter(is_free=True).exists() and activities.filter(is_free=False).exists()
        )
        self.assertTrue(activities.filter(star_cost__gt=0).exists())
        for season in (Season.SPRING, Season.SUMMER, Season.AUTUMN, Season.WINTER):
            self.assertTrue(activities.in_season(season).filter(place=Place.HOME).exists())

    def test_seed_is_idempotent(self):
        family = Family.objects.create(name="X", invite_code="")
        self.assertEqual(seed_default_activities(family), len(DEFAULT_ACTIVITIES))
        self.assertEqual(seed_default_activities(family), 0)


class WheelTests(TestCase):
    def setUp(self):
        self.family = make_family()

    def test_chosen_appears_once_and_lands_under_pointer(self):
        from apps.saturday.wheel import build_wheel

        chosen = activity(self.family, "Cirque")
        decor = [activity(self.family, f"Décor {i}") for i in range(6)]
        wheel = build_wheel([chosen], chosen, random.Random(3), decor=decor)
        labels = [s.label for s in wheel["segments"]]
        self.assertEqual(labels.count("Cirque"), 1)
        self.assertEqual(len(labels), 7)
        step = 360 / len(labels)
        middle = labels.index("Cirque") * step + step / 2
        self.assertAlmostEqual((wheel["rotation"] + middle) % 360, 0, places=1)
        self.assertGreaterEqual(wheel["rotation"], 5 * 360)
