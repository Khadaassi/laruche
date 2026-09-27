from django import forms
from django.db import models, transaction

from apps.absences.forms import Scope
from apps.accounts.forms import FIELD_CLASSES
from apps.families.models import Person
from apps.tasks.forms import ScheduleFieldsMixin
from apps.tasks.models import ALL_WEEKDAYS

from .models import Event


class Repeat(models.TextChoices):
    ONCE = "once", "Une seule fois"
    WEEKLY = "weekly", "Chaque semaine"


TIME_WIDGET = forms.TimeInput(attrs={"type": "time", "step": 300}, format="%H:%M")


class EventForm(ScheduleFieldsMixin, forms.ModelForm):
    """Rendez-vous : une seule fois (date), ou chaque semaine (jours + période)."""

    scope = forms.ChoiceField(
        label="Pour qui",
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
    repeat = forms.ChoiceField(
        label="Répétition",
        choices=Repeat.choices,
        initial=Repeat.ONCE,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )
    date = forms.DateField(
        label="Le",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    class Meta:
        model = Event
        fields = ["title", "start_time", "end_time", "location"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Dentiste, foot, piano…"}),
            "start_time": TIME_WIDGET,
            "end_time": TIME_WIDGET,
            "location": forms.TextInput(attrs={"placeholder": "Facultatif"}),
        }

    def __init__(self, *args, family, day=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.family = family
        self.fields["people"].queryset = Person.objects.for_family(family)
        event = self.instance
        if event.pk:
            chosen = list(event.people.all())
            self.initial.update(
                {
                    "scope": Scope.PEOPLE if chosen else Scope.FAMILY,
                    "people": chosen,
                    "repeat": Repeat.ONCE if event.is_once else Repeat.WEEKLY,
                    "date": event.start_date if event.is_once else None,
                }
            )
            if not event.is_once:
                self.init_schedule(event.weekdays, event.start_date, event.end_date)
        elif day:
            self.initial["date"] = day
        for name in (
            "title",
            "start_time",
            "end_time",
            "location",
            "date",
            "start_date",
            "end_date",
        ):
            self.fields[name].widget.attrs["class"] = FIELD_CLASSES

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("scope") == Scope.PEOPLE and not cleaned.get("people"):
            self.add_error("people", "Choisissez au moins une personne.")
        if cleaned.get("repeat") == Repeat.ONCE:
            # La planification hebdomadaire ne s'applique pas : on n'en garde pas les erreurs.
            for name in ("days_preset", "weekday_choices", "when", "start_date", "end_date"):
                self.errors.pop(name, None)
            date = cleaned.get("date")
            if not date:
                self.add_error("date", "Indiquez la date.")
            self.schedule = (ALL_WEEKDAYS, date, date)
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        event = super().save(commit=False)
        event.weekdays, event.start_date, event.end_date = self.schedule
        event.save()
        people = self.cleaned_data["people"] if self.cleaned_data["scope"] == Scope.PEOPLE else []
        event.people.set(people)
        return event
