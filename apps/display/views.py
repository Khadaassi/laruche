import datetime

from django.contrib.auth import login, logout
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.forms import LoginForm
from apps.celebrations.models import Celebration
from apps.celebrations.services import roll_over_recurring
from apps.core.ratelimit import BLOCKED_MESSAGE
from apps.families.access import parent_required
from apps.families.models import Person
from apps.household.models import HouseholdChore
from apps.household.selectors import chores_by_day, set_chore_done
from apps.household.views import requested_monday
from apps.household.week import build_week
from apps.meals.week import build_menu_week
from apps.saturday.draw import DrawError, accept, close_past_plans, current_plan
from apps.saturday.models import PlanStatus, SaturdayPlan
from apps.saturday.views import draw_context, perform_spin
from apps.school.models import Lunch
from apps.school.selectors import school_days_for
from apps.stars.selectors import balances
from apps.stars.services import claim_tier_celebration
from apps.tasks.periods import PERIOD_PHRASES, current_period, seconds_until_next_period
from apps.tasks.selectors import group_by_person, tasks_for_day
from apps.tasks.services import set_done

from .access import (
    can_tick,
    delete_device_cookie,
    get_device,
    set_device_cookie,
    shared_display_required,
)
from .forms import DeviceForm
from .models import SharedDisplayDevice
from .parent_check import check_parent_password
from .wheel_unlock import grant as grant_wheel
from .wheel_unlock import revoke as revoke_wheel
from .wheel_unlock import wheel_parent


def child_columns(request, person=None):
    """Colonnes de la période en cours : une par enfant de la famille (ou une seule).

    Toujours tous les enfants, quel que soit le visiteur ; seule la
    possibilité de cocher (`column.tickable`) dépend de lui. Chaque colonne
    porte aussi la journée d'école du jour et un rappel pour demain.
    """
    today, period = timezone.localdate(), current_period()
    tomorrow = today + datetime.timedelta(days=1)
    children = Person.objects.for_family(request.family).children()
    if person is not None:
        children = children.filter(pk=person.pk)
    tasks = tasks_for_day(request.family, today, people=children, period=period)
    school_today = school_days_for(request.family, today, people=children)
    school_tomorrow = school_days_for(request.family, tomorrow, people=children)
    chores_today = chores_by_day(request.family, today, 1)[today]
    stars = balances(request.family, people=children)
    columns = group_by_person(children, tasks)
    for column in columns:
        column.stars = stars.get(column.person.pk)
        # Nouveau palier atteint : fêté une seule fois, sur cet écran.
        column.celebrate_tier = claim_tier_celebration(column.stars) if column.stars else None
        # Ménage du jour de l'enfant (toutes périodes), coché comme ses tâches.
        column.chores = [o for o in chores_today if o.chore.assignee_id == column.person.pk]
        column.tickable = can_tick(request, column.person)
        column.school = school_today.get(column.person.pk)
        column.tomorrow = tomorrow_hint(school_tomorrow.get(column.person.pk))
    return columns


def tomorrow_hint(day) -> str:
    """Rappel court pour la colonne d'un enfant (sandwich, pas d'école)."""
    if day is None:
        return ""
    if day.lunch == Lunch.PACKED:
        return "Demain : sandwich"
    if day.lunch == Lunch.NONE and day.is_override:
        return "Demain : pas d'école"
    return ""


@require_GET
@shared_display_required
def board(request):
    """Affichage partagé : une colonne par enfant, tâches de la période en cours."""
    period = current_period()
    today = timezone.localdate()
    close_past_plans(request.family, today)
    plan = current_plan(request.family, today)
    return render(
        request,
        "shared/board.html",
        {
            "saturday_plan": plan if plan and plan.status == PlanStatus.PLANNED else None,
            "columns": child_columns(request),
            "period": period,
            "period_phrase": PERIOD_PHRASES[period],
            "today": timezone.localdate(),
            "reload_in": seconds_until_next_period(),
        },
    )


@require_GET
@shared_display_required
def week(request):
    """Semainier en lecture seule : une colonne par jour (ménage, école, fêtes)."""
    return render(
        request,
        "shared/week.html",
        {
            "today": timezone.localdate(),
            "reload_in": seconds_until_next_period(),
            **build_week(request.family, requested_monday(request)),
        },
    )


@require_GET
@shared_display_required
def menu(request):
    """Menu de la semaine en lecture seule : une colonne par jour.

    Ni recettes détaillées ni liste de courses sur l'écran partagé.
    """
    return render(
        request,
        "shared/menu.html",
        {
            "today": timezone.localdate(),
            "reload_in": seconds_until_next_period(),
            **build_menu_week(request.family, requested_monday(request)),
        },
    )


@require_GET
@shared_display_required
def celebrations(request):
    """Fêtes à venir en lecture seule : préparatifs et recettes.

    La liste de cadeaux n'est jamais montrée sur l'écran partagé : les
    enfants la verraient, surprise gâchée.
    """
    roll_over_recurring(request.family, timezone.localdate())
    upcoming = (
        Celebration.objects.for_family(request.family)
        .filter(date__gte=timezone.localdate())
        .prefetch_related("todos__assignee", "recipes")[:6]
    )
    return render(
        request,
        "shared/celebrations.html",
        {
            "today": timezone.localdate(),
            "reload_in": seconds_until_next_period(),
            "celebrations": upcoming,
        },
    )


