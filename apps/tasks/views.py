import datetime
from urllib.parse import urlencode

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.absences.models import Absence
from apps.absences.selectors import absences_on
from apps.core.preparation import tomorrow_items
from apps.families.access import family_member_required, parent_required
from apps.families.models import Person
from apps.goals.views import today_steps_for
from apps.meals.week import dinner_of
from apps.review.selectors import REVIEW_FROM_WEEKDAY, is_done, review_monday
from apps.saturday.draw import current_plan
from apps.school.selectors import school_days_for
from apps.stars.selectors import balances, pot
from apps.stars.services import award_day_star

from .forms import TaskForm
from .models import Task
from .periods import GREETINGS, Period, period_at
from .selectors import count_remaining, group_by_period, tasks_for_day
from .services import set_done

PERSON_PARAM = "personne"
PERIOD_ORDER = {period: index for index, period in enumerate(Period)}
SATURDAY = 5


def selected_person(request, raw):
    """Personne choisie dans le sélecteur, forcément de la famille (sinon 404)."""
    if not raw:
        return None
    if not str(raw).isdigit():
        raise Http404
    return get_object_or_404(Person.objects.for_family(request.family), pk=raw)


DAY_PARAM = "jour"
CORRECTION_DAYS = 7  # un parent peut corriger les cochages des 7 derniers jours


def selected_day(raw, today: datetime.date) -> datetime.date:
    """Jour choisi (?jour=AAAA-MM-JJ) : aujourd'hui par défaut, sinon un des
    `CORRECTION_DAYS` derniers jours (404 au-delà ou dans le futur)."""
    if not raw:
        return today
    try:
        day = datetime.date.fromisoformat(raw)
    except ValueError as error:
        raise Http404 from error
    if not today - datetime.timedelta(days=CORRECTION_DAYS) <= day <= today:
        raise Http404
    return day


def is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


@require_GET
@family_member_required
def home(request):
    """Accueil parent (mobile) : tâches du jour par période.

    Un compte enfant n'a pas de vue individuelle : il est envoyé sur
    l'écran partagé, seul chemin d'accès enfant (toutes les colonnes).
    """
    if not request.membership.is_parent:
        return redirect("display:board")
    person = selected_person(request, request.GET.get(PERSON_PARAM))
    now = timezone.localtime()
    day = selected_day(request.GET.get(DAY_PARAM), now.date())
    people = [person] if person else None
    tasks = tasks_for_day(request.family, day, people=people)
    children = Person.objects.for_family(request.family).children()
    if person:
        children = children.filter(pk=person.pk)
    school = school_days_for(request.family, now.date(), people=children)
    saturday_plan = current_plan(request.family, now.date())
    current = period_at(now.time())
    return render(
        request,
        "parent/home.html",
        {
            "nav_active": "home",
            "greeting": GREETINGS[current],
            # Étoiles de la famille : somme des soldes des enfants (le pot commun).
            "family_stars": pot(request.family),
            "today": now.date(),
            "people": Person.objects.for_family(request.family),
            "selected": person,
            "groups": group_by_period(tasks, current=current if day == now.date() else None),
            # Correction des jours passés (un parent coche/décoche après coup).
            "day": day,
            "is_today": day == now.date(),
            "previous_day": (
                day - datetime.timedelta(days=1)
                if day > now.date() - datetime.timedelta(days=CORRECTION_DAYS)
                else None
            ),
            "next_day": day + datetime.timedelta(days=1) if day < now.date() else None,
            "remaining": count_remaining(tasks),
            "school_today": [(c, school[c.pk]) for c in children if c.pk in school],
            "tomorrow": tomorrow_items(request.family, now.date(), people=people),
            "saturday_plan": saturday_plan,
            "is_saturday": now.date().weekday() == SATURDAY,
            "dinner": dinner_of(request.family, now.date()),
            # Mon année (privé) : petits pas du jour de la personne connectée seulement.
            "my_steps": today_steps_for(request.user, now.date()),
            # Revue du dimanche : proposée du vendredi au dimanche tant qu'elle n'est pas faite.
            "review_due": now.date().weekday() >= REVIEW_FROM_WEEKDAY
            and not is_done(request.family, review_monday(now.date())),
            "absences_today": Absence.objects.for_family(request.family)
            .overlapping(now.date(), now.date())
            .select_related("person"),
        },
    )


