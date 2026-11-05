"""Fêtes côté parent : tout est réservé aux parents et scopé par famille.

Les enfants voient les fêtes en lecture seule sur l'écran partagé
(apps.display.views.celebrations), sans la liste de cadeaux.
"""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.families.access import parent_required

from .forms import CelebrationForm, GiftForm, RecipeForm, TodoForm
from .models import Celebration, CelebrationTodo, GiftItem, RecipeIdea

# Sous-éléments : (modèle, formulaire, clé de contexte).
ITEM_KINDS = {
    "preparatifs": (CelebrationTodo, TodoForm, "todo_form"),
    "cadeaux": (GiftItem, GiftForm, "gift_form"),
    "recettes": (RecipeIdea, RecipeForm, "recipe_form"),
}
TOGGLABLE = {"preparatifs", "cadeaux"}


def _celebration(request, pk):
    return get_object_or_404(Celebration.objects.for_family(request.family), pk=pk)


def _item(request, kind, pk):
    model = ITEM_KINDS[kind][0]
    return get_object_or_404(model.objects.for_family(request.family), pk=pk)


@require_http_methods(["GET", "POST"])
@parent_required
def index(request):
    """Liste des fêtes (à venir puis passées) et création."""
    form = CelebrationForm(request.POST or None, family=request.family)
    if request.method == "POST" and form.is_valid():
        celebration = form.save(commit=False)
        celebration.family = request.family
        celebration.save()
        return redirect("celebrations:detail", pk=celebration.pk)
    today = timezone.localdate()
    celebrations = Celebration.objects.for_family(request.family)
    return render(
        request,
        "parent/celebrations.html",
        {
            "nav_active": "celebrations",
            "form": form,
            "upcoming": celebrations.filter(date__gte=today),
            "past": celebrations.filter(date__lt=today).order_by("-date")[:10],
        },
        status=400 if form.is_bound and form.errors else 200,
    )


def _detail(request, celebration, forms=None, status=200):
    forms = forms or {}
    context = {
        "nav_active": "celebrations",
        "celebration": celebration,
        "edit_form": forms.get("edit_form")
        or CelebrationForm(instance=celebration, family=request.family),
        "todos": celebration.todos.select_related("assignee"),
        "gifts": celebration.gifts.select_related("recipient", "buyer"),
        "recipes": celebration.recipes.all(),
    }
    for _, form_class, key in ITEM_KINDS.values():
        context[key] = forms.get(key) or form_class(family=request.family)
    return render(request, "parent/celebration_detail.html", context, status=status)


@require_http_methods(["GET"])
@parent_required
def detail(request, pk):
    return _detail(request, _celebration(request, pk))


@require_POST
@parent_required
def edit(request, pk):
    celebration = _celebration(request, pk)
    form = CelebrationForm(request.POST, instance=celebration, family=request.family)
    if form.is_valid():
        form.save()
        return redirect("celebrations:detail", pk=pk)
    return _detail(request, celebration, {"edit_form": form}, status=400)


@require_http_methods(["GET", "POST"])
@parent_required
def delete(request, pk):
    """Confirmation sur une page dédiée (pas de confirm() : CSP et accessibilité)."""
    celebration = _celebration(request, pk)
    if request.method == "POST":
        celebration.delete()
        return redirect("celebrations:index")
    return render(
        request,
        "parent/celebration_delete.html",
        {"nav_active": "celebrations", "celebration": celebration},
    )


@require_POST
@parent_required
def add_item(request, pk, kind):
    celebration = _celebration(request, pk)
    model, form_class, key = ITEM_KINDS[kind]
    # La fête est fixée avant validation : clean() vérifie les personnes contre elle.
    form = form_class(request.POST, instance=model(celebration=celebration), family=request.family)
    if form.is_valid():
        form.save()
        return redirect("celebrations:detail", pk=pk)
    return _detail(request, celebration, {key: form}, status=400)


@require_POST
@parent_required
def toggle_item(request, kind, pk):
    """Coche un préparatif ou un cadeau (endpoint HTMX, état fixé, idempotent)."""
    if kind not in TOGGLABLE:
        return HttpResponse(status=404)
    item = _item(request, kind, pk)
    item.done = request.POST.get("done") == "on"
    item.save(update_fields=["done"])
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(status=204)
    return redirect("celebrations:detail", pk=item.celebration_id)


@require_POST
@parent_required
def delete_item(request, kind, pk):
    item = _item(request, kind, pk)
    celebration_id = item.celebration_id
    item.delete()
    return redirect("celebrations:detail", pk=celebration_id)
