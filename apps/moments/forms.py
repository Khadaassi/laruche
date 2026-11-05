from django import forms

from apps.accounts.forms import FIELD_CLASSES

from .models import MomentSettings


class MomentSettingsForm(forms.ModelForm):
    hijri_shift = forms.TypedChoiceField(
        label="Dates du Ramadan et de l'Aïd",
        coerce=int,
        choices=[
            (-1, "Un jour plus tôt que le calcul"),
            (0, "Comme le calcul"),
            (1, "Un jour plus tard que le calcul"),
        ],
        help_text="Ajustez si l'annonce officielle (observation de la lune) diffère.",
    )

    class Meta:
        model = MomentSettings
        fields = ["hijri_shift", "eid_days", "ramadan_light"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("hijri_shift", "eid_days"):
            self.fields[name].widget.attrs["class"] = FIELD_CLASSES
        self.fields["eid_days"].widget.attrs.update({"min": 1, "max": 3})
