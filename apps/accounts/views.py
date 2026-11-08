import logging

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, PasswordChangeView, PasswordResetConfirmView
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from apps.core.ratelimit import BLOCKED_MESSAGE, FORGOT_PASSWORD, JOIN_FAMILY, LOGIN
from apps.families.services import create_family, join_family

from .forms import (
    MODE_CREATE,
    MODE_JOIN,
    LoginForm,
    ParentPasswordResetForm,
    SignupForm,
    StyledPasswordChangeForm,
    StyledSetPasswordForm,
    resolve_login,
)
from .models import User

TOO_MANY_REQUESTS = 429

logger = logging.getLogger(__name__)


class EmailLoginView(LoginView):
    """Connexion par identifiant ou e-mail, limitée en cas d'échecs répétés.

    Limites par IP et par compte visé : l'identifiant et l'e-mail d'un même
    compte comptent ensemble (`resolve_login`).
    """

    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        target = resolve_login(request.POST.get("username", ""))
        if LOGIN.is_blocked(request, target=target):
            # Formulaire vierge : le mot de passe n'est même pas vérifié.
            context = self.get_context_data(form=self.form_class(request))
            context["blocked"] = BLOCKED_MESSAGE
            return self.render_to_response(context, status=TOO_MANY_REQUESTS)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        LOGIN.record_failure(
            self.request, target=resolve_login(self.request.POST.get("username", ""))
        )
        return super().form_invalid(form)


@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("tasks:home")
    form = SignupForm(request.POST or None)
    if request.method == "POST":
        # Seules les tentatives de code (rejoindre) sont limitées : c'est là
        # qu'on pourrait deviner le code d'une famille.
        if request.POST.get("mode") == MODE_JOIN and JOIN_FAMILY.is_blocked(request):
            return render(
                request,
                "accounts/signup.html",
                {"form": form, "blocked": BLOCKED_MESSAGE},
                status=TOO_MANY_REQUESTS,
            )
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data["email"],
                    email=data["email"],
                    password=data["password"],
                    first_name=data["first_name"].strip(),
                )
                if data["mode"] == MODE_CREATE:
                    create_family(user=user, name=data["family_name"])
                elif join_family(user=user, invite_code=data["invite_code"]) is None:
                    # Code supprimé ou régénéré entre la validation et ici.
                    transaction.set_rollback(True)
                    form.add_error("invite_code", "Ce code ne correspond à aucune famille.")
                    return render(request, "accounts/signup.html", {"form": form})
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("tasks:home")
        if form.invalid_code:
            JOIN_FAMILY.record_failure(request)
    return render(request, "accounts/signup.html", {"form": form})


# --- Mot de passe ------------------------------------------------------------
# Pas d'e-mail : un parent génère, depuis ses réglages, un lien à usage unique pour un
# autre membre (families.views.reset_link). Le lien expire (PASSWORD_RESET_TIMEOUT) et
# devient invalide dès que le mot de passe change (jeton Django standard).


class ResetPasswordView(PasswordResetConfirmView):
    template_name = "accounts/password_reset.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_done")


class ResetPasswordDoneView(TemplateView):
    template_name = "accounts/password_reset_done.html"


class ChangePasswordView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("families:settings")


@require_http_methods(["GET", "POST"])
def forgot_password(request):
    """« Mot de passe oublié » d'un parent : lien de réinitialisation par e-mail.

    Même réponse que l'adresse corresponde à un compte parent ou non. Chaque demande
    compte dans la limite (elle peut envoyer un e-mail). Sans service d'e-mail
    configuré, la page le dit (aucune promesse d'envoi).
    """
    if request.user.is_authenticated:
        return redirect("accounts:password_change")
    form = ParentPasswordResetForm(request.POST or None)
    context = {"form": form, "email_enabled": settings.EMAIL_ENABLED}
    if request.method == "POST" and settings.EMAIL_ENABLED:
        target = request.POST.get("email", "")
        if FORGOT_PASSWORD.is_blocked(request, target=target):
            context["blocked"] = BLOCKED_MESSAGE
            return render(request, "accounts/forgot_password.html", context, status=429)
        FORGOT_PASSWORD.record_failure(request, target=target)
        if form.is_valid():
            try:
                form.save(
                    request=request,
                    use_https=request.is_secure(),
                    subject_template_name="accounts/emails/reset_subject.txt",
                    email_template_name="accounts/emails/reset_body.txt",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                )
            except Exception:  # noqa: BLE001 (service tiers : on n'expose rien)
                logger.exception("E-mail de réinitialisation non envoyé")
            return render(
                request, "accounts/forgot_password_sent.html", {"email": form.cleaned_data["email"]}
            )
    status = 400 if form.is_bound and form.errors else 200
    return render(request, "accounts/forgot_password.html", context, status=status)
