import re

from django import forms

from apps.accounts.forms import FIELD_CLASSES

from .models import Meal, MealKind, MealSlot, Recipe, RecipeIngredient

CHECKBOX_CLASSES = "h-6 w-6 shrink-0 accent-sage"
# Numérotation tapée à la main en début de ligne : « 1. », « 2) », « - », « • ».
STEP_PREFIX = re.compile(r"^\s*(?:\d+\s*[.)]|[-•*])\s*")
NOTHING = "none"


def style(form):
    for field in form.fields.values():
        if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
            field.widget.attrs.setdefault("class", FIELD_CLASSES)


class RecipeForm(forms.ModelForm):
    """Recette + étapes. Les étapes se saisissent une par ligne, et sont
    enregistrées comme une liste ordonnée (une ligne `RecipeStep` chacune)."""

    steps_text = forms.CharField(
        label="Étapes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="Une étape par ligne, dans l'ordre. La numérotation est automatique.",
    )

    class Meta:
        model = Recipe
        fields = ["name", "prep_minutes", "is_favorite"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Couscous, gratin de pâtes…"}),
            "prep_minutes": forms.NumberInput(attrs={"inputmode": "numeric", "min": 0}),
            "is_favorite": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
        }

    def __init__(self, *args, family, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.family = family
        if self.instance.pk and not self.is_bound:
            self.initial["steps_text"] = "\n".join(s.text for s in self.instance.steps.all())
        style(self)

    def clean_steps_text(self):
        raw = self.cleaned_data["steps_text"].splitlines()
        steps = [text for text in (STEP_PREFIX.sub("", line).strip() for line in raw) if text]
        if any(len(step) > 500 for step in steps):
            raise forms.ValidationError("Une étape ne doit pas dépasser 500 caractères.")
        return steps

    def save(self, commit=True):
        recipe = super().save()
        recipe.replace_steps(self.cleaned_data["steps_text"])
        return recipe


class IngredientForm(forms.ModelForm):
    class Meta:
        model = RecipeIngredient
        fields = ["name", "quantity", "unit"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Carottes"}),
            "quantity": forms.NumberInput(attrs={"inputmode": "decimal", "step": "any", "min": 0}),
        }
        help_texts = {"quantity": "Vide = à convenance (sel, poivre…)."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)


class MealSlotForm(forms.Form):
    """Un repas du menu : une recette, un repas libre, ou rien."""

    kind = forms.ChoiceField(
        label="Au menu",
        choices=[*MealKind.choices, (NOTHING, "Rien de prévu")],
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )
    recipe = forms.ModelChoiceField(label="Recette", queryset=Recipe.objects.none(), required=False)
    note = forms.CharField(
        label="Précision",
        max_length=80,
        required=False,
        help_text="Restes du couscous, chez mamie, pizza… (obligatoire pour « Autre »).",
    )

    def __init__(self, *args, family, slot=None, **kwargs):
        if slot is not None:
            kwargs["initial"] = {"kind": slot.kind, "recipe": slot.recipe_id, "note": slot.note}
        else:
            kwargs["initial"] = {"kind": NOTHING}
        super().__init__(*args, **kwargs)
        self.fields["recipe"].queryset = Recipe.objects.for_family(family)
        self.fields["recipe"].empty_label = "Choisir une recette"
        style(self)

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        if kind == MealKind.RECIPE and not cleaned.get("recipe"):
            self.add_error("recipe", "Choisissez une recette.")
        if kind == MealKind.FREE and not cleaned.get("note", "").strip():
            self.add_error("note", "Précisez ce qui est prévu.")
        if kind != MealKind.RECIPE:
            cleaned["recipe"] = None
        return cleaned

    def save(self, family, date, meal: Meal):
        """Crée, modifie ou supprime le repas. Renvoie le repas (ou None)."""
        kind = self.cleaned_data["kind"]
        if kind == NOTHING:
            MealSlot.objects.for_family(family).filter(date=date, meal=meal).delete()
            return None
        slot, _ = MealSlot.objects.update_or_create(
            family=family,
            date=date,
            meal=meal,
            defaults={
                "kind": kind,
                "recipe": self.cleaned_data["recipe"],
                "note": self.cleaned_data["note"].strip(),
            },
        )
        return slot
