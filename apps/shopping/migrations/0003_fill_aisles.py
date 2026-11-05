"""Rayon deviné pour les articles déjà sur la liste."""

from django.db import migrations


def forwards(apps, schema_editor):
    from apps.shopping.aisles import guess_aisle

    ShoppingItem = apps.get_model("shopping", "ShoppingItem")
    for item in ShoppingItem.objects.filter(aisle=""):
        item.aisle = guess_aisle(item.name)
        item.save(update_fields=["aisle"])


class Migration(migrations.Migration):
    dependencies = [("shopping", "0002_shopping_item_aisle")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
