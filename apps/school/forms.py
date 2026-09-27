from django import forms
from django.db import transaction

from apps.accounts.forms import FIELD_CLASSES
from apps.families.models import Person
from apps.tasks.models import WEEKDAY_LABELS

from .models import SCHOOL_WEEKDAYS, Lunch, SchoolDayOverride, SchoolDaySchedule

NOT_SET = ""
CHECKBOX_CLASSES = "h-6 w-6 shrink-0 accent-sage"
LUNCH_CHOICES = [(NOT_SET, "—"), *Lunch.choices]


class WeekScheduleForm(forms.Form):
    """Semaine type d'UN enfant : midi, précision et étude pour lundi → vendredi.

    « — » supprime le jour (rien ne s'affiche ce jour-là).
    """

    def __init__(self, *args, person, **kwargs):
        self.person = person
        kwargs.setdefault("prefix", f"child-{person.pk}")
        super().__init__(*args, **kwargs)
        existing = {row.weekday: row for row in person.school_schedules.all()}
        for day in SCHOOL_WEEKDAYS:
            row = existing.get(day)
            self.fields[f"lunch_{day}"] = forms.ChoiceField(
                label=f"{WEEKDAY_LABELS[day]} midi",
                choices=LUNCH_CHOICES,
                required=False,
                initial=row.lunch if row else NOT_SET,
                widget=forms.Select(attrs={"class": FIELD_CLASSES}),
            )
            self.fields[f"note_{day}"] = forms.CharField(
                label=f"{WEEKDAY_LABELS[day]} précision",
                max_length=60,
                required=False,
                initial=row.lunch_note if row else "",
                widget=forms.TextInput(attrs={"class": FIELD_CLASSES, "placeholder": "Précision"}),
            )
            self.fields[f"study_{day}"] = forms.BooleanField(
                label=f"{WEEKDAY_LABELS[day]} étude",
                required=False,
                initial=row.study if row else False,
                widget=forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
            )

    def days(self):
        """Pour le gabarit : un triplet de champs par jour."""
        return [
            (WEEKDAY_LABELS[d], self[f"lunch_{d}"], self[f"note_{d}"], self[f"study_{d}"])
            for d in SCHOOL_WEEKDAYS
        ]

    @transaction.atomic
    def save(self):
        for day in SCHOOL_WEEKDAYS:
            lunch = self.cleaned_data[f"lunch_{day}"]
            rows = SchoolDaySchedule.objects.filter(person=self.person, weekday=day)
            if lunch == NOT_SET:
                rows.delete()
                continue
            SchoolDaySchedule.objects.update_or_create(
                person=self.person,
                weekday=day,
                defaults={
                    "lunch": lunch,
                    "lunch_note": self.cleaned_data[f"note_{day}"].strip(),
                    "study": self.cleaned_data[f"study_{day}"],
                },
            )


class OverrideForm(forms.ModelForm):
    """Exception pour une date : remplace (ou crée) celle qui existe déjà."""

    class Meta:
        model = SchoolDayOverride
        fields = ["person", "date", "lunch", "lunch_note", "study"]
        labels = {"person": "Enfant"}
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "study": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
        }

    def __init__(self, *args, family, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["person"].queryset = Person.objects.for_family(family).children()
        self.fields["person"].empty_label = None
        for name in ("person", "date", "lunch", "lunch_note"):
            self.fields[name].widget.attrs["class"] = FIELD_CLASSES

    def clean(self):
        cleaned = super().clean()
        # Une exception existe déjà pour cet enfant et ce jour : on la modifie
        # (le formulaire s'y rattache avant la validation des contraintes).
        person, date = cleaned.get("person"), cleaned.get("date")
        if person and date:
            existing = SchoolDayOverride.objects.filter(person=person, date=date).first()
            if existing is not None:
                self.instance = existing
        cleaned["lunch_note"] = cleaned.get("lunch_note", "").strip()
        return cleaned
