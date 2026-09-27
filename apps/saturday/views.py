"""Roue du samedi côté parent. Tout est réservé aux parents (permissions/SKILL.md) :
c'est un moment parent-enfant, le parent lance et tout le monde regarde. Le
résultat validé est visible par tous (accueil, écran partagé)."""

import secrets

from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.families.access import parent_required
from apps.stars.selectors import balances

from .draw import (
    MAX_SPINS,
    DrawError,
    accept,
    cancel,
    close_past_plans,
    current_plan,
    draw,
    eligible_activities,
    mark_done,
    target_saturday,
)
from .forms import ActivityForm, DrawFiltersForm
from .models import PlanStatus, SaturdayActivity, SaturdayPlan, season_of
from .wheel import build_wheel

# Refus métier (plus de relance, rien d'éligible…) : affiché dans la zone du tirage.
REFUSED = 422


def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _page_context(request, **extra):
    today = timezone.localdate()
    close_past_plans(request.family, today)
    plan = current_plan(request.family, today)
    stars = balances(request.family)
    return {
        "nav_active": "home",
        "saturday": target_saturday(today),
        "saturday_label": date_format(target_saturday(today), "j F"),
        "plan": plan,
        "spins_left": MAX_SPINS - (plan.spins if plan else 0),
        "filters": extra.pop("filters", None) or DrawFiltersForm(),
        "stars": list(stars.values()),
        "pot": sum(max(b.balance, 0) for b in stars.values()),
        "history": SaturdayPlan.objects.for_family(request.family)
        .filter(status=PlanStatus.DONE)
        .select_related("star_spend")[:8],
        **extra,
    }


@require_GET
@parent_required
def page(request):
    """Préparer le samedi : filtres, roue, plan validé, historique."""
    return render(request, "parent/saturday.html", _page_context(request))


@require_POST
@parent_required
def spin(request):
    """Un tour de roue (premier tirage ou relance), limité côté serveur."""
    filters = DrawFiltersForm(request.POST)
    template = "parent/_saturday_draw.html" if _is_htmx(request) else "parent/saturday.html"
    if not filters.is_valid():
        return render(request, template, _page_context(request, filters=filters), status=400)
    try:
        plan = draw(
            request.family,
            request.user,
            timezone.localdate(),
            filters.cleaned_data["cost"],
            filters.cleaned_data["place"],
        )
    except DrawError as error:
        context = _page_context(request, filters=filters, draw_error=str(error))
        return render(request, template, context, status=REFUSED)
    context = _page_context(request, filters=filters, just_spun=True)
    candidates = eligible_activities(
        request.family,
        plan.date,
        filters.cleaned_data["cost"],
        filters.cleaned_data["place"],
        context["pot"],
    ) or [plan.activity]
    decor = SaturdayActivity.objects.for_family(request.family).in_season(season_of(plan.date))
    context["wheel"] = build_wheel(
        candidates, plan.activity, secrets.SystemRandom(), decor=list(decor)
    )
    return render(request, template, context)


@require_POST
@parent_required
def validate(request, pk):
    """« On y va ! » : le plan est validé, les étoiles éventuelles sont payées."""
    plan = get_object_or_404(SaturdayPlan.objects.for_family(request.family), pk=pk)
    try:
        accept(plan)
    except DrawError as error:
        return render(
            request,
            "parent/saturday.html",
            _page_context(request, draw_error=str(error)),
            status=REFUSED,
        )
    return redirect("saturday:page")


@require_POST
@parent_required
def done(request, pk):
    plan = get_object_or_404(SaturdayPlan.objects.for_family(request.family), pk=pk)
    mark_done(plan, timezone.localdate())
    return redirect("saturday:page")


@require_POST
@parent_required
def cancel_plan(request, pk):
    plan = get_object_or_404(SaturdayPlan.objects.for_family(request.family), pk=pk)
    try:
        cancel(plan)
    except DrawError as error:
        return render(
            request,
            "parent/saturday.html",
            _page_context(request, draw_error=str(error)),
            status=REFUSED,
        )
    return redirect("saturday:page")


# --- Catalogue (Réglages → Activités du samedi) -------------------------------


@require_http_methods(["GET", "POST"])
@parent_required
def catalog(request):
    form = ActivityForm(request.POST or None, family=request.family)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("saturday:catalog")
    return render(
        request,
        "parent/activities_manage.html",
        {
            "nav_active": "settings",
            "form": form,
            "activities": SaturdayActivity.objects.for_family(request.family),
        },
        status=400 if form.is_bound and form.errors else 200,
    )


@require_http_methods(["GET", "POST"])
@parent_required
def edit_activity(request, pk):
    activity = get_object_or_404(SaturdayActivity.objects.for_family(request.family), pk=pk)
    form = ActivityForm(request.POST or None, instance=activity, family=request.family)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("saturday:catalog")
    return render(
        request,
        "parent/activity_edit.html",
        {"nav_active": "settings", "form": form, "activity": activity},
        status=400 if form.is_bound and form.errors else 200,
    )


@require_http_methods(["GET", "POST"])
@parent_required
def delete_activity(request, pk):
    activity = get_object_or_404(SaturdayActivity.objects.for_family(request.family), pk=pk)
    if request.method == "POST":
        activity.delete()
        return redirect("saturday:catalog")
    return render(
        request, "parent/activity_delete.html", {"nav_active": "settings", "activity": activity}
    )
