from django import forms
from django.utils import timezone

from apps.accounts.forms import FIELD_CLASSES
from apps.families.models import Person
from apps.tasks.models import ALL_WEEKDAYS, WEEKDAY_LABELS, weekdays_to_mask

from .models import Frequency, HouseholdChore


class ChoreForm(forms.ModelForm):
    frequency = forms.ChoiceField(
        label="Fréquence",
        choices=Frequency.choices,
        initial=Frequency.WEEKLY,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )
    weekday_choices = forms.TypedMultipleChoiceField(
        label="Jours",
        choices=list(enumerate(WEEKDAY_LABELS)),
        coerce=int,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "sr-only"}),
        help_text="Pour « chaque semaine » et « une semaine sur deux ».",
    )

    class Meta:
        model = HouseholdChore
        fields = ["title", "assignee", "alternate"]
        labels = {"assignee": "Qui", "alternate": "En alternance avec"}
        help_texts = {
            "alternate": "Facultatif. « Qui » s'en charge cette semaine, puis la tâche "
            "change de main chaque lundi."
        }

    def __init__(self, *args, family, **kwargs):
        super().__init__(*args, **kwargs)
        self.family = family
        self.instance.family = family  # avant validation : clean() compare les familles
        # Parent ou enfant : toute personne de la famille (et seulement elle).
        self.fields["assignee"].queryset = Person.objects.for_family(family)
        self.fields["assignee"].empty_label = None
        self.fields["alternate"].queryset = Person.objects.for_family(family)
        self.fields["alternate"].empty_label = "Personne (toujours la même)"
        for name in ("title", "assignee", "alternate"):
            self.fields[name].widget.attrs["class"] = FIELD_CLASSES

    def clean(self):
        cleaned = super().clean()
        frequency = cleaned.get("frequency")
        if frequency and frequency != Frequency.DAILY and not cleaned.get("weekday_choices"):
            self.add_error("weekday_choices", "Choisissez au moins un jour.")
        if frequency == Frequency.BIWEEKLY and cleaned.get("alternate"):
            self.add_error(
                "alternate", "L'alternance se fait chaque semaine : choisissez une autre fréquence."
            )
        return cleaned

    def save(self, commit=True):
        chore = self.instance
        frequency = self.cleaned_data["frequency"]
        if frequency == Frequency.DAILY:
            chore.weekdays, chore.interval_weeks = ALL_WEEKDAYS, 1
        else:
            chore.weekdays = weekdays_to_mask(self.cleaned_data["weekday_choices"])
            chore.interval_weeks = 2 if frequency == Frequency.BIWEEKLY else 1
        # Une semaine sur deux se compte à partir de la semaine en cours.
        chore.start_date = timezone.localdate()
        return super().save(commit=commit)
