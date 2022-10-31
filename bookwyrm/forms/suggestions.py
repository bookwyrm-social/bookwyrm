from django import forms
from django.forms import widgets
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_celery_beat.models import IntervalSchedule

from bookwyrm import models
from .custom_form import StyledForm


class SuggestionForm(StyledForm):
    class Meta:
        model = models.SuggestedGenre

        fields = ("name", "description")

        widgets = {
            "name": forms.TextInput(attrs={"aria-describedby": "desc_name"}),
            "description": forms.Textarea(
                attrs={
                    "aria-describedby": "desc_desc",
                    "class": "textarea",
                    "cols": "40",
                }
            ),
        }

class MinimumVotesForm(StyledForm):
    class Meta:
        model = models.MinimumVotesSetting

        fields = ['minimum_votes']

        widgets = {
            'minimum_votes': forms.IntegerField(min_value=1, label_suffix='Minimum Votes')
        }