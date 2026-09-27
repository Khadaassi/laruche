from django.contrib.auth import login, logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.forms import LoginForm
from apps.core.ratelimit import BLOCKED_MESSAGE, EXIT_DISPLAY
from apps.families.access import get_membership, parent_required
from apps.families.models import Person
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


def child_columns(request, person=None):
    """Colonnes de la période en cours : une par enfant de la famille (ou une seule).

    Toujours tous les enfants, quel que soit le visiteur ; seule la
    possibilité de cocher (`column.tickable`) dépend de lui.
    """
    today, period = timezone.localdate(), current_period()
    children = Person.objects.for_family(request.family).children()
    if person is not None:
        children = children.filter(pk=person.pk)
    tasks = tasks_for_day(request.family, today, people=children, period=period)
    columns = group_by_person(children, tasks)
    for column in columns:
        column.tickable = can_tick(request, column.person)
    return columns


@require_GET
@shared_display_required
def board(request):
    """Affichage partagé : une colonne par enfant, tâches de la période en cours."""
    period = current_period()
    return render(
        request,
        "shared/board.html",
        {
            "columns": child_columns(request),
            "period": period,
            "period_phrase": PERIOD_PHRASES[period],
            "today": timezone.localdate(),
            "reload_in": seconds_until_next_period(),
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
    task = get_object_or_404(child.tasks.on_weekday(today.weekday()), pk=task_pk)
    by = request.user if request.user.is_authenticated else None
    set_done(task, today, request.POST.get("done") == "on", by=by)
    if request.headers.get("HX-Request") != "true":
        return redirect("display:board")
    return render(request, "shared/_column_oob.html", {"column": child_columns(request, child)[0]})


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
    form = LoginForm(request, data=request.POST or None)
    # Limite par appareil (le jeton, pas l'IP) : on ne teste pas les mots de
    # passe des parents en boucle depuis la tablette.
    target = str(device.pk)
    if request.method == "POST":
        if EXIT_DISPLAY.is_blocked(request, target=target):
            # Formulaire vierge : le mot de passe n'est même pas vérifié.
            return render(
                request,
                "shared/exit.html",
                {"form": LoginForm(request), "blocked": BLOCKED_MESSAGE},
                status=429,
            )
        if form.is_valid():
            user = form.get_user()
            membership = get_membership(user)
            if (
                membership is not None
                and membership.is_parent
                and membership.family == device.family
            ):
                device.revoke()
                login(request, user)
                response = redirect("tasks:home")
                delete_device_cookie(response)
                return response
            form.add_error(
                None, "Seul un parent de cette famille peut quitter l'affichage partagé."
            )
        EXIT_DISPLAY.record_failure(request, target=target)
    return render(request, "shared/exit.html", {"form": form})
