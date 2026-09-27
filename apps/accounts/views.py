from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.families.services import join_or_create_family

from .forms import LoginForm, SignupForm
from .models import User


class EmailLoginView(LoginView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True


@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("tasks:home")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            user = User.objects.create_user(
                username=data["email"],
                email=data["email"],
                password=data["password"],
                first_name=data["first_name"].strip(),
            )
            join_or_create_family(
                user=user,
                invite_code=data["invite_code"],
                family_name=data["family_name"].strip(),
            )
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("tasks:home")
    return render(request, "accounts/signup.html", {"form": form})
