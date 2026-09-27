from django.contrib.auth import login, logout
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.forms import LoginForm
from apps.families.access import get_membership, parent_required
from apps.families.models import Person
from apps.tasks.periods import PERIOD_PHRASES, current_period, seconds_until_next_period
from apps.tasks.selectors import group_by_person, tasks_for_day
from apps.tasks.services import set_done

from .access import delete_device_cookie, get_device, set_device_cookie, shared_display_required
from .forms import DeviceForm
from .models import SharedDisplayDevice


def child_columns(family, person=None):
    """Colonnes de la période en cours : une par enfant (ou une seule)."""
    today, period = timezone.localdate(), current_period()
    children = Person.objects.for_family(family).children()
    if person is not None:
        children = children.filter(pk=person.pk)
    tasks = tasks_for_day(family, today, people=children, period=period)
    return group_by_person(children, tasks)


@require_GET
@shared_display_required
def board(request):
    """Affichage partagé : une colonne par enfant, tâches de la période en cours."""
    period = current_period()
    return render(
        request,
        "shared/board.html",
        {
            "columns": child_columns(request.family),
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

    L'enfant ciblé doit être un enfant de la famille de l'appareil, et la
    tâche doit être la sienne : une colonne ne touche jamais une autre.
    """
    today = timezone.localdate()
    child = get_object_or_404(Person.objects.for_family(request.family).children(), pk=person_pk)
    task = get_object_or_404(child.tasks.on_weekday(today.weekday()), pk=task_pk)
    by = request.user if request.user.is_authenticated else None
    set_done(task, today, request.POST.get("done") == "on", by=by)
    if request.headers.get("HX-Request") != "true":
        return redirect("display:board")
    return render(
        request, "shared/_column_oob.html", {"column": child_columns(request.family, child)[0]}
    )


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
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        membership = get_membership(user)
        if membership is not None and membership.is_parent and membership.family == device.family:
            device.revoke()
            login(request, user)
            response = redirect("tasks:home")
            delete_device_cookie(response)
            return response
        form.add_error(None, "Seul un parent de cette famille peut quitter l'affichage partagé.")
    return render(request, "shared/exit.html", {"form": form})
