"""Valeurs de départ du mode vacances pour les tâches existantes.

Prière → obligatoire ; devoirs → objectif de la semaine (3 fois). Le reste
reste en bonus (valeur par défaut). Modifiable ensuite dans Réglages → Tâches.
"""

import unicodedata

from django.db import migrations


def plain(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def forwards(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    for task in Task.objects.all():
        title = plain(task.title)
        if "priere" in title or "salat" in title:
            task.holiday_mode = "required"
        elif "devoir" in title:
            task.holiday_mode = "weekly"
            task.weekly_target = 3
        else:
            continue
        task.save(update_fields=["holiday_mode", "weekly_target"])


class Migration(migrations.Migration):
    dependencies = [("tasks", "0005_task_holiday_mode_task_weekly_target_and_more")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
