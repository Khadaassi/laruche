from django import forms

from apps.meals.forms import CHECKBOX_CLASSES, style

from .models import ShoppingItem


class ShoppingItemForm(forms.ModelForm):
    """Ajout ou modification d'un article. `recurring` : produits ajoutés à la main seulement."""

    class Meta:
        model = ShoppingItem
        fields = ["name", "quantity", "unit", "recurring"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Lait, pain, lessive…"}),
            "quantity": forms.NumberInput(attrs={"inputmode": "decimal", "step": "any", "min": 0}),
            "recurring": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
        }

    def __init__(self, *args, family, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.family = family
        if self.instance.is_from_menu:
            del self.fields["recurring"]
        self.fields["quantity"].required = False
        style(self)