@require_POST
@shared_display_required
def toggle(request, person_pk, task_pk):
    """Coche la tâche d'un enfant depuis sa colonne.

    L'enfant ciblé doit être un enfant de la famille, et la tâche doit être
    la sienne : une colonne ne touche jamais une autre. Un compte enfant ne
    coche que sa propre colonne (403 sinon).
    """
    today = timezone.localdate()
    child = get_object_or_404(Person.objects.for_family(request.family).children(), pk=person_pk)
    if not can_tick(request, child):
        raise PermissionDenied("Un enfant ne coche que sa propre colonne.")
    task = get_object_or_404(child.tasks.scheduled_on(today), pk=task_pk)
    by = request.user if request.user.is_authenticated else None
    set_done(task, today, request.POST.get("done") == "on", by=by)
    if request.headers.get("HX-Request") != "true":
        return redirect("display:board")
    return render(request, "shared/_column_oob.html", {"column": child_columns(request, child)[0]})


@require_POST
@shared_display_required
def toggle_chore(request, person_pk, chore_pk):
    """Coche une tâche de ménage d'un enfant depuis sa colonne.

    Mêmes règles que les tâches : l'enfant ciblé est un enfant de la
    famille, la tâche de ménage lui est assignée et prévue aujourd'hui, et
    un compte enfant ne coche que sa propre colonne. Une tâche de ménage
    assignée à un parent n'est jamais atteignable ici (404).
    """
    today = timezone.localdate()
    child = get_object_or_404(Person.objects.for_family(request.family).children(), pk=person_pk)
    if not can_tick(request, child):
        raise PermissionDenied("Un enfant ne coche que sa propre colonne.")
    chore = get_object_or_404(
        HouseholdChore.objects.for_family(request.family).filter(assignee=child), pk=chore_pk
    )
    if not chore.occurs_on(today):
        raise Http404
    set_chore_done(chore, today, request.POST.get("done") == "on")
    if request.headers.get("HX-Request") != "true":
        return redirect("display:board")
    return render(request, "shared/_column_oob.html", {"column": child_columns(request, child)[0]})


# --- Roue du samedi sur l'écran partagé ---------------------------------------


def _saturday_context(request, **extra):
    return draw_context(
        request.family,
        today=timezone.localdate(),
        reload_in=seconds_until_next_period(),
        spin_url_name="display:saturday_spin",
        validate_url_name="display:saturday_validate",
        **extra,
    )


@require_GET
@shared_display_required
def saturday(request):
    """Roue du samedi en grand, pour que toute la famille la regarde tourner.

    Lancement réservé à un parent : confirmation par mot de passe si l'écran
    n'est pas déjà ouvert par un parent.
    """
    parent = wheel_parent(request)
    context = _saturday_context(request, unlocked=parent is not None)
    if parent is None:
        context["form"] = LoginForm(request)
    return render(request, "shared/saturday.html", context)


@sensitive_post_parameters("password")
@require_POST
@shared_display_required
def saturday_unlock(request):
    """Un parent confirme son mot de passe : la roue est lançable 10 minutes."""
    check = check_parent_password(request, request.family)
    if check.user is not None:
        grant_wheel(request, request.family, check.user)
        return redirect("display:saturday")
    context = _saturday_context(
        request,
        unlocked=False,
        form=check.form,
        blocked=BLOCKED_MESSAGE if check.blocked else "",
    )
    return render(request, "shared/saturday.html", context, status=429 if check.blocked else 400)


@require_POST
@shared_display_required
def saturday_spin(request):
    """Un tour de roue depuis l'écran partagé : mêmes règles que sur le téléphone."""
    parent = wheel_parent(request)
    if parent is None:
        raise PermissionDenied("Un parent doit confirmer avant de lancer la roue.")
    context, status = perform_spin(
        request.family,
        parent,
        request.POST,
        spin_url_name="display:saturday_spin",
        validate_url_name="display:saturday_validate",
    )
    context.update(today=timezone.localdate(), unlocked=True, wheel_size="max-w-md")
    template = (
        "parent/_saturday_draw.html"
        if request.headers.get("HX-Request") == "true"
        else "shared/saturday.html"
    )
    return render(request, template, context, status=status)


@require_POST
@shared_display_required
def saturday_validate(request, pk):
    """« On y va ! » depuis l'écran partagé : validé au nom du parent qui a confirmé."""
    if wheel_parent(request) is None:
        raise PermissionDenied("Un parent doit confirmer avant de valider.")
    plan = get_object_or_404(SaturdayPlan.objects.for_family(request.family), pk=pk)
    try:
        accept(plan)
    except DrawError as error:
        context = _saturday_context(request, unlocked=True, draw_error=str(error))
        return render(request, "shared/saturday.html", context, status=422)
    revoke_wheel(request)
    return redirect("display:board")


@require_POST
@parent_required
def activate(request):
    """Transforme cet appareil en affichage partagé et ferme la session parent."""
    form = DeviceForm(request.POST)
    name = form.cleaned_data["name"] if form.is_valid() else "Tablette"
    _, raw = SharedDisplayDevice.create_for(
        family=request.family, name=name, created_by=request.user
    )
    logout(request)
    response = redirect("display:board")
    set_device_cookie(response, raw)
    return response


@require_POST
@parent_required
def revoke(request, pk):
    device = get_object_or_404(
        SharedDisplayDevice.objects.for_family(request.family).active(), pk=pk
    )
    device.revoke()
    return redirect("families:settings")


@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def exit_display(request):
    """Quitter le mode : ré-authentification d'un parent de CETTE famille."""
    device = get_device(request)
    if device is None:
        return redirect("display:board")
    request.display_device = device
    check = check_parent_password(request, device.family)
    if check.user is not None:
        device.revoke()
        login(request, check.user)
        response = redirect("tasks:home")
        delete_device_cookie(response)
        return response
    context = {"form": check.form, "blocked": BLOCKED_MESSAGE if check.blocked else ""}
    return render(request, "shared/exit.html", context, status=429 if check.blocked else 200)
