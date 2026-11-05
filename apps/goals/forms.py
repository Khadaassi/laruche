from django import forms

from apps.accounts.forms import FIELD_CLASSES

from .models import Contact, Entry, Goal, Step


class _Styled:
    def style(self):
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = FIELD_CLASSES


class GoalForm(_Styled, forms.ModelForm):
    class Meta:
        model = Goal
        fields = ["title", "journal_label", "savings_target", "has_contacts"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style()


class StepForm(_Styled, forms.ModelForm):
    class Meta:
        model = Step
        fields = ["title", "unit", "daily_target", "days_per_week"]
        widgets = {"days_per_week": forms.NumberInput(attrs={"min": 1, "max": 7})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style()


class EntryForm(_Styled, forms.ModelForm):
    class Meta:
        model = Entry
        fields = ["text", "amount"]

    def __init__(self, *args, savings=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not savings:
            del self.fields["amount"]
        self.style()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("text") and not cleaned.get("amount"):
            raise forms.ValidationError("Écrivez une note ou un montant.")
        return cleaned


class ContactForm(_Styled, forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["name", "every_days"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style()
