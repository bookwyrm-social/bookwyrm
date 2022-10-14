""" using django model forms """
import datetime
from django import forms
from django.forms import widgets
from django.utils.translation import gettext_lazy as _

from bookwyrm import models
from bookwyrm.models.user import FeedFilterChoices
from .custom_form import CustomForm

# pylint: disable=missing-class-docstring
class FeedStatusTypesForm(CustomForm):
    class Meta:
        model = models.User
        fields = ["feed_status_types"]
        help_texts = {f: None for f in fields}
        widgets = {
            "feed_status_types": widgets.CheckboxSelectMultiple(
                choices=FeedFilterChoices,
            ),
        }


class ImportForm(forms.Form):
    csv_file = forms.FileField()


class ShelfForm(CustomForm):
    class Meta:
        model = models.Shelf
        fields = ["user", "name", "privacy", "description"]


class GoalForm(CustomForm):
    class Meta:
        model = models.AnnualGoal
        fields = ["user", "year", "goal", "privacy"]


class ReportForm(CustomForm):
    class Meta:
        model = models.Report
        fields = ["user", "reporter", "status", "links", "note"]


class ReadThroughForm(CustomForm):
    def clean(self):
        """don't let readthroughs end before they start"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        finish_date = cleaned_data.get("finish_date")
        if start_date and finish_date and start_date > finish_date:
            self.add_error(
                "finish_date", _("Reading finish date cannot be before start date.")
            )
        stopped_date = cleaned_data.get("stopped_date")
        if start_date and stopped_date and start_date > stopped_date:
            self.add_error(
                "stopped_date", _("Reading stopped date cannot be before start date.")
            )
        current_time = datetime.datetime.now()
        if (
            stopped_date is not None
            and current_time.timestamp() < stopped_date.timestamp()
        ):
            self.add_error(
                "stopped_date", _("Reading stopped date cannot be in the future.")
            )
        if (
            finish_date is not None
            and current_time.timestamp() < finish_date.timestamp()
        ):
            self.add_error(
                "finish_date", _("Reading finished date cannot be in the future.")
            )

    class Meta:
        model = models.ReadThrough
        fields = ["user", "book", "start_date", "finish_date", "stopped_date"]
