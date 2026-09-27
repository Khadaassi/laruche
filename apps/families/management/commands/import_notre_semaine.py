"""Reprise ponctuelle des données de notre-semaine dans La Ruche.

Commande à usage unique, pas du code applicatif. Elle lit un **instantané JSON**
produit hors du repo (lecture seule de l'ancienne base, voir le compte-rendu de la
reprise) : aucun code de l'ancienne application n'est importé ici.

Par défaut : **simulation** (dry-run). Rien n'est écrit, seules des lectures sont faites
dans la base La Ruche ; la commande affiche tout ce qui serait créé et l'empreinte
SHA-256 de l'instantané.

Écriture réelle : `--commit --expect-sha <empreinte du dry-run validé>`. Garde-fous :
- l'empreinte doit être celle du dry-run validé (on écrit exactement ce qui a été montré) ;
- les étoiles sont relues EN DIRECT dans l'ancienne base (variable d'environnement
  `LEGACY_DATABASE_URL`, connexion en lecture seule) et doivent être identiques à
  l'instantané, sinon rien n'est écrit ;
- jamais deux fois : refus si la famille existe déjà, si le compte parent appartient déjà
  à une famille, ou si un solde de départ « notre-semaine » existe ; tout se fait dans une
  seule transaction, sous verrou consultatif (PostgreSQL), et la contrainte OneToOne du
  solde de départ empêche en base tout doublon d'étoiles.
"""

import hashlib
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.families.models import Family, FamilyMembership, Person, Role, next_avatar_color
from apps.families.services import create_family
from apps.household.models import HouseholdChore
from apps.stars.models import StarOpeningBalance
from apps.stars.services import grant_opening_balance
from apps.tasks.models import Task, weekdays_to_mask
from apps.tasks.periods import Period

SNAPSHOT_FORMAT = "notre-semaine-snapshot/1"
OPENING_REASON = "Reprise de notre-semaine"
ADVISORY_LOCK_KEY = 7_411_202_609  # arbitraire, propre à cette reprise
DAY_LABELS = ["L", "Ma", "Me", "J", "V", "S", "D"]
CHILD_KEYS = ("fille", "fils")


def read_legacy_stars(url: str) -> dict[str, int]:
    """Totaux d'étoiles actuels dans notre-semaine ({clé: total}), en lecture seule."""
    import psycopg

    with psycopg.connect(url, options="-c default_transaction_read_only=on") as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SELECT person, total FROM planner_kidstars WHERE family_id = 1")
            totals = dict(cur.fetchall())
        conn.rollback()
    return totals


@dataclass
class Plan:
    snapshot: dict
    sha: str
    parent_email: str
    papa_email: str | None
    blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def people(self) -> dict:
        return {p["key"]: p for p in self.snapshot["people"]}

    @property
    def family_name(self) -> str:
        return self.snapshot["source"]["family_name"]

    def star_totals(self) -> dict[str, int]:
        return {key: data["total"] for key, data in self.snapshot["stars"].items()}


def load_snapshot(path: str) -> tuple[dict, str]:
    raw = Path(path).read_bytes()
    try:
        snapshot = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CommandError(f"Instantané illisible : {error}") from error
    if snapshot.get("format") != SNAPSHOT_FORMAT:
        raise CommandError(f"Format d'instantané inattendu (attendu : {SNAPSHOT_FORMAT}).")
    keys = {p["key"] for p in snapshot["people"]}
    if not set(CHILD_KEYS) <= keys or not {"maman", "papa"} <= keys:
        raise CommandError("Instantané incomplet : il faut maman, papa, fille et fils.")
    for task in snapshot["tasks"]:
        if task["person"] not in CHILD_KEYS or task["period"] not in Period.values:
            raise CommandError(f"Tâche invalide dans l'instantané : {task}")
        if not task["weekdays"] or not set(task["weekdays"]) <= set(range(7)):
            raise CommandError(f"Jours invalides : {task}")
    for chore in snapshot["chores"]:
        if chore["person"] not in ("maman", "papa") or not chore["weekdays"]:
            raise CommandError(f"Ménage invalide dans l'instantané : {chore}")
    return snapshot, hashlib.sha256(raw).hexdigest()


