"""Saisie rapide (bouton « + » des pages parent) : formulaire commun."""

from django import template

from apps.families.models import Person

register = template.Library()


@register.inclusion_tag("parent/_quick_add.html", takes_context=True)
def quick_add(context):
    request = context["request"]
    family = getattr(request, "family", None)
    membership = getattr(request, "membership", None)
    if family is None or membership is None or not membership.is_parent:
        return {"show": False}
    people = list(Person.objects.for_family(family))
    return {
        "show": True,
        "request": request,
        "csrf_token": context.get("csrf_token"),
        "children": [p for p in people if p.is_child],
        "people": people,
        "next": request.get_full_path(),
    }
