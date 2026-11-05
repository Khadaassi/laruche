"""Mot de passe oublié : lien créé par un autre parent, usage unique, isolation."""

import re

from django.test import TestCase
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

    def test_link_lets_the_other_parent_set_a_new_password_once(self):
        link = self.link_for(self.partner)
        self.client.logout()
        path = link.split("testserver", 1)[1]
        form = self.get(path, follow=True)
        self.assertContains(form, "Choisir un nouveau mot de passe")
        done = self.post(
            form.redirect_chain[-1][0],
            {"new_password1": "Abeilles-dorees-2027", "new_password2": "Abeilles-dorees-2027"},
        )
        self.assertRedirects(done, reverse("accounts:password_reset_done"))
        self.partner.refresh_from_db()
        self.assertTrue(self.partner.check_password("Abeilles-dorees-2027"))
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
        self.assertRedirects(response, reverse("families:settings"))
        self.me.refresh_from_db()
        self.assertTrue(self.me.check_password("Nouveau-mot-de-passe-2"))

    def test_login_page_explains_what_to_do(self):
        self.client.logout()
        self.assertContains(self.get(reverse("accounts:login")), "Mot de passe oublié ?")
