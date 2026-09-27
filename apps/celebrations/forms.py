from django import forms

from apps.accounts.forms import FIELD_CLASSES
from apps.families.models import Person

from .models import Celebration, CelebrationTodo, GiftItem, RecipeIdea


class FamilyScopedForm(forms.ModelForm):
    """Applique le style de la charte et limite les choix de personnes à la famille."""

    person_fields: tuple = ()

    def __init__(self, *args, family, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.person_fields:
            self.fields[name].queryset = Person.objects.for_family(family)
            self.fields[name].empty_label = "—"
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", FIELD_CLASSES)


class CelebrationForm(FamilyScopedForm):
    class Meta:
        model = Celebration
        fields = ["name", "date"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "name": forms.TextInput(attrs={"placeholder": "Aïd, anniversaire de Lina…"}),
        }


class TodoForm(FamilyScopedForm):
    person_fields = ("assignee",)

    class Meta:
        model = CelebrationTodo
        fields = ["title", "assignee"]


class GiftForm(FamilyScopedForm):
    person_fields = ("recipient", "buyer")

    class Meta:
        model = GiftItem
        fields = ["item", "recipient", "recipient_name", "buyer", "buyer_name"]
        widgets = {
            "recipient_name": forms.TextInput(attrs={"placeholder": "ou un autre nom"}),
            "buyer_name": forms.TextInput(attrs={"placeholder": "ou un autre nom"}),
        }


class RecipeForm(FamilyScopedForm):
    class Meta:
        model = RecipeIdea
        fields = ["name", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
