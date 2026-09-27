"""Vacances et absences : réservées aux parents, scopées par famille."""

from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.families.access import parent_required

from .forms import AbsenceForm
from .models import Absence


@require_http_methods(["GET", "POST"])
@parent_required
def manage(request):
    form = AbsenceForm(request.POST or None, family=request.family)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("absences:manage")
    today = timezone.localdate()
    absences = Absence.objects.for_family(request.family).select_related("person")
    return render(
        request,
        "parent/absences_manage.html",
        {
            "nav_active": "settings",
            "form": form,
            "current": absences.filter(end_date__gte=today),
            "past": absences.filter(end_date__lt=today).order_by("-start_date")[:10],
            "today": today,
        },
        status=400 if form.is_bound and form.errors else 200,
    )


@require_POST
@parent_required
def delete(request, pk):
    get_object_or_404(Absence.objects.for_family(request.family), pk=pk).delete()
    return redirect("absences:manage")
