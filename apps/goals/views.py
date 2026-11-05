"""« Mon année » : vision board personnel. Tout est filtré sur `request.user` (privé).

Un objectif d'un autre compte (même de la famille) → 404, jamais 403 : on ne révèle
pas son existence.
"""

import datetime

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.families.access import parent_required

from .defaults import MOTTO, TAGLINE
from .forms import ContactForm, EntryForm, GoalForm, StepForm
from .models import Contact, Entry, Goal, Step
from .selectors import goal_states, year_calendar
from .services import default_year, ensure_vision, set_step_value

YEAR_PARAM = "annee"


def _year(request, today):
    raw = request.GET.get(YEAR_PARAM)
    if not raw:
        return default_year(today)
    if not raw.isdigit() or not 2020 <= int(raw) <= 2100:
        raise Http404
    return int(raw)


def _goal(request, pk):
    return get_object_or_404(Goal.objects.mine(request.user), pk=pk)


@require_GET
@parent_required
def board(request):
    today = timezone.localdate()
    year = _year(request, today)
    ensure_vision(request.user, year)
    states = goal_states(Goal.objects.mine(request.user, year), today)
    return render(
        request,
        "parent/goals_board.html",
        {
            "nav_active": "home",
            "year": year,
            "states": states,
            "tagline": TAGLINE,
            "motto": MOTTO,
            "today": today,
            "started": today.year >= year,
        },
    )


@require_GET
@parent_required
def detail(request, pk):
    today = timezone.localdate()
    goal = _goal(request, pk)
    state = goal_states([goal], today)[0]
    return render(
        request,
        "parent/goals_detail.html",
        {
            "nav_active": "home",
            "state": state,
            "goal": goal,
            "today": today,
            "months": year_calendar(goal, today),
            "entries": goal.entries.all()[:20],
            "entry_form": EntryForm(savings=bool(goal.savings_target)),
            "contacts": goal.contacts.all() if goal.has_contacts else [],
            "contact_form": ContactForm(),
            "weekday_initials": ["L", "M", "M", "J", "V", "S", "D"],
        },
    )


@require_POST
@parent_required
def log_step(request, pk):
    """Valeur du jour d'un petit pas : case cochée (`done`) ou nombre (`value`)."""
    step = get_object_or_404(Step.objects.mine(request.user), pk=pk)
    if step.is_counted:
        raw = request.POST.get("value", "0").strip() or "0"
        if not raw.isdigit():
            raise Http404
        value = min(int(raw), 999)
    else:
        value = step.daily_target if request.POST.get("done") == "on" else 0
    set_step_value(step, timezone.localdate(), value)
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(status=204)
    if request.POST.get("suivant") == "objectif":
        return redirect("goals:detail", step.goal_id)
    return redirect("goals:board")


@require_POST
@parent_required
def add_entry(request, pk):
    goal = _goal(request, pk)
    form = EntryForm(request.POST, savings=bool(goal.savings_target))
    if form.is_valid():
        entry = form.save(commit=False)
        entry.goal, entry.date = goal, timezone.localdate()
        entry.save()
    return redirect("goals:detail", goal.pk)


@require_POST
@parent_required
def delete_entry(request, pk):
    entry = get_object_or_404(Entry.objects.filter(goal__user=request.user), pk=pk)
    entry.delete()
    return redirect("goals:detail", entry.goal_id)


@require_POST
@parent_required
def add_contact(request, pk):
    goal = _goal(request, pk)
    form = ContactForm(request.POST)
    if form.is_valid():
        contact = form.save(commit=False)
        contact.goal = goal
        contact.save()
    return redirect("goals:detail", goal.pk)


@require_POST
@parent_required
def contact_done(request, pk):
    """« J'ai pris des nouvelles » : date du jour, et le 1er petit pas de l'objectif coché."""
    contact = get_object_or_404(Contact.objects.filter(goal__user=request.user), pk=pk)
    today = timezone.localdate()
    contact.last_contact = today
    contact.save(update_fields=["last_contact"])
    first = contact.goal.steps.first()
    if first and not first.is_counted:
        set_step_value(first, today, first.daily_target)
    return redirect("goals:detail", contact.goal_id)


@require_POST
@parent_required
def delete_contact(request, pk):
    contact = get_object_or_404(Contact.objects.filter(goal__user=request.user), pk=pk)
    contact.delete()
    return redirect("goals:detail", contact.goal_id)


@require_http_methods(["GET", "POST"])
@parent_required
def edit(request, pk):
    """Modifier l'objectif et ses petits pas (ajout, modification, suppression)."""
    goal = _goal(request, pk)
    form = GoalForm(request.POST or None, instance=goal, prefix="goal")
    step_form = StepForm(prefix="new")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "goal" and form.is_valid():
            form.save()
            return redirect("goals:edit", goal.pk)
        if action == "add_step":
            step_form = StepForm(request.POST, prefix="new")
            if step_form.is_valid():
                step = step_form.save(commit=False)
                step.goal, step.position = goal, goal.steps.count()
                step.save()
                return redirect("goals:edit", goal.pk)
        if action == "delete_step":
            get_object_or_404(goal.steps, pk=request.POST.get("pk")).delete()
            return redirect("goals:edit", goal.pk)
        if action == "update_step":
            step = get_object_or_404(goal.steps, pk=request.POST.get("pk"))
            update = StepForm(request.POST, instance=step, prefix=f"s{step.pk}")
            if update.is_valid():
                update.save()
            return redirect("goals:edit", goal.pk)
    return render(
        request,
        "parent/goals_edit.html",
        {
            "nav_active": "home",
            "goal": goal,
            "form": form,
            "step_form": step_form,
            "steps": [(s, StepForm(instance=s, prefix=f"s{s.pk}")) for s in goal.steps.all()],
        },
        status=400
        if form.is_bound and form.errors or step_form.is_bound and step_form.errors
        else 200,
    )


def today_steps_for(user, today: datetime.date):
    """Petits pas à proposer aujourd'hui sur l'accueil (année par défaut), ou []."""
    goals = Goal.objects.mine(user, default_year(today))
    rows = []
    for state in goal_states(goals, today):
        rows += [(state.goal, s) for s in state.steps if s.show_today]
    return rows
