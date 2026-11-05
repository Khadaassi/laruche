"""Le « Marché de Noël » du catalogue de départ devient « Bowling »."""

from decimal import Decimal

from django.db import migrations


def forwards(apps, schema_editor):
    SaturdayActivity = apps.get_model("saturday", "SaturdayActivity")
    for activity in SaturdayActivity.objects.filter(name="Marché de Noël"):
        if SaturdayActivity.objects.filter(family_id=activity.family_id, name="Bowling").exists():
            activity.delete()  # les samedis passés gardent leur nom (copie `activity_name`)
            continue
        activity.name = "Bowling"
        activity.is_free = False
        activity.price = Decimal("8")
        activity.save(update_fields=["name", "is_free", "price"])


class Migration(migrations.Migration):
    dependencies = [("saturday", "0003_seed_default_activities")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
