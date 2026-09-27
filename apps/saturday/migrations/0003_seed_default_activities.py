from django.db import migrations


def seed_existing_families(apps, schema_editor):
    """Donne le catalogue de départ aux familles créées avant la Phase 3."""
    from apps.saturday.defaults import seed_default_activities

    Family = apps.get_model("families", "Family")
    SaturdayActivity = apps.get_model("saturday", "SaturdayActivity")
    for family in Family.objects.all():
        seed_default_activities(family, model=SaturdayActivity)


class Migration(migrations.Migration):

    dependencies = [
        ("families", "0001_initial"),
        ("saturday", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(seed_existing_families, migrations.RunPython.noop),
    ]
