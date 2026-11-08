"""Mot de passe oublié : lien parental (enfants, tablette), e-mail (parents), isolation."""

import json
import re
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.families.services import promote_to_parent
from apps.families.tests.factories import SecureClientMixin, join, make_family


class ResetLinkTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.me = join(self.family, "Khadija")
        self.partner = join(self.family, "Lhousseine")
        promote_to_parent(self.partner.membership)
        self.kid = join(self.family, "Aliyah")
        self.client.force_login(self.me)

    def link_for(self, user):
        page = self.post(reverse("families:reset_link", args=[user.pk]))
        self.assertEqual(page.status_code, 200)
        return re.search(
            r'value="(https://[^"]+/mot-de-passe/[^"]+)"', page.content.decode()
        ).group(1)

    def test_no_link_for_another_parent(self):
        # Sinon un parent pourrait prendre le compte de l'autre (et ses objectifs privés).
        response = self.post(reverse("families:reset_link", args=[self.partner.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(
            self.get(reverse("families:settings")),
            reverse("families:reset_link", args=[self.partner.pk]),
        )

    def test_link_lets_a_child_set_a_new_password_once(self):
        link = self.link_for(self.kid)
        self.client.logout()
        path = link.split("testserver", 1)[1]
        form = self.get(path, follow=True)
        self.assertContains(form, "Choisir un nouveau mot de passe")
        done = self.post(
            form.redirect_chain[-1][0],
            {"new_password1": "Abeilles-dorees-2027", "new_password2": "Abeilles-dorees-2027"},
        )
        self.assertRedirects(
            done, reverse("accounts:password_reset_done"), fetch_redirect_response=False
        )
        self.kid.refresh_from_db()
        self.assertTrue(self.kid.check_password("Abeilles-dorees-2027"))
        self.assertContains(self.get(path, follow=True), "Lien expiré")  # usage unique

    def test_not_for_myself_nor_another_family(self):
        self.assertEqual(
            self.post(reverse("families:reset_link", args=[self.me.pk])).status_code, 404
        )
        other = make_family()
        stranger = join(other, "Alex")
        self.assertEqual(
            self.post(reverse("families:reset_link", args=[stranger.pk])).status_code, 404
        )

    def test_children_cannot_create_links(self):
        self.client.force_login(self.kid)
        response = self.post(reverse("families:reset_link", args=[self.me.pk]))
        self.assertNotEqual(response.status_code, 200)

    def test_bad_token_is_refused(self):
        self.client.logout()
        self.assertContains(self.get("/mot-de-passe/MQ/faux-jeton/", follow=True), "Lien expiré")

    def test_change_my_own_password(self):
        self.me.set_password("Ancien-mot-de-passe-1")
        self.me.save()
        self.client.force_login(self.me)
        response = self.post(
            reverse("accounts:password_change"),
            {
                "old_password": "Ancien-mot-de-passe-1",
                "new_password1": "Nouveau-mot-de-passe-2",
                "new_password2": "Nouveau-mot-de-passe-2",
            },
        )
        self.assertRedirects(response, reverse("families:settings"), fetch_redirect_response=False)
        self.me.refresh_from_db()
        self.assertTrue(self.me.check_password("Nouveau-mot-de-passe-2"))

    def test_login_page_explains_what_to_do(self):
        self.client.logout()
        page = self.get(reverse("accounts:login"))
        self.assertContains(page, reverse("accounts:forgot_password"))


@override_settings(
    EMAIL_ENABLED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class ForgotPasswordEmailTests(SecureClientMixin, TestCase):
    URL = reverse("accounts:forgot_password")

    def setUp(self):
        self.family = make_family()
        self.me = join(self.family, "Khadija")
        self.me.email = "khadija@example.com"
        self.me.save()
        self.kid = join(self.family, "Aliyah")
        self.kid.email = "aliyah@example.com"
        self.kid.save()

    def test_parent_receives_a_one_time_link(self):
        page = self.post(self.URL, {"email": "Khadija@Example.com"})
        self.assertContains(page, "Vérifiez vos e-mails")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["khadija@example.com"])
        link = re.search(r"https://testserver(/mot-de-passe/\S+)", mail.outbox[0].body).group(1)
        form = self.get(link, follow=True)
        done = self.post(
            form.redirect_chain[-1][0],
            {"new_password1": "Ruche-dorée-2027", "new_password2": "Ruche-dorée-2027"},
        )
        self.assertRedirects(
            done, reverse("accounts:password_reset_done"), fetch_redirect_response=False
        )
        self.me.refresh_from_db()
        self.assertTrue(self.me.check_password("Ruche-dorée-2027"))
        self.assertContains(self.get(link, follow=True), "Lien expiré")

    def test_unknown_address_and_child_account_get_the_same_answer_and_no_mail(self):
        for email in ("personne@example.com", "aliyah@example.com"):
            page = self.post(self.URL, {"email": email})
            self.assertContains(page, "Vérifiez vos e-mails")
        self.assertEqual(mail.outbox, [])

    def test_requests_are_limited(self):
        for _ in range(3):
            self.post(self.URL, {"email": "khadija@example.com"})
        page = self.post(self.URL, {"email": "khadija@example.com"})
        self.assertEqual(page.status_code, 429)
        self.assertEqual(len(mail.outbox), 3)

    @override_settings(EMAIL_ENABLED=False)
    def test_without_email_service_nothing_is_promised(self):
        page = self.post(self.URL, {"email": "khadija@example.com"})
        self.assertContains(page, "pas encore configuré")
        self.assertEqual(mail.outbox, [])


class BrevoBackendTests(TestCase):
    @override_settings(
        EMAIL_BACKEND="apps.core.email.BrevoEmailBackend",
        BREVO_API_KEY="cle-de-test",
        DEFAULT_FROM_EMAIL="La Ruche <ruche@example.com>",
    )
    def test_message_is_posted_to_the_api(self):
        response = mock.MagicMock(status=201)
        response.__enter__.return_value = response
        with mock.patch("urllib.request.urlopen", return_value=response) as urlopen:
            sent = mail.send_mail("Sujet", "Corps", None, ["a@example.com"])
        self.assertEqual(sent, 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(request.get_header("Api-key"), "cle-de-test")
        payload = json.loads(request.data)
        self.assertEqual(payload["sender"], {"email": "ruche@example.com", "name": "La Ruche"})
        self.assertEqual(payload["to"], [{"email": "a@example.com"}])
        self.assertEqual(payload["textContent"], "Corps")
