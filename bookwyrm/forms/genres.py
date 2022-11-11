from django import forms
from django.forms import widgets
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_celery_beat.models import IntervalSchedule

from bookwyrm import models
from .custom_form import StyledForm


class GenreForm(StyledForm):
    class Meta:
        model = models.Genre

        fields = ("genre_name", "description")

        widgets = {
            "genre_name": forms.TextInput(attrs={"aria-describedby": "desc_name"}),
            "genre_description": forms.Textarea(
                attrs={
                    "aria-describedby": "desc_desc",
                    "class": "textarea",
                    "cols": "40",
                }
            ),
        }
