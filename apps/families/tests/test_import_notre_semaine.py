"""Reprise ponctuelle de notre-semaine : dry-run, écriture, jamais deux fois."""

import hashlib
import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.families.models import Family, Person, Role
from apps.families.tests.factories import join, make_family, make_user
from apps.household.models import HouseholdChore
from apps.stars.models import StarOpeningBalance
from apps.stars.selectors import balances
from apps.tasks.models import Task, mask_to_weekdays

READER = "apps.families.management.commands.import_notre_semaine.read_legacy_stars"

SNAPSHOT = {
    "format": "notre-semaine-snapshot/1",
    "source": {
        "family_id": 1,
        "family_name": "Famille Reprise",
        "read_at": "2026-09-27T20:00:00+00:00",
        "reference_week": "2026-10-05",
        "active_exceptions": [],
        "future_day_modes": [],
    },
    "people": [
        {"key": "maman", "name": "Maman", "role": "parent"},
        {"key": "papa", "name": "Papa", "role": "parent"},
        {"key": "fille", "name": "Inès", "role": "child"},
        {"key": "fils", "name": "Adam", "role": "child"},
    ],
    "stars": {
        "fille": {"total": 7, "star_award_rows": 7, "last_award": "2026-09-27"},
        "fils": {"total": 5, "star_award_rows": 5, "last_award": "2026-09-26"},
    },
    "tasks": [
        {
            "person": "fille",
            "period": "morning",
            "position": 0,
            "title": "Faire son lit",
            "weekdays": [0, 1, 2, 3, 4, 5, 6],
            "legacy_ids": ["lit"],
        },
        {
            "person": "fille",
            "period": "evening",
            "position": 0,
            "title": "Prière",
            "weekdays": [0, 1, 2, 3, 4],
            "legacy_ids": ["priere1"],
        },
        {
            "person": "fille",
            "period": "evening",
            "position": 1,
            "title": "Prière",
            "weekdays": [0, 1, 2, 3, 4],
            "legacy_ids": ["priere2"],
        },
        {
            "person": "fils",
            "period": "evening",
            "position": 0,
            "title": "Lutte",
            "weekdays": [0, 2],
            "legacy_ids": ["activite_2", "activite_5"],
        },
    ],
    "chores": [
        {"person": "maman", "title": "Laver le frigo", "weekdays": [5], "legacy_id": "frigo"},
        {"person": "papa", "title": "Aider à la lessive", "weekdays": [6], "legacy_id": "lessive"},
    ],
    "skipped": [
        {
            "person": "fille",
            "period": "noon",
            "title": "École",
            "weekdays": [0],
            "legacy_id": "ecole",
            "why": "non cochable (information)",
        },
    ],
}


