from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.forms import FIELD_CLASSES
from apps.display.forms import DeviceForm
from apps.display.models import SharedDisplayDevice

from .access import family_member_required, parent_required
from .models import Person, Role, next_avatar_color
from .services import promote_to_parent, regenerate_invite_code


class ChildProfileForm(forms.Form):
    name = forms.CharField(
        label="Prénom", max_length=40, widget=forms.TextInput(attrs={"class": FIELD_CLASSES})
    )


@require_GET
@family_member_required
def settings_page(request):
    """Réglages. Un enfant n'y voit que son compte (déconnexion)."""
    context = {"nav_active": "settings"}
    if request.membership.is_parent:
        context.update(
            people=Person.objects.for_family(request.family).select_related("user__membership"),
            child_form=ChildProfileForm(),
            device_form=DeviceForm(),
            devices=SharedDisplayDevice.objects.for_family(request.family).active(),
        )
    return render(request, "parent/settings.html", context)


@require_POST
@parent_required
def add_child(request):
    """Ajoute un enfant sans compte (affiché dans l'app, sans connexion)."""
    form = ChildProfileForm(request.POST)
    if form.is_valid():
        Person.objects.create(
            family=request.family,
            name=form.cleaned_data["name"].strip(),
            role=Role.CHILD,
            avatar_color=next_avatar_color(request.family),
        )
    return redirect("families:settings")


@require_POST
@parent_required
def promote(request, pk):
    person = get_object_or_404(
        Person.objects.for_family(request.family).filter(
            user__isnull=False, user__membership__role=Role.CHILD
        ),
        pk=pk,
    )
    promote_to_parent(person.user.membership)
    return redirect("families:settings")


@require_POST
@parent_required
def regenerate_code(request):
    regenerate_invite_code(request.family)
    return redirect("families:settings")
