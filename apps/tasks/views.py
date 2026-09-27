from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.preparation import tomorrow_items
from apps.families.access import family_member_required, parent_required
from apps.families.models import Person
from apps.school.selectors import school_days_for

from .forms import TaskForm
from .models import Task
from .periods import Period, period_at
from .selectors import count_remaining, group_by_period, tasks_for_day
from .services import set_done

PERSON_PARAM = "personne"


def selected_person(request, raw):
    """Personne choisie dans le sélecteur, forcément de la famille (sinon 404)."""
    if not raw:
        return None
    if not str(raw).isdigit():
        raise Http404
    return get_object_or_404(Person.objects.for_family(request.family), pk=raw)


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
    people = [person] if person else None
    tasks = tasks_for_day(request.family, now.date(), people=people)
    children = Person.objects.for_family(request.family).children()
    if person:
        children = children.filter(pk=person.pk)
    school = school_days_for(request.family, now.date(), people=children)
    return render(
        request,
        "parent/home.html",
        {
            "nav_active": "home",
            "today": now.date(),
            "people": Person.objects.for_family(request.family),
            "selected": person,
            "groups": group_by_period(tasks, current=period_at(now.time())),
            "remaining": count_remaining(tasks),
            "school_today": [(c, school[c.pk]) for c in children if c.pk in school],
            "tomorrow": tomorrow_items(request.family, now.date(), people=people),
        },
    )


@require_POST
@parent_required
def toggle(request, pk):
    """Coche / décoche une tâche du jour depuis l'accueil parent (endpoint HTMX).

    Les enfants cochent depuis l'écran partagé (display:toggle).
    """
    today = timezone.localdate()
    task = get_object_or_404(
        Task.objects.for_family(request.family).on_weekday(today.weekday()), pk=pk
    )
    set_done(task, today, request.POST.get("done") == "on", by=request.user)

    # Le filtre ne sert qu'à recalculer les compteurs affichés ; il reste
    # borné à la famille par selected_person().
    person = selected_person(request, request.POST.get(PERSON_PARAM))
    if not is_htmx(request):
        url = reverse("tasks:home")
        return redirect(f"{url}?{PERSON_PARAM}={person.pk}" if person else url)
    tasks = tasks_for_day(request.family, today, people=[person] if person else None)
    period_tasks = [t for t in tasks if t.period == task.period]
    return render(
        request,
        "parent/_counters_oob.html",
        {
            "remaining": count_remaining(tasks),
            "period": Period(task.period),
            "period_remaining": count_remaining(period_tasks),
        },
    )


@require_http_methods(["GET", "POST"])
@parent_required
def manage(request):
    """Réglages → tâches : liste et ajout (parents uniquement)."""
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
            "tasks": tasks.order_by("person__created_at", "person__pk", "period", "position", "pk"),
        },
    )


@require_POST
@parent_required
def delete(request, pk):
    get_object_or_404(Task.objects.for_family(request.family), pk=pk).delete()
    return redirect("tasks:manage")
