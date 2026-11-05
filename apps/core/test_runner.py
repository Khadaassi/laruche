"""Lanceur de tests : les parcours navigateur (tag « browser ») sont exclus par défaut.

Ils demandent Chromium et `npm run build` : `manage.py test --tag browser` les lance
(job CI « Browser tests »). Sans --tag, `manage.py test` reste rapide et autonome.
"""

from django.test.runner import DiscoverRunner


class LaRucheRunner(DiscoverRunner):
    def __init__(self, *args, tags=None, exclude_tags=None, **kwargs):
        exclude_tags = set(exclude_tags or ())
        if not tags or "browser" not in tags:
            exclude_tags.add("browser")
        super().__init__(*args, tags=tags, exclude_tags=exclude_tags, **kwargs)
