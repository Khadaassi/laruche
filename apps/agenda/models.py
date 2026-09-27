import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F

from apps.tasks.models import ALL_WEEKDAYS, WEEKDAY_SHORT, mask_to_weekdays


class EventQuerySet(models.QuerySet):
    def for_family(self, family):
        return self.filter(family=family)

    def between(self, start: datetime.date, end: datetime.date):
        """Événements dont la période touche [start, end] (le jour de semaine est
        vérifié ensuite, par `occurs_on`)."""
        return self.filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=end),
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=start),
        )


class Event(models.Model):
    """Rendez-vous ou activité à heure fixe : une seule fois, ou chaque semaine.

    - Une seule fois : `start_date == end_date`, tous les jours cochés.
    - Chaque semaine : jours choisis (`weekdays`), période facultative.
    `people` vide = toute la famille.
    """

    family = models.ForeignKey("families.Family", on_delete=models.CASCADE, related_name="events")
    title = models.CharField("quoi", max_length=80)
    people = models.ManyToManyField(
        "families.Person", blank=True, related_name="events", verbose_name="qui"
    )
    start_time = models.TimeField("de")
    end_time = models.TimeField("à")
    weekdays = models.PositiveSmallIntegerField("jours", default=ALL_WEEKDAYS)
    start_date = models.DateField("du", null=True, blank=True)
    end_date = models.DateField("au", null=True, blank=True)
    location = models.CharField("où", max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        verbose_name = "rendez-vous"
        verbose_name_plural = "rendez-vous"
        ordering = ["start_time", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=F("start_time")), name="event_times_ordered"
            ),
            models.CheckConstraint(
                condition=models.Q(weekdays__gt=0, weekdays__lte=ALL_WEEKDAYS),
                name="event_weekdays_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(start_date__isnull=True)
                | models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=F("start_date")),
                name="event_dates_ordered",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "La fin doit être après le début."})

    @property
    def is_once(self) -> bool:
        return self.start_date is not None and self.start_date == self.end_date

    def occurs_on(self, day: datetime.date) -> bool:
        if self.start_date and day < self.start_date:
            return False
        if self.end_date and day > self.end_date:
            return False
        return bool(self.weekdays & (1 << day.weekday()))

    @property
    def time_display(self) -> str:
        return f"{self.start_time:%H:%M}–{self.end_time:%H:%M}".replace(":", "h")

    @property
    def schedule_display(self) -> str:
        if self.is_once:
            return f"le {self.start_date:%d/%m}"
        days = (
            "tous les jours"
            if self.weekdays == ALL_WEEKDAYS
            else " ".join(WEEKDAY_SHORT[d] for d in mask_to_weekdays(self.weekdays))
        )
        if self.start_date and self.end_date:
            return f"{days}, du {self.start_date:%d/%m} au {self.end_date:%d/%m}"
        return f"chaque semaine : {days}"
