"""Liste de courses : réservée aux parents, scopée par famille.

Les enfants n'y ont pas accès, ni sur l'écran partagé ni avec un compte.
"""

import datetime

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.families.access import parent_required
from apps.household.models import monday_of
from apps.household.views import WEEK_PARAM, requested_monday

from .forms import ShoppingItemForm
from .models import Origin, ShoppingItem, ShoppingTransfer, Status
from .transfer import DECISIONS, MissingDecision, apply_transfer, build_plan, clear_bought

CHOICE_PREFIX = "choice_"


def _item(request, pk):
    return get_object_or_404(ShoppingItem.objects.for_family(request.family), pk=pk)


def _last_transfer(family):
    return ShoppingTransfer.objects.filter(family=family).first()


def transfer_week(request):
    """Semaine à transférer : celle demandée, sinon celle du dernier envoi si elle
    n'est pas passée, sinon la semaine en cours."""
    if request.GET.get(WEEK_PARAM):
        return requested_monday(request)
    current = monday_of(timezone.localdate())
    last = _last_transfer(request.family)
    return last.week if last and last.week >= current else current


def _sorted(items):
    """À acheter d'abord, puis achetés ; ordre alphabétique dans chaque groupe."""
    return sorted(items, key=lambda i: (i.status != Status.TO_BUY, i.name.casefold()))


@require_http_methods(["GET", "POST"])
@parent_required
def index(request):
    """Liste de courses : articles du menu, produits ajoutés à la main, ajout."""
    form = ShoppingItemForm(request.POST or None, family=request.family)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("shopping:index")

    items = list(ShoppingItem.objects.for_family(request.family))
    active = [i for i in items if i.status != Status.AT_HOME]
    last = _last_transfer(request.family)
    week = transfer_week(request)
    # Le menu a-t-il changé depuis le dernier envoi (semaine pas encore passée) ?
    menu_changed = bool(last and last.week == week and build_plan(request.family, week).has_changes)
    return render(
        request,
        "parent/shopping.html",
        {
            "nav_active": "kitchen",
            "kitchen_tab": "shopping",
            "form": form,
            "menu_items": _sorted(i for i in active if i.origin == Origin.MENU),
            "manual_items": _sorted(i for i in active if i.origin == Origin.MANUAL),
            "at_home_items": [i for i in items if i.status == Status.AT_HOME],
            "to_buy_count": sum(i.status == Status.TO_BUY for i in items),
            "bought_count": sum(i.status == Status.BOUGHT for i in items),
            "last_transfer": last,
            "transfer_week": week,
            "menu_changed": menu_changed,
        },
        status=400 if form.is_bound and form.errors else 200,
    )


@require_http_methods(["GET", "POST"])
@parent_required
def transfer(request):
    """Aperçu du transfert menu → courses, puis application.

    Rien n'est écrit sans confirmation. Chaque article déjà coché (ou « à la
    maison ») dont la quantité change demande un choix explicite.
    """
    week = transfer_week(request)
    missing = set()
    if request.method == "POST":
        decisions = {
            int(key.removeprefix(CHOICE_PREFIX)): value
            for key, value in request.POST.items()
            if key.startswith(CHOICE_PREFIX) and key.removeprefix(CHOICE_PREFIX).isdigit()
        }
        try:
            apply_transfer(request.family, week, decisions)
        except MissingDecision:
            # Conflits sans choix valide (ou apparus depuis l'aperçu) : on redemande.
            missing = {
                item.pk
                for item, _ in build_plan(request.family, week).conflicts
                if decisions.get(item.pk) not in DECISIONS
            }
        else:
            return redirect("shopping:index")
    plan = build_plan(request.family, week)
    return render(
        request,
        "parent/shopping_transfer.html",
        {
            "nav_active": "kitchen",
            "plan": plan,
            "missing": missing,
            "monday": week,
            **_week_nav(week),
        },
        status=400 if missing else 200,
    )


def _week_nav(monday):
    today = timezone.localdate()
    return {
        "sunday": monday + datetime.timedelta(days=6),
        "previous_monday": monday - datetime.timedelta(days=7),
        "next_monday": monday + datetime.timedelta(days=7),
        "is_current_week": monday <= today < monday + datetime.timedelta(days=7),
    }


@require_POST
@parent_required
def toggle(request, pk):
    """Coche (acheté) / décoche un article (endpoint HTMX, état fixé, idempotent)."""
    item = _item(request, pk)
    item.status = Status.BOUGHT if request.POST.get("done") == "on" else Status.TO_BUY
    item.save(update_fields=["status"])
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(status=204)
    return redirect("shopping:index")


@require_POST
@parent_required
def at_home(request, pk):
    """« Déjà à la maison » : hors de la liste active, sans toucher au menu."""
    item = _item(request, pk)
    item.status = Status.AT_HOME
    item.save(update_fields=["status"])
    return redirect("shopping:index")


@require_POST
@parent_required
def restore(request, pk):
    item = _item(request, pk)
    item.status = Status.TO_BUY
    item.save(update_fields=["status"])
    return redirect("shopping:index")


@require_http_methods(["GET", "POST"])
@parent_required
def edit(request, pk):
    item = _item(request, pk)
    form = ShoppingItemForm(request.POST or None, instance=item, family=request.family)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("shopping:index")
    return render(
        request,
        "parent/shopping_item_edit.html",
        {"nav_active": "kitchen", "form": form, "item": item},
        status=400 if form.is_bound and form.errors else 200,
    )


@require_POST
@parent_required
def delete(request, pk):
    _item(request, pk).delete()
    return redirect("shopping:index")


@require_POST
@parent_required
def clear(request):
    """Retire les articles achetés (les produits habituels repassent « à acheter »)."""
    clear_bought(request.family)
    return redirect("shopping:index")
