from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from apps.families.models import Family, normalize_invite_code

from .models import User

FIELD_CLASSES = (
    "block w-full rounded-md border border-border-strong bg-surface-0 px-space-4 py-3 text-ink"
)


class StyledFormMixin:
    """Applique la recette « champ » de la charte à tous les widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs.setdefault("class", FIELD_CLASSES)


def normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


class LoginForm(StyledFormMixin, AuthenticationForm):
    """Connexion par e-mail : l'identifiant stocké est l'e-mail en minuscules."""

    username = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}),
    )

    error_messages = {
        "invalid_login": "E-mail ou mot de passe incorrect.",
        "inactive": "Ce compte est désactivé.",
    }

    def clean_username(self):
        return normalize_email(self.cleaned_data["username"])


MODE_CREATE = "create"
MODE_JOIN = "join"


class SignupForm(StyledFormMixin, forms.Form):
    first_name = forms.CharField(
        label="Prénom", max_length=40, widget=forms.TextInput(attrs={"autocomplete": "given-name"})
    )
    email = forms.EmailField(
        label="Adresse e-mail", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="12 caractères minimum.",
    )
    mode = forms.ChoiceField(
        label="Votre famille",
        choices=[
            (MODE_CREATE, "Créer une nouvelle famille"),
            (MODE_JOIN, "Rejoindre une famille existante"),
        ],
        initial=MODE_CREATE,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )
    family_name = forms.CharField(
        label="Nom de la famille",
        max_length=80,
        required=False,
        help_text="Pour une nouvelle famille. Son code d'invitation sera créé "
        "automatiquement et visible dans vos réglages.",
    )
    invite_code = forms.CharField(
        label="Code famille",
        max_length=32,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "autocapitalize": "characters"}),
        help_text="Pour rejoindre une famille : le code donné par un parent.",
    )

    # Vrai si le formulaire a été refusé pour un code inconnu (compté par le rate-limit).
    invalid_code = False

    def clean_email(self):
        email = normalize_email(self.cleaned_data["email"])
        if (
            User.objects.filter(username=email).exists()
            or User.objects.filter(email__iexact=email).exists()
        ):
            raise forms.ValidationError("Un compte existe déjà avec cette adresse.")
        return email

    def clean_invite_code(self):
        return normalize_invite_code(self.cleaned_data["invite_code"])

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        if mode == MODE_CREATE:
            cleaned["family_name"] = cleaned.get("family_name", "").strip()
            if not cleaned["family_name"]:
                self.add_error("family_name", "Donnez un nom à votre famille.")
        elif mode == MODE_JOIN:
            code = cleaned.get("invite_code", "")
            if not code:
                self.add_error("invite_code", "Saisissez le code donné par un parent.")
            elif not Family.objects.filter(invite_code=code).exists():
                self.invalid_code = True
                self.add_error("invite_code", "Ce code ne correspond à aucune famille.")
        password = cleaned.get("password")
        if password:
            candidate = User(
                username=cleaned.get("email", ""),
                email=cleaned.get("email", ""),
                first_name=cleaned.get("first_name", ""),
            )
            try:
                password_validation.validate_password(password, candidate)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return cleaned
