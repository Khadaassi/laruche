from django import forms

from apps.accounts.forms import FIELD_CLASSES

from .draw import CostFilter, PlaceFilter
from .models import SaturdayActivity

CHECKBOX_CLASSES = "h-6 w-6 shrink-0 accent-sage"


class DrawFiltersForm(forms.Form):
    """Les deux filtres rapides, rendus en gros boutons (puces)."""

    cost = forms.ChoiceField(
        label="Côté budget",
        choices=CostFilter.choices,
        initial=CostFilter.ANY,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )
    place = forms.ChoiceField(
        label="Où ça ?",
        choices=PlaceFilter.choices,
        initial=PlaceFilter.ANY,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )


class ActivityForm(forms.ModelForm):
    class Meta:
        model = SaturdayActivity
        fields = ["name", "season", "place", "is_free", "price", "star_cost", "last_done_on"]
        widgets = {
            "season": forms.RadioSelect(attrs={"class": "sr-only"}),
            "place": forms.RadioSelect(attrs={"class": "sr-only"}),
            "is_free": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
            "last_done_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, family, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.family = family
        for name in ("name", "price", "star_cost", "last_done_on"):
            self.fields[name].widget.attrs["class"] = FIELD_CLASSES
