"""Qui peut cocher quelle tâche (comptes connectés).

L'affichage partagé a ses propres règles : apps.display.views.toggle.
"""


def can_toggle(membership, own_person, task) -> bool:
    """Parent : toutes les tâches de sa famille. Enfant : uniquement les siennes.

    Suppose `task` déjà obtenue via `Task.objects.for_family(...)`.
    """
    if membership.is_parent:
        return True
    return own_person is not None and task.person_id == own_person.pk
