import datetime

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.absences.selectors import absences_on
from apps.families.access import parent_required
from apps.stars.services import award_day_star

from .forms import ChoreForm
from .models import HouseholdChore, monday_of
from .selectors import set_chore_done
from .week import build_week

WEEK_PARAM = "semaine"


def requested_monday(request) -> datetime.date:
    """Lundi de la semaine demandée (?semaine=AAAA-MM-JJ), sinon semaine en cours."""
    raw = request.GET.get(WEEK_PARAM)
    if raw:
        try:
            return monday_of(datetime.date.fromisoformat(raw))
        except ValueError as error:
            raise Http404 from error
    return monday_of(timezone.localdate())


@require_GET
@parent_required
def week(request):
    """Semainier parent : grille horaire de la semaine, et détail du jour choisi
    (?jour=AAAA-MM-JJ) avec le ménage à cocher."""
    monday = requested_monday(request)
    try:
        selected = datetime.date.fromisoformat(request.GET.get("jour", ""))
    except ValueError:
        selected = None
    return render(
        request,
        "parent/week.html",
        {"nav_active": "week", **build_week(request.family, monday, selected)},
    )


@require_POST
@parent_required
def toggle(request, pk, day):
    """Coche une tâche de ménage pour un jour (endpoint HTMX, parents)."""
    try:
        date = datetime.date.fromisoformat(day)
    except ValueError as error:
        raise Http404 from error
    chore = get_object_or_404(HouseholdChore.objects.for_family(request.family), pk=pk)
    if not chore.occurs_on(date) or absences_on(request.family, date).is_absent(chore.assignee_id):
        raise Http404
    done = request.POST.get("done") == "on"
    set_chore_done(chore, date, done)
    if done:
        award_day_star(chore.assignee, date)
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(status=204)
    return redirect(f"{reverse('household:week')}?{WEEK_PARAM}={monday_of(date).isoformat()}")


@require_http_methods(["GET", "POST"])
@parent_required
def manage(request):
    """Réglages → ménage : liste et ajout (parents uniquement)."""
    form = ChoreForm(request.POST or None, family=request.family)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("household:manage")
    return render(
        request,
        "parent/chores_manage.html",
        {
            "nav_active": "settings",
            "form": form,
            "chores": HouseholdChore.objects.for_family(request.family).select_related("assignee"),
        },
        status=400 if form.is_bound and form.errors else 200,
    )


@require_POST
@parent_required
def delete(request, pk):
    get_object_or_404(HouseholdChore.objects.for_family(request.family), pk=pk).delete()
    return redirect("household:manage")
