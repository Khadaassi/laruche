from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from apps.families.models import INVITE_CODE_MIN_LENGTH, Family, normalize_invite_code

from .models import User

FIELD_CLASSES = (
    "block w-full rounded-md border border-border-strong bg-surface-0 px-space-4 py-3 text-ink"
)


class StyledFormMixin:
    """Applique la recette « champ » de la charte à tous les widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
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
    invite_code = forms.CharField(
        label="Code famille",
        max_length=32,
        widget=forms.TextInput(attrs={"autocomplete": "off", "autocapitalize": "characters"}),
        help_text="Le code donné par un parent pour rejoindre sa famille, "
        "ou un nouveau code pour créer la vôtre.",
    )
    family_name = forms.CharField(
        label="Nom de la famille",
        max_length=80,
        required=False,
        help_text="Seulement si vous créez une nouvelle famille.",
    )

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
        code = cleaned.get("invite_code")
        if code and not Family.objects.filter(invite_code=code).exists():
            # Code inconnu = création. On exige un nom (une faute de frappe dans
            # un code existant ne crée donc pas une famille par erreur) et un
            # code assez long pour ne pas être deviné.
            if not cleaned.get("family_name", "").strip():
                self.add_error(
                    "family_name",
                    "Ce code ne correspond à aucune famille. Vérifiez-le, "
                    "ou donnez un nom pour créer une nouvelle famille.",
                )
            if len(code) < INVITE_CODE_MIN_LENGTH:
                self.add_error(
                    "invite_code",
                    f"Pour créer une famille, choisissez un code d'au moins "
                    f"{INVITE_CODE_MIN_LENGTH} caractères.",
                )
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

    @property
    def creates_family(self) -> bool:
        code = self.cleaned_data.get("invite_code")
        return bool(code) and not Family.objects.filter(invite_code=code).exists()
