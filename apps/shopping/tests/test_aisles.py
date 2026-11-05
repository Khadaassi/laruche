"""Rayons : devinette, mode magasin groupé dans l'ordre du parcours."""

from django.test import TestCase
from django.urls import reverse

from apps.families.tests.factories import SecureClientMixin, join, make_family
from apps.shopping.aisles import Aisle, guess_aisle
from apps.shopping.models import ShoppingItem, Status


class GuessTests(TestCase):
    def test_common_items(self):
        cases = {
            "Tomates": Aisle.PRODUCE,
            "poireau": Aisle.PRODUCE,  # « eau » en fin de mot : pas une boisson
            "Gâteau au chocolat": Aisle.SWEET,
            "Eau gazeuse": Aisle.DRINKS,
            "Lait": Aisle.DAIRY,
            "lait de coco": Aisle.SAVORY,
            "Tomates concassées": Aisle.SAVORY,
            "Bouillon de légumes (cube)": Aisle.SAVORY,
            "Pâte à pizza": Aisle.BAKERY,
            "Pâtes": Aisle.SAVORY,
            "Escalopes de dinde": Aisle.MEAT_FISH,
            "Lessive": Aisle.CLEANING,
            "Dentifrice": Aisle.HYGIENE,
            "Petits pois surgelés": Aisle.FROZEN,
            "Bougies": Aisle.OTHER,
        }
        for name, aisle in cases.items():
            self.assertEqual(guess_aisle(name), aisle, name)

    def test_set_on_save_and_editable(self):
        family = make_family()
        item = ShoppingItem.objects.create(family=family, name="Yaourts nature")
        self.assertEqual(item.aisle, Aisle.DAIRY)
        item.aisle = Aisle.OTHER
        item.save()
        item.refresh_from_db()
        self.assertEqual(item.aisle, Aisle.OTHER)


class StoreViewTests(SecureClientMixin, TestCase):
    def setUp(self):
        self.family = make_family()
        self.parent = join(self.family, "Sam")
        self.client.force_login(self.parent)
        for name in ("Lessive", "Tomates", "Lait", "Pain"):
            ShoppingItem.objects.create(family=self.family, name=name)
        ShoppingItem.objects.create(family=self.family, name="Miel", status=Status.BOUGHT)

    def test_grouped_in_store_order(self):
        page = self.get(reverse("shopping:store")).content.decode()
        order = [
            page.index(label)
            for label in ("Fruits et légumes", "Boulangerie", "Crèmerie", "Entretien")
        ]
        self.assertEqual(order, sorted(order))
        self.assertIn("Dans le panier (1)", page)

    def test_link_from_list_and_isolation(self):
        self.assertContains(
            self.get(reverse("shopping:index")), "En magasin : la liste par rayon (4)"
        )
        other = make_family()
        ShoppingItem.objects.create(family=other, name="Intrus")
        self.assertNotContains(self.get(reverse("shopping:store")), "Intrus")
