from django import forms

from apps.accounts.forms import FIELD_CLASSES

from .models import SchoolHoliday


class SchoolHolidayForm(forms.ModelForm):
    class Meta:
        model = SchoolHoliday
        fields = ["name", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        help_texts = {"name": "Ex. Vacances de fin d'année, pont de mai…"}

    def __init__(self, *args, family, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.family = family
        for field in self.fields.values():
            field.widget.attrs["class"] = FIELD_CLASSES