@require_POST
@parent_required
def toggle(request, pk):
    """Coche / décoche une tâche du jour depuis l'accueil parent (endpoint HTMX).

    Les enfants cochent depuis l'écran partagé (display:toggle).
    """
    today = selected_day(request.POST.get(DAY_PARAM), timezone.localdate())
    task = get_object_or_404(Task.objects.for_family(request.family).scheduled_on(today), pk=pk)
    if absences_on(request.family, today).is_absent(task.person_id):
        raise Http404  # tâche suspendue (vacances, malade)
    done = request.POST.get("done") == "on"
    set_done(task, today, done, by=request.user)
    day_star = done and award_day_star(task.person, today)

    # Le filtre ne sert qu'à recalculer les compteurs affichés ; il reste
    # borné à la famille par selected_person().
    person = selected_person(request, request.POST.get(PERSON_PARAM))
    if not is_htmx(request):
        params = {PERSON_PARAM: person.pk} if person else {}
        if today != timezone.localdate():
            params[DAY_PARAM] = today.isoformat()
        query = f"?{urlencode(params)}" if params else ""
        return redirect(f"{reverse('tasks:home')}{query}")
    tasks = tasks_for_day(request.family, today, people=[person] if person else None)
    period_tasks = [t for t in tasks if t.period == task.period]
    return render(
        request,
        "parent/_counters_oob.html",
        {
            "remaining": count_remaining(tasks),
            "period": Period(task.period),
            "period_remaining": count_remaining(period_tasks),
            "day_star_person": task.person if day_star else None,
            "day_star_balance": (
                balances(request.family, people=[task.person])[task.person.pk].balance
                if day_star
                else None
            ),
        },
    )


@require_http_methods(["GET", "POST"])
@parent_required
def manage(request):
    """Réglages → tâches : liste (triable), ajout pour une ou plusieurs personnes."""
    form = TaskForm(request.POST or None, family=request.family)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("tasks:manage")
    tasks = Task.objects.for_family(request.family).select_related("person")
    return render(
        request,
        "parent/tasks_manage.html",
        {
            "nav_active": "settings",
            "form": form,
            # Par personne, puis dans l'ordre de la journée (pas l'ordre alphabétique
            # des codes de période), puis dans l'ordre choisi par le parent.
            "tasks": sorted(
                tasks.order_by("position", "created_at", "pk"),
                key=lambda t: (t.person.created_at, t.person_id, PERIOD_ORDER[t.period]),
            ),
        },
        status=400 if form.is_bound and form.errors else 200,
    )


@require_http_methods(["GET", "POST"])
@parent_required
def edit(request, pk):
    task = get_object_or_404(Task.objects.for_family(request.family), pk=pk)
    form = TaskForm(request.POST or None, instance=task, family=request.family)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("tasks:manage")
    return render(
        request,
        "parent/task_edit.html",
        {"nav_active": "settings", "form": form, "task": task},
        status=400 if form.is_bound and form.errors else 200,
    )


@require_POST
@parent_required
def move(request, pk, direction):
    """Monte ou descend une tâche parmi celles de la même personne et période.

    C'est cet ordre qui s'affiche sur l'accueil parent et l'écran partagé.
    """
    task = get_object_or_404(Task.objects.for_family(request.family), pk=pk)
    siblings = list(
        Task.objects.filter(person=task.person, period=task.period).order_by(
            "position", "created_at", "pk"
        )
    )
    index = next(i for i, t in enumerate(siblings) if t.pk == task.pk)
    target = index - 1 if direction == "monter" else index + 1
    if 0 <= target < len(siblings):
        siblings[index], siblings[target] = siblings[target], siblings[index]
    for position, sibling in enumerate(siblings):
        sibling.position = position
    Task.objects.bulk_update(siblings, ["position"])
    return redirect(f"{reverse('tasks:manage')}#task-{task.pk}")


@require_POST
@parent_required
def delete(request, pk):
    get_object_or_404(Task.objects.for_family(request.family), pk=pk).delete()
    return redirect("tasks:manage")
