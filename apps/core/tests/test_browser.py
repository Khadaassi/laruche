"""Parcours réels dans Chromium (Playwright) : JavaScript, HTMX, Alpine, cookies.

Lancés à part (`manage.py test --tag browser`, job CI « Browser tests ») : ils ont besoin
de Chromium et des fichiers statiques construits (`npm run build`). En local :
`PLAYWRIGHT_CHROMIUM_EXECUTABLE=/chemin/vers/chrome` pour utiliser un Chrome installé.

Cinq parcours (revue externe) : connexion, activation de la tablette, cochage, transfert
du menu vers les courses, coupure réseau pendant un cochage.
"""

import datetime
import os
from decimal import Decimal

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings, tag

from apps.families.tests.factories import join, make_family
from apps.meals.models import Meal, MealKind, MealSlot, Recipe, RecipeIngredient
from apps.shopping.models import ShoppingItem
from apps.tasks.models import Task, TaskCompletion
from apps.tasks.periods import Period

PASSWORD = "Ruche-test-2027!"
PHONE = {"width": 390, "height": 844}
TABLET = {"width": 1180, "height": 820}


@tag("browser")
@override_settings(
    # Serveur de test en HTTP sur localhost : pas de redirection HTTPS, fichiers
    # statiques servis tels quels (pas de manifeste collectstatic).
    SECURE_SSL_REDIRECT=False,
    SECURE_HSTS_SECONDS=0,
    ALLOWED_HOSTS=["localhost", "127.0.0.1"],
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class BrowserJourneyTests(StaticLiveServerTestCase):
    host = "localhost"  # cookies « Secure » acceptés par Chromium sur localhost

    @classmethod
    def setUpClass(cls):
        # Playwright (API synchrone) fait tourner une boucle asyncio dans ce fil :
        # sans ceci, Django refuse les requêtes ORM des tests.
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        from playwright.sync_api import sync_playwright

        cls.playwright = sync_playwright().start()
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or None
        cls.browser = cls.playwright.chromium.launch(executable_path=executable)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Khadija")
        self.parent.set_password(PASSWORD)
        self.parent.save()
        self.kid = join(self.family, "Aliyah")
        self.tasks = [
            Task.objects.create(person=self.kid.person, title=f"Ranger ({p.label})", period=p)
            for p in Period
        ]
        self.context = self.browser.new_context(viewport=PHONE, base_url=self.live_server_url)
        self.page = self.context.new_page()
        self.page.set_default_timeout(10_000)

    def tearDown(self):
        self.context.close()

    def login(self):
        page = self.page
        page.goto("/connexion/")
        page.fill("input[name=username]", self.parent.email)
        page.fill("input[name=password]", PASSWORD)
        page.get_by_role("button", name="Se connecter").click()
        page.wait_for_url(f"{self.live_server_url}/")

    def first_open_task(self):
        return self.page.locator("details[open] input[type=checkbox]").first

    # --- 1. Connexion ----------------------------------------------------------

    def test_login_shows_the_day_tasks_first(self):
        self.login()
        self.assertTrue(self.page.get_by_text("tâches restantes").is_visible())
        # Téléphone : les tâches du moment avant les encarts (ordre du document).
        tasks_top = self.page.locator("details").first.bounding_box()["y"]
        dinner_top = self.page.get_by_text("Ce soir au menu").bounding_box()["y"]
        self.assertLess(tasks_top, dinner_top)

    # --- 2. Activation de la tablette -----------------------------------------

    def test_tablet_activation_opens_the_children_screen(self):
        self.page.set_viewport_size(TABLET)
        self.login()
        self.page.goto("/reglages/")
        self.page.get_by_role("button", name="Activer sur cet appareil").click()
        self.page.wait_for_url("**/affichage/")
        self.assertTrue(self.page.get_by_role("heading", name="Aliyah").is_visible())
        # La session parent est fermée : les réglages ne sont plus accessibles.
        self.page.goto("/reglages/")
        self.assertIn("/connexion/", self.page.url)
        self.assertEqual(
            self.page.get_by_role("heading", name="Comptes et identifiants").count(), 0
        )

    # --- 3. Cochage d'une tâche ------------------------------------------------

    def test_ticking_a_task_is_saved(self):
        self.login()
        box = self.first_open_task()
        with self.page.expect_response(lambda r: "/fait/" in r.url and r.ok):
            box.click()
        self.assertTrue(box.is_checked())
        self.assertEqual(TaskCompletion.objects.count(), 1)
        self.page.reload()
        self.assertTrue(self.first_open_task().is_checked())

    # --- 4. Transfert du menu vers les courses --------------------------------

    def test_menu_to_shopping_transfer(self):
        recipe = Recipe.objects.create(family=self.family, name="Harira")
        RecipeIngredient.objects.create(
            recipe=recipe, name="lentilles", quantity=Decimal("200"), unit="g"
        )
        MealSlot.objects.create(
            family=self.family,
            date=datetime.date.today(),
            meal=Meal.DINNER,
            kind=MealKind.RECIPE,
            recipe=recipe,
        )
        self.login()
        self.page.goto("/courses/envoyer-le-menu/")
        self.page.get_by_role("button", name="Mettre à jour la liste de courses").click()
        self.page.wait_for_url("**/courses/**")
        self.assertTrue(ShoppingItem.objects.filter(family=self.family, name="lentilles").exists())
        self.page.goto("/courses/")
        self.assertTrue(self.page.get_by_text("lentilles").first.is_visible())

    # --- 5. Coupure réseau pendant un cochage ---------------------------------

    def test_offline_tick_is_reverted_then_retried(self):
        self.login()
        box = self.first_open_task()
        self.context.set_offline(True)
        box.click()
        self.page.locator("#save-error").wait_for(state="visible")
        self.assertFalse(box.is_checked())  # revenu à son état précédent
        self.assertEqual(TaskCompletion.objects.count(), 0)
        self.context.set_offline(False)
        with self.page.expect_response(lambda r: "/fait/" in r.url and r.ok):
            self.page.get_by_role("button", name="Réessayer").click()
        self.page.locator("#save-error").wait_for(state="hidden")
        self.assertTrue(box.is_checked())
        self.assertEqual(TaskCompletion.objects.count(), 1)

    # --- 6. Saisie rapide ------------------------------------------------------

    def test_quick_add_a_shopping_item_from_home(self):
        self.login()
        self.page.get_by_label("Ajout rapide").click()
        self.page.fill("#quick-title", "Lait d'amande")
        self.page.get_by_role("button", name="Ajouter", exact=True).click()
        self.page.wait_for_url("**/?ajoute=course")
        self.page.get_by_text("Ajouté à la liste de courses").wait_for(state="visible")
        self.assertTrue(ShoppingItem.objects.filter(name="Lait d'amande").exists())
        # Onglet « Rendez-vous » : champs date et heure affichés.
        self.page.get_by_label("Ajout rapide").click()
        self.page.get_by_role("tab", name="Rendez-vous").click()
        self.assertTrue(self.page.locator("input[name=time]").is_visible())
