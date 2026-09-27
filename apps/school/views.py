from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.families.access import parent_required
from apps.families.models import Person

from .forms import OverrideForm, WeekScheduleForm
from .models import SchoolDayOverride


def _page(request, week_forms=None, override_form=None, status=200):
    children = Person.objects.for_family(request.family).children()
    week_forms = week_forms or {}
    return render(
        request,
        "parent/school_manage.html",
        {
            "nav_active": "settings",
            "week_forms": [week_forms.get(c.pk) or WeekScheduleForm(person=c) for c in children],
            "override_form": override_form or OverrideForm(family=request.family),
            "overrides": SchoolDayOverride.objects.for_family(request.family)
            .filter(date__gte=timezone.localdate())
            .select_related("person"),
        },
        status=status,
    )


@require_GET
@parent_required
def manage(request):
    """Réglages → école : semaine type par enfant et exceptions datées."""
    return _page(request)


@require_POST
@parent_required
def save_week(request, person_pk):
    child = get_object_or_404(Person.objects.for_family(request.family).children(), pk=person_pk)
    form = WeekScheduleForm(request.POST, person=child)
    if form.is_valid():
        form.save()
        return redirect("school:manage")
    return _page(request, week_forms={child.pk: form}, status=400)


@require_POST
@parent_required
def add_override(request):
    form = OverrideForm(request.POST, family=request.family)
    if form.is_valid():
        form.save()
        return redirect("school:manage")
    return _page(request, override_form=form, status=400)


@require_POST
@parent_required
def delete_override(request, pk):
    get_object_or_404(SchoolDayOverride.objects.for_family(request.family), pk=pk).delete()
    return redirect("school:manage")
