from django import forms

from apps.accounts.forms import FIELD_CLASSES


class DeviceForm(forms.Form):
    name = forms.CharField(
        label="Nom de l'appareil",
        max_length=60,
        initial="Tablette de la cuisine",
        widget=forms.TextInput(attrs={"class": FIELD_CLASSES}),
    )