class ImportNotreSemaineTests(TestCase):
    def setUp(self):
        self.parent = make_user(first_name="Parent Test", email="parent@example.test")
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(SNAPSHOT, tmp, ensure_ascii=False)
        self.path = tmp.name
        self.addCleanup(Path(self.path).unlink)
        self.sha = hashlib.sha256(Path(self.path).read_bytes()).hexdigest()

    def run_command(self, *extra, live=None, env=True):
        out = StringIO()
        environ = {"LEGACY_DATABASE_URL": "postgresql://lecture-seule"} if env else {}
        live = live if live is not None else {"fille": 7, "fils": 5}
        with mock.patch.dict("os.environ", environ), mock.patch(READER, return_value=live):
            call_command(
                "import_notre_semaine",
                self.path,
                "--parent-email",
                "parent@example.test",
                *extra,
                stdout=out,
            )
        return out.getvalue()

    def commit(self, *extra, **kwargs):
        return self.run_command("--commit", "--expect-sha", self.sha, *extra, **kwargs)

    def test_dry_run_writes_nothing_and_shows_everything(self):
        out = self.run_command()
        self.assertIn(self.sha, out)
        self.assertIn("DRY-RUN : rien n'a été écrit.", out)
        self.assertIn("Inès : 7 ★", out)
        self.assertIn("Adam : 5 ★", out)
        self.assertIn("Lutte", out)
        self.assertIn("Aucun bloquant.", out)
        self.assertFalse(Family.objects.exists())
        self.assertFalse(Task.objects.exists())

    def test_commit_creates_family_tasks_chores_and_exact_stars(self):
        out = self.commit("--papa-email", "papa@example.test")
        self.assertIn("Reprise écrite.", out)
        self.assertIn("Mot de passe provisoire de papa@example.test", out)
        family = Family.objects.get(name="Famille Reprise")
        people = {p.name: p for p in Person.objects.for_family(family)}
        self.assertEqual(set(people), {"Maman", "Papa", "Inès", "Adam"})
        self.assertEqual(people["Maman"].user, self.parent)
        self.assertEqual(self.parent.membership.role, Role.PARENT)
        self.assertEqual(people["Papa"].user.membership.role, Role.PARENT)
        self.assertEqual(people["Papa"].role, Role.PARENT)
        self.assertTrue(people["Papa"].user.check_password(out.split(": ")[-1].split()[0]))
        stars = balances(family)
        self.assertEqual(stars[people["Inès"].pk].earned, 7)
        self.assertEqual(stars[people["Adam"].pk].earned, 5)
        # Les deux « Prière » du même soir restent deux tâches distinctes.
        prayers = Task.objects.filter(person=people["Inès"], title="Prière").order_by("position")
        self.assertEqual([t.position for t in prayers], [0, 1])
        lutte = Task.objects.get(person=people["Adam"])
        self.assertEqual(mask_to_weekdays(lutte.weekdays), [0, 2])
        self.assertEqual(HouseholdChore.objects.filter(family=family).count(), 2)
        self.assertFalse(Task.objects.filter(title="École").exists())
        # Le catalogue du samedi est créé comme pour toute nouvelle famille.
        self.assertEqual(family.saturday_activities.count(), 18)

    def test_never_twice(self):
        self.commit()
        with self.assertRaisesMessage(CommandError, "Écriture refusée"):
            self.commit()
        self.assertEqual(Family.objects.count(), 1)
        self.assertEqual(StarOpeningBalance.objects.count(), 2)
        self.assertEqual(Task.objects.count(), 4)

    def test_dry_run_after_import_reports_it(self):
        self.commit()
        out = self.run_command()
        self.assertIn("reprise déjà faite", out)

    def test_wrong_sha_writes_nothing(self):
        with self.assertRaisesMessage(CommandError, "--expect-sha"):
            self.run_command("--commit", "--expect-sha", "0" * 64)
        self.assertFalse(Family.objects.exists())

    def test_stars_that_moved_since_the_snapshot_block_the_write(self):
        with self.assertRaisesMessage(CommandError, "Les étoiles ont bougé"):
            self.commit(live={"fille": 8, "fils": 5})
        self.assertFalse(Family.objects.exists())

    def test_commit_requires_the_live_star_check(self):
        with self.assertRaisesMessage(CommandError, "LEGACY_DATABASE_URL"):
            self.commit(env=False)
        self.assertFalse(Family.objects.exists())

    def test_parent_still_in_another_family_blocks(self):
        other = make_family(name="Famille Test")
        user = join(other, "Parent Test")
        user.email = "parent@example.test"
        user.save()
        self.parent.email = "autre@example.test"
        self.parent.save()
        out = self.run_command()
        self.assertIn("appartient encore à « Famille Test »", out)
        with self.assertRaisesMessage(CommandError, "Écriture refusée"):
            self.commit()
        self.assertFalse(Family.objects.filter(name="Famille Reprise").exists())

    def test_unknown_parent_blocks(self):
        self.parent.delete()
        with self.assertRaisesMessage(CommandError, "Compte parent introuvable"):
            self.commit()

    def test_papa_without_email_has_no_account(self):
        self.commit()
        papa = Person.objects.get(name="Papa")
        self.assertIsNone(papa.user)
        self.assertEqual(papa.role, Role.PARENT)
