"""Vacances scolaires : réservées aux parents, scopées par famille."""

from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.families.access import parent_required

from .forms import SchoolHolidayForm
from .models import SchoolHoliday
from .services import add_zone_b


@require_http_methods(["GET", "POST"])
@parent_required
def manage(request):
    form = SchoolHolidayForm(request.POST or None, family=request.family)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("holidays:manage")
    today = timezone.localdate()
    holidays = SchoolHoliday.objects.for_family(request.family)
    return render(
        request,
        "parent/holidays_manage.html",
        {
            "nav_active": "settings",
            "form": form,
            "current": holidays.filter(end_date__gte=today),
            "today": today,
        },
        status=400 if form.is_bound and form.errors else 200,
    )


@require_POST
@parent_required
def prefill(request):
    """Ajoute le calendrier officiel zone B (sans doublon)."""
    add_zone_b(request.family)
    return redirect("holidays:manage")


@require_POST
@parent_required
def delete(request, pk):
    get_object_or_404(SchoolHoliday.objects.for_family(request.family), pk=pk).delete()
    return redirect("holidays:manage")
