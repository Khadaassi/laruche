from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.core.ratelimit import BLOCKED_MESSAGE, JOIN_FAMILY, LOGIN
from apps.families.services import create_family, join_family

from .forms import MODE_CREATE, MODE_JOIN, LoginForm, SignupForm, resolve_login
from .models import User

TOO_MANY_REQUESTS = 429


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
