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
        "mode": "create",
        "family_name": "Les Martin",
        "invite_code": "",
    }
    data.update(overrides)
    return data


class SignupTests(SecureClientMixin, TestCase):
    url = reverse("accounts:signup")

    def test_create_family_generates_code_and_makes_creator_parent(self):
        response = self.post(self.url, signup_data(invite_code="MONCODE123"))
        self.assertRedirects(response, reverse("tasks:home"), fetch_redirect_response=False)
        user = User.objects.get(email="sam@example.test")
        self.assertEqual(user.membership.role, Role.PARENT)
        self.assertEqual(user.family.name, "Les Martin")
        # Le code saisi est ignoré : il est toujours généré.
        self.assertNotEqual(user.family.invite_code, "MONCODE123")
        self.assertEqual(len(user.family.invite_code), 10)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_create_requires_family_name(self):
        response = self.post(self.url, signup_data(family_name=" "))
        self.assertContains(response, "Donnez un nom à votre famille")
        self.assertFalse(Family.objects.exists())

    def test_join_with_code_enters_as_child(self):
        family = make_family(code="RUCHE2026")
        join(family)  # un parent existe déjà
        self.post(
            self.url,
            signup_data(email="kid@example.test", mode="join", invite_code="ruche-2026"),
        )
        kid = User.objects.get(email="kid@example.test")
        self.assertEqual(kid.family, family)
        self.assertEqual(kid.membership.role, Role.CHILD)
        self.assertEqual(Family.objects.count(), 1)

    def test_join_with_unknown_code_creates_nothing(self):
        response = self.post(self.url, signup_data(mode="join", invite_code="INCONNU99"))
        self.assertContains(response, "ne correspond à aucune famille")
        self.assertFalse(Family.objects.exists())
        self.assertFalse(User.objects.exists())

    def test_join_requires_code(self):
        response = self.post(self.url, signup_data(mode="join", invite_code=""))
        self.assertContains(response, "Saisissez le code")

    def test_email_is_unique_case_insensitive(self):
        make_user(email="sam@example.test")
        response = self.post(self.url, signup_data(email="SAM@Example.test"))
        self.assertContains(response, "Un compte existe déjà")

    def test_weak_password_rejected(self):
        response = self.post(self.url, signup_data(password="court"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())


class SignupRateLimitTests(SecureClientMixin, TestCase):
    url = reverse("accounts:signup")

    def attempt(self, n, **overrides):
        data = signup_data(mode="join", invite_code=f"FAUX{n:05d}", email=f"u{n}@example.test")
        data.update(overrides)
        return self.post(self.url, data)

    def test_invalid_codes_are_limited_per_ip(self):
        for n in range(10):
            self.assertEqual(self.attempt(n).status_code, 200)
        blocked = self.attempt(99)
        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, "Trop de tentatives", status_code=429)

    def test_block_applies_even_with_the_right_code(self):
        family = make_family(code="RUCHE2026")
        for n in range(10):
            self.attempt(n)
        self.assertEqual(self.attempt(50, invite_code="RUCHE2026").status_code, 429)
        self.assertFalse(family.memberships.exists())

    def test_changing_ip_does_not_bypass_global_limit(self):
        for n in range(100):
            self.attempt(n, REMOTE_ADDR=f"10.0.{n // 250}.{n % 250}")
        self.assertEqual(self.attempt(200, REMOTE_ADDR="192.0.2.1").status_code, 429)

    def test_creating_a_family_is_not_limited(self):
        for n in range(10):
            self.attempt(n)
        response = self.post(self.url, signup_data(email="new@example.test"))
        self.assertEqual(response.status_code, 302)

    def test_valid_join_does_not_count(self):
        family = make_family(code="RUCHE2026")
        for n in range(12):
            response = self.attempt(n, invite_code="RUCHE2026")
            self.assertEqual(response.status_code, 302)
            self.client.logout()
        self.assertEqual(family.memberships.count(), 12)


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
        self.assertContains(response, "Identifiant, e-mail ou mot de passe incorrect")

    def test_logout_requires_post(self):
        self.client.force_login(make_user())
        self.assertEqual(self.get(reverse("accounts:logout")).status_code, 405)
        self.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_repeated_failures_block_login_for_that_account(self):
        make_user(email="sam@example.test")
        url = reverse("accounts:login")
        for _ in range(10):
            self.post(url, {"username": "sam@example.test", "password": "faux"})
        # Même avec le bon mot de passe et depuis une autre IP : bloqué.
        response = self.post(
            url, {"username": "SAM@example.test", "password": PASSWORD}, REMOTE_ADDR="192.0.2.9"
        )
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Trop de tentatives", status_code=429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_failures_are_limited_per_ip_across_accounts(self):
        url = reverse("accounts:login")
        for n in range(20):
            self.post(url, {"username": f"x{n}@example.test", "password": "faux"})
        make_user(email="sam@example.test")
        response = self.post(url, {"username": "sam@example.test", "password": PASSWORD})
        self.assertEqual(response.status_code, 429)

    def test_successful_logins_do_not_count(self):
        make_user(email="sam@example.test")
        url = reverse("accounts:login")
        for _ in range(15):
            response = self.post(url, {"username": "sam@example.test", "password": PASSWORD})
            self.assertEqual(response.status_code, 302)
            self.client.logout()

    def test_anonymous_redirected_to_login(self):
        response = self.get(reverse("tasks:home"))
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next=/", fetch_redirect_response=False
        )