def check_database(plan: Plan) -> None:
    """Contrôles en lecture seule ; chaque problème bloque l'écriture réelle."""
    parent = User.objects.filter(email__iexact=plan.parent_email).first()
    if parent is None:
        plan.blockers.append(f"Compte parent introuvable : {plan.parent_email}.")
    else:
        membership = FamilyMembership.objects.filter(user=parent).select_related("family").first()
        if membership is not None:
            plan.blockers.append(
                f"{plan.parent_email} appartient encore à « {membership.family.name} » : "
                "supprimer cette famille d'abord (le compte, lui, est gardé)."
            )
    if plan.papa_email and User.objects.filter(email__iexact=plan.papa_email).exists():
        plan.blockers.append(f"Un compte existe déjà pour {plan.papa_email}.")
    if Family.objects.filter(name=plan.family_name).exists():
        plan.blockers.append(
            f"Une famille « {plan.family_name} » existe déjà : reprise déjà faite ?"
        )
    if StarOpeningBalance._meta.db_table not in connection.introspection.table_names():
        plan.blockers.append(
            "Table du solde de départ absente : fusionner et déployer la PR « starting star "
            "balance » (migration stars.0004) avant l'écriture."
        )
    elif StarOpeningBalance.objects.filter(reason=OPENING_REASON).exists():
        plan.blockers.append(
            "Un solde de départ « notre-semaine » existe déjà : reprise déjà faite."
        )


def check_live_stars(plan: Plan, url: str | None) -> dict[str, int] | None:
    if not url:
        plan.notes.append("Étoiles non relues en direct (LEGACY_DATABASE_URL absente).")
        return None
    live = read_legacy_stars(url)
    expected = plan.star_totals()
    if {k: live.get(k) for k in expected} != expected:
        plan.blockers.append(
            f"Les étoiles ont bougé dans notre-semaine depuis l'instantané : {live} "
            f"au lieu de {expected}. Refaire l'instantané et le dry-run."
        )
    return live


def days_label(days) -> str:
    return " ".join(DAY_LABELS[d] for d in sorted(days))


