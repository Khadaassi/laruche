from django import forms
from django.db import models, transaction
from django.db.models import Max

from apps.accounts.forms import FIELD_CLASSES
from apps.families.models import Person

from .models import ALL_WEEKDAYS, SCHOOL_DAYS, WEEKDAY_LABELS, WEEKEND, Task, weekdays_to_mask
from .periods import Period


class DaysPreset(models.TextChoices):
    EVERYDAY = "everyday", "Tous les jours"
    SCHOOL = "school", "Jours d'école"
    WEEKEND = "weekend", "Week-end"
    CUSTOM = "custom", "Personnalisé"


PRESET_MASKS = {
    DaysPreset.EVERYDAY: ALL_WEEKDAYS,
    DaysPreset.SCHOOL: SCHOOL_DAYS,
    DaysPreset.WEEKEND: WEEKEND,
}


class When(models.TextChoices):
    ALWAYS = "always", "Toujours"
    RANGE = "range", "Sur une période"


def preset_for(mask: int) -> str:
    return next((p for p, m in PRESET_MASKS.items() if m == mask), DaysPreset.CUSTOM)


class ScheduleFieldsMixin(forms.Form):
    """Jours (raccourci ou jours choisis) et période facultative (du… au…).

    Rendu par `parent/_schedule_fields.html` : les jours et les dates ne
    s'affichent qu'avec « Personnalisé » / « Sur une période » (CSS seul).
    Après `clean()`, `self.schedule` = (masque de jours, début, fin).
    """

    days_preset = forms.ChoiceField(
        label="Jours",
        choices=DaysPreset.choices,
        initial=DaysPreset.EVERYDAY,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
        help_text="Jours d'école : lundi, mardi, jeudi, vendredi.",
    )
    weekday_choices = forms.TypedMultipleChoiceField(
        label="Jours choisis",
        choices=list(enumerate(WEEKDAY_LABELS)),
        coerce=int,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "sr-only"}),
    )
    when = forms.ChoiceField(
        label="Quand",
        choices=When.choices,
        initial=When.ALWAYS,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )
    start_date = forms.DateField(
        label="Du",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    end_date = forms.DateField(
        label="Au",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text="Un seul jour : même date deux fois.",
    )

    def init_schedule(self, weekdays, start, end):
        """Valeurs initiales depuis un objet existant."""
        self.initial.update(
            {
                "days_preset": preset_for(weekdays),
                "weekday_choices": [d for d in range(7) if weekdays & (1 << d)],
                "when": When.RANGE if (start or end) else When.ALWAYS,
                "start_date": start,
                "end_date": end,
            }
        )

    def clean(self):
        cleaned = super().clean()
        preset = cleaned.get("days_preset")
        if preset == DaysPreset.CUSTOM:
            mask = weekdays_to_mask(cleaned.get("weekday_choices") or [])
            if not mask:
                self.add_error("weekday_choices", "Choisissez au moins un jour.")
        else:
            mask = PRESET_MASKS.get(preset, 0)
        start = end = None
        if cleaned.get("when") == When.RANGE:
            start, end = cleaned.get("start_date"), cleaned.get("end_date")
            if not start:
                self.add_error("start_date", "Indiquez la date de début.")
            if not end:
                self.add_error("end_date", "Indiquez la date de fin.")
            if start and end and end < start:
                self.add_error("end_date", "La fin doit être après le début.")
        self.schedule = (mask, start, end)
        return cleaned


class TaskForm(ScheduleFieldsMixin, forms.ModelForm):
    """Nouvelle tâche (pour une ou plusieurs personnes) ou modification d'une tâche."""

    people = forms.ModelMultipleChoiceField(
        label="Pour",
        queryset=Person.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "sr-only"}),
        error_messages={"required": "Choisissez au moins une personne."},
        help_text="Plusieurs choix possibles : une tâche est créée pour chacun.",
    )
    period = forms.ChoiceField(
        label="Période",
        choices=Period.choices,
        widget=forms.RadioSelect(attrs={"class": "sr-only"}),
    )

    class Meta:
        model = Task
        fields = ["title", "period"]
        labels = {"title": "Tâche"}

    def __init__(self, *args, family, **kwargs):
        super().__init__(*args, **kwargs)
        # Les choix proposés sont eux aussi limités à la famille.
        self.fields["people"].queryset = Person.objects.for_family(family)
        if self.instance.pk:
            # Modification : la tâche reste à sa personne.
            del self.fields["people"]
            self.init_schedule(
                self.instance.weekdays, self.instance.start_date, self.instance.end_date
            )
        self.fields["title"].widget.attrs["class"] = FIELD_CLASSES
        for name in ("start_date", "end_date"):
            self.fields[name].widget.attrs["class"] = FIELD_CLASSES

    def _apply(self, task):
        task.weekdays, task.start_date, task.end_date = self.schedule
        task.title, task.period = self.cleaned_data["title"], self.cleaned_data["period"]

    @transaction.atomic
    def save(self, commit=True):
        """Modification : la tâche. Création : la liste des tâches créées (une par personne),
        placées en fin de leur période."""
        if self.instance.pk:
            self._apply(self.instance)
            self.instance.save()
            return self.instance
        created = []
        for person in self.cleaned_data["people"]:
            last = Task.objects.filter(person=person, period=self.cleaned_data["period"]).aggregate(
                m=Max("position")
            )["m"]
            task = Task(person=person, position=0 if last is None else last + 1)
            self._apply(task)
            task.save()
            created.append(task)
        return created
