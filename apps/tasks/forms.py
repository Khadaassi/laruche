from django import forms

from apps.accounts.forms import FIELD_CLASSES
from apps.families.models import Person

from .models import WEEKDAY_LABELS, Task, weekdays_to_mask
from .periods import Period


class TaskForm(forms.ModelForm):
    weekday_choices = forms.TypedMultipleChoiceField(
        label="Jours",
        choices=list(enumerate(WEEKDAY_LABELS)),
        coerce=int,
        initial=list(range(7)),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "sr-only"}),
        error_messages={"required": "Choisissez au moins un jour."},
    )
    period = forms.ChoiceField(
        label="Période",
        choices=Period.choices,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )

    class Meta:
        model = Task
        fields = ["person", "title", "period"]
        labels = {"person": "Pour", "title": "Tâche"}

    def __init__(self, *args, family, **kwargs):
        super().__init__(*args, **kwargs)
        # Les choix proposés sont eux aussi limités à la famille.
        self.fields["person"].queryset = Person.objects.for_family(family)
        self.fields["person"].empty_label = None
        for name in ("person", "title"):
            self.fields[name].widget.attrs["class"] = FIELD_CLASSES

    def save(self, commit=True):
        self.instance.weekdays = weekdays_to_mask(self.cleaned_data["weekday_choices"])
        return super().save(commit=commit)
