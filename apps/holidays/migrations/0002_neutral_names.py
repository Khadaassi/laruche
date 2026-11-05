"""Noms neutres : la famille ne fête ni les fêtes commerciales ni les fêtes chrétiennes."""

from django.db import migrations

RENAMES = {
    "Vacances de Noël": "Vacances de fin d'année",
    "Vacances de la Toussaint": "Vacances d'automne",
}


def forwards(apps, schema_editor):
    SchoolHoliday = apps.get_model("holidays", "SchoolHoliday")
    for old, new in RENAMES.items():
        SchoolHoliday.objects.filter(name=old).update(name=new)


class Migration(migrations.Migration):
    dependencies = [("holidays", "0001_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
