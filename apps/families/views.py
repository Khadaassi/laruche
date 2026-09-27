from django import forms
from django.contrib.auth import password_validation
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.forms import FIELD_CLASSES
from apps.accounts.models import User, normalize_login_name, validate_login_name
from apps.display.forms import DeviceForm
from apps.display.models import SharedDisplayDevice

from .access import parent_required
from .models import FamilyMembership, Person, Role, next_avatar_color
from .services import (
    LoginNameTaken,
    create_display_account,
    display_account,
    promote_to_parent,
    regenerate_invite_code,
    set_login_name,
)


class ChildProfileForm(forms.Form):
    name = forms.CharField(
        label="Prénom", max_length=40, widget=forms.TextInput(attrs={"class": FIELD_CLASSES})
    )


def login_name_field(required: bool) -> forms.CharField:
    return forms.CharField(
        label="Identifiant",
        max_length=30,
        required=required,
        widget=forms.TextInput(
            attrs={"class": FIELD_CLASSES, "autocapitalize": "none", "spellcheck": "false"}
        ),
        help_text="Lettres sans accent, chiffres, point ou tiret (ex. : khadija, enfants).",
    )


class LoginNameForm(forms.Form):
    login_name = login_name_field(required=False)

    def clean_login_name(self):
        value = normalize_login_name(self.cleaned_data["login_name"])
        if value:
            validate_login_name(value)
        return value


class DisplayAccountForm(forms.Form):
    login_name = login_name_field(required=True)
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": FIELD_CLASSES, "autocomplete": "new-password"}),
        help_text="12 caractères minimum.",
    )

    def clean_login_name(self):
        value = normalize_login_name(self.cleaned_data["login_name"])
        validate_login_name(value)
        if User.objects.filter(login_name=value).exists():
            raise forms.ValidationError("Cet identifiant est déjà pris.")
        return value

    def clean_password(self):
        password = self.cleaned_data["password"]
        password_validation.validate_password(password, User(first_name="Écran partagé"))
        return password


def family_accounts(family):
    """Comptes de la famille (parents, enfants, écran partagé), avec leur personne."""
    return (
        FamilyMembership.objects.filter(family=family)
        .select_related("user__person")
        .order_by("joined_at")
    )


def render_settings(request, *, display_form=None, login_forms=None, status=200):
    login_forms = login_forms or {}
    accounts = []
    for membership in family_accounts(request.family):
        form = login_forms.get(membership.user_id) or LoginNameForm(
            initial={"login_name": membership.user.login_name or ""},
            prefix=f"account-{membership.user_id}",
        )
        accounts.append((membership, form))
    context = {
        "nav_active": "settings",
        "people": Person.objects.for_family(request.family).select_related("user__membership"),
        "accounts": accounts,
        "display_account": display_account(request.family),
        "display_form": display_form or DisplayAccountForm(),
        "child_form": ChildProfileForm(),
        "device_form": DeviceForm(),
        "devices": SharedDisplayDevice.objects.for_family(request.family).active(),
    }
    return render(request, "parent/settings.html", context, status=status)


@require_GET
@parent_required
def settings_page(request):
    """Réglages (parents uniquement)."""
    return render_settings(request)


@require_POST
@parent_required
def update_login_name(request, user_pk):
    """Donne ou retire l'identifiant d'un compte de la famille (parents)."""
    user = get_object_or_404(User.objects.filter(membership__family=request.family), pk=user_pk)
    form = LoginNameForm(request.POST, prefix=f"account-{user.pk}")
    if form.is_valid():
        try:
            set_login_name(user, form.cleaned_data["login_name"])
        except LoginNameTaken:
            form.add_error("login_name", "Cet identifiant est déjà pris.")
        else:
            return redirect("families:settings")
    return render_settings(request, login_forms={user.pk: form}, status=400)


@sensitive_post_parameters("password")
@require_POST
@parent_required
def create_display(request):
    """Crée le compte « écran partagé » des enfants (un par famille)."""
    if display_account(request.family) is not None:
        return redirect("families:settings")
    form = DisplayAccountForm(request.POST)
    if form.is_valid():
        try:
            create_display_account(
                request.family,
                login_name=form.cleaned_data["login_name"],
                password=form.cleaned_data["password"],
            )
        except LoginNameTaken:
            form.add_error("login_name", "Cet identifiant est déjà pris.")
        else:
            return redirect("families:settings")
    return render_settings(request, display_form=form, status=400)


@require_POST
@parent_required
def delete_display(request):
    """Supprime le compte « écran partagé » (ses sessions ne donnent plus accès)."""
    user = display_account(request.family)
    if user is not None:
        user.delete()
    return redirect("families:settings")


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
