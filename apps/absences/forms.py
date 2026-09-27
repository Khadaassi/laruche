from django import forms
from django.db import models, transaction
from django.utils import timezone

from apps.accounts.forms import FIELD_CLASSES
from apps.families.models import Person

from .models import Absence, AbsenceKind


class Scope(models.TextChoices):
    FAMILY = "family", "Toute la famille"
    PEOPLE = "people", "Certaines personnes"


class AbsenceForm(forms.Form):
    """Déclare une absence pour toute la famille, ou une par personne choisie."""

    scope = forms.ChoiceField(
        label="Qui",
        choices=Scope.choices,
        initial=Scope.PEOPLE,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )
    people = forms.ModelMultipleChoiceField(
        label="Personnes",
        queryset=Person.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "sr-only"}),
    )
    kind = forms.ChoiceField(
        label="Motif",
        choices=AbsenceKind.choices,
        initial=AbsenceKind.SICK,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )
    start_date = forms.DateField(
        label="Du", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    end_date = forms.DateField(
        label="Au",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text="Un seul jour : même date deux fois.",
    )
    note = forms.CharField(
        label="Précision", max_length=80, required=False, help_text="Chez mamie, gastro…"
    )

    def __init__(self, *args, family, **kwargs):
        super().__init__(*args, **kwargs)
        self.family = family
        self.fields["people"].queryset = Person.objects.for_family(family)
        today = timezone.localdate()
        self.initial.setdefault("start_date", today)
        self.initial.setdefault("end_date", today)
        for name in ("start_date", "end_date", "note"):
            self.fields[name].widget.attrs["class"] = FIELD_CLASSES

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("scope") == Scope.PEOPLE and not cleaned.get("people"):
            self.add_error("people", "Choisissez au moins une personne.")
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "La fin doit être après le début.")
        return cleaned

    @transaction.atomic
    def save(self) -> list[Absence]:
        data = self.cleaned_data
        people = [None] if data["scope"] == Scope.FAMILY else list(data["people"])
        return [
            Absence.objects.create(
                family=self.family,
                person=person,
                kind=data["kind"],
                note=data["note"].strip(),
                start_date=data["start_date"],
                end_date=data["end_date"],
            )
            for person in people
        ]