class Command(BaseCommand):
    help = "Reprise ponctuelle de notre-semaine (dry-run par défaut)."

    def add_arguments(self, parser):
        parser.add_argument("snapshot", help="Instantané JSON (lecture seule de notre-semaine).")
        parser.add_argument("--parent-email", required=True, help="Compte La Ruche de Khadija.")
        parser.add_argument("--parent-first-name", default="Khadija")
        parser.add_argument("--papa-email", help="Compte à créer pour Lhousseine (facultatif).")
        parser.add_argument("--papa-first-name", default="Lhousseine")
        parser.add_argument("--commit", action="store_true", help="Écrire pour de vrai.")
        parser.add_argument("--expect-sha", help="Empreinte de l'instantané validé au dry-run.")

    def handle(self, *args, **options):
        snapshot, sha = load_snapshot(options["snapshot"])
        plan = Plan(snapshot, sha, options["parent_email"].strip(), options["papa_email"])
        check_database(plan)
        live = check_live_stars(plan, os.environ.get("LEGACY_DATABASE_URL"))
        self.report(plan, options, live)

        if not options["commit"]:
            self.stdout.write(self.style.WARNING("\nDRY-RUN : rien n'a été écrit."))
            return
        if options["expect_sha"] != sha:
            raise CommandError("--expect-sha ne correspond pas à l'instantané : rien n'est écrit.")
        if live is None:
            raise CommandError("--commit exige LEGACY_DATABASE_URL (relecture des étoiles).")
        if plan.blockers:
            raise CommandError("Écriture refusée : " + " | ".join(plan.blockers))
        password = self.apply(plan, options)
        self.stdout.write(self.style.SUCCESS("\nReprise écrite."))
        if password:
            self.stdout.write(f"Mot de passe provisoire de {plan.papa_email} : {password}")
            self.stdout.write("(affiché une seule fois, jamais enregistré en clair)")

    # --- Affichage ----------------------------------------------------------------

    def report(self, plan: Plan, options, live) -> None:
        w = self.stdout.write
        src = plan.snapshot["source"]
        people = plan.people
        w(f"Instantané : {options['snapshot']}")
        w(f"SHA-256    : {plan.sha}")
        w(f"Lu dans notre-semaine le {src['read_at']} (semaine type du {src['reference_week']})")
        w(f"\n== Famille « {plan.family_name} » (nouvelle, code d'invitation généré)")
        w(
            f"- {people['maman']['name']} : parent, compte existant {plan.parent_email} "
            f"(prénom du compte → {options['parent_first_name']})"
        )
        if plan.papa_email:
            w(
                f"- {people['papa']['name']} : parent, NOUVEAU compte {plan.papa_email} "
                f"(prénom {options['papa_first_name']}, mot de passe provisoire affiché une fois)"
            )
        else:
            w(f"- {people['papa']['name']} : parent, SANS compte (e-mail non fourni)")
        for key in CHILD_KEYS:
            w(f"- {people[key]['name']} : enfant, sans compte (écran partagé)")

        w("\n== Étoiles (solde de départ, exact)")
        for key in CHILD_KEYS:
            data = plan.snapshot["stars"][key]
            now = f", relu en direct : {live.get(key)}" if live is not None else ""
            w(
                f"- {people[key]['name']} : {data['total']} ★ "
                f"(historique notre-semaine : {data['star_award_rows']} journées{now})"
            )

        for key in CHILD_KEYS:
            tasks = [t for t in plan.snapshot["tasks"] if t["person"] == key]
            w(f"\n== Tâches de {people[key]['name']} ({len(tasks)})")
            for period in Period:
                block = [t for t in tasks if t["period"] == period.value]
                w(f"  {period.label} ({len(block)})")
                for t in sorted(block, key=lambda t: t["position"]):
                    w(f"    {t['position']:>2}. {t['title']:<52} {days_label(t['weekdays'])}")

        w(f"\n== Ménage des parents ({len(plan.snapshot['chores'])}, chaque semaine)")
        for c in plan.snapshot["chores"]:
            w(f"- {people[c['person']]['name']:<6} {c['title']:<52} {days_label(c['weekdays'])}")

        skipped = plan.snapshot["skipped"]
        w(f"\n== Non repris ({len(skipped)} lignes de routine)")
        for why in sorted({s["why"] for s in skipped}):
            titles = sorted(
                {
                    f"{people[s['person']]['name']} · {s['title']}"
                    for s in skipped
                    if s["why"] == why
                }
            )
            w(f"- {why} : " + " ; ".join(titles))
        if src.get("active_exceptions") or src.get("future_day_modes"):
            upcoming = [*src.get("active_exceptions", []), *src.get("future_day_modes", [])]
            w(f"- Exceptions / modes de journée à venir : {upcoming}")
        else:
            w("- Exceptions et modes de journée à venir : aucun")

        for note in plan.notes:
            w(f"\nNote : {note}")
        if plan.blockers:
            w(self.style.ERROR("\n== Bloquants pour l'écriture réelle"))
            for blocker in plan.blockers:
                w(self.style.ERROR(f"- {blocker}"))
        else:
            w(self.style.SUCCESS("\nAucun bloquant."))

    # --- Écriture -----------------------------------------------------------------

    @transaction.atomic
    def apply(self, plan: Plan, options) -> str | None:
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [ADVISORY_LOCK_KEY])
        # Revérifié sous verrou : une exécution concurrente a pu passer entre-temps.
        plan.blockers.clear()
        check_database(plan)
        if plan.blockers:
            raise CommandError("Écriture refusée : " + " | ".join(plan.blockers))

        people = plan.people
        today = timezone.localdate()
        parent = User.objects.get(email__iexact=plan.parent_email)
        parent.first_name = options["parent_first_name"]
        parent.save(update_fields=["first_name"])
        membership = create_family(user=parent, name=plan.family_name)
        family = membership.family
        persons = {"maman": Person.objects.get(user=parent)}
        persons["maman"].name = people["maman"]["name"]
        persons["maman"].save(update_fields=["name"])

        password = None
        papa_user = None
        if plan.papa_email:
            password = secrets.token_urlsafe(12)
            email = plan.papa_email.strip().lower()
            papa_user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=options["papa_first_name"],
            )
            FamilyMembership.objects.create(user=papa_user, family=family, role=Role.PARENT)
        persons["papa"] = Person.objects.create(
            family=family,
            user=papa_user,
            name=people["papa"]["name"],
            role=Role.PARENT,
            avatar_color=next_avatar_color(family),
        )
        for key in CHILD_KEYS:
            persons[key] = Person.objects.create(
                family=family,
                name=people[key]["name"],
                role=Role.CHILD,
                avatar_color=next_avatar_color(family),
            )

        Task.objects.bulk_create(
            Task(
                person=persons[t["person"]],
                title=t["title"],
                period=t["period"],
                weekdays=weekdays_to_mask(t["weekdays"]),
                position=t["position"],
            )
            for t in plan.snapshot["tasks"]
        )
        HouseholdChore.objects.bulk_create(
            HouseholdChore(
                family=family,
                title=c["title"],
                assignee=persons[c["person"]],
                weekdays=weekdays_to_mask(c["weekdays"]),
                interval_weeks=1,
                start_date=today,
            )
            for c in plan.snapshot["chores"]
        )
        for key in CHILD_KEYS:
            total = plan.snapshot["stars"][key]["total"]
            if total > 0:
                grant_opening_balance(persons[key], total, OPENING_REASON)

        self.stdout.write(f"Famille créée : {family.name} (code d'invitation {family.invite_code})")
        return password
