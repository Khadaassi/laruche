from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.families.models import Family, Role
from apps.families.tests.factories import PASSWORD, SecureClientMixin, join, make_family, make_user


def signup_data(**overrides):
    data = {
        "first_name": "Sam",
        "email": "sam@example.test",
        "password": PASSWORD,
        "invite_code": "RUCHE2026",
        "family_name": "Les Martin",
    }
    data.update(overrides)
    return data


class SignupTests(SecureClientMixin, TestCase):
    url = reverse("accounts:signup")

    def test_new_code_creates_family_and_makes_first_member_parent(self):
        response = self.post(self.url, signup_data())
        self.assertRedirects(response, reverse("tasks:home"), fetch_redirect_response=False)
        user = User.objects.get(email="sam@example.test")
        self.assertEqual(user.membership.role, Role.PARENT)
        self.assertEqual(user.family.name, "Les Martin")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_existing_code_joins_family_as_child(self):
        family = make_family(code="RUCHE2026")
        join(family)  # un parent existe déjà
        self.post(
            self.url,
            signup_data(email="kid@example.test", family_name="", invite_code="ruche-2026"),
        )
        kid = User.objects.get(email="kid@example.test")
        self.assertEqual(kid.family, family)
        self.assertEqual(kid.membership.role, Role.CHILD)
        self.assertEqual(Family.objects.count(), 1)

    def test_unknown_code_without_family_name_is_rejected(self):
        response = self.post(self.url, signup_data(family_name=""))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ne correspond à aucune famille")
        self.assertFalse(Family.objects.exists())
        self.assertFalse(User.objects.exists())

    def test_new_family_code_must_be_long_enough(self):
        response = self.post(self.url, signup_data(invite_code="ABC"))
        self.assertContains(response, "au moins 8 caractères")
        self.assertFalse(Family.objects.exists())

    def test_email_is_unique_case_insensitive(self):
        make_user(email="sam@example.test")
        response = self.post(self.url, signup_data(email="SAM@Example.test"))
        self.assertContains(response, "Un compte existe déjà")

    def test_weak_password_rejected(self):
        response = self.post(self.url, signup_data(password="court"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())


class LoginTests(SecureClientMixin, TestCase):
    def test_login_with_email_any_case(self):
        make_user(email="sam@example.test")
        response = self.post(
            reverse("accounts:login"), {"username": "Sam@Example.TEST", "password": PASSWORD}
        )
        self.assertRedirects(response, reverse("tasks:home"), fetch_redirect_response=False)

    def test_wrong_password(self):
        make_user(email="sam@example.test")
        response = self.post(
            reverse("accounts:login"), {"username": "sam@example.test", "password": "faux"}
        )
        self.assertContains(response, "E-mail ou mot de passe incorrect")

    def test_logout_requires_post(self):
        self.client.force_login(make_user())
        self.assertEqual(self.get(reverse("accounts:logout")).status_code, 405)
        self.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_anonymous_redirected_to_login(self):
        response = self.get(reverse("tasks:home"))
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next=/", fetch_redirect_response=False
        )
