""" using django model forms """
from django import forms
from django.forms import ChoiceField
from django.utils.translation import gettext_lazy as _

from bookwyrm import models
from .custom_form import CustomForm


# pylint: disable=missing-class-docstring
class ListForm(CustomForm):
    class Meta:
        model = models.List
        fields = ["user", "name", "description", "curation", "privacy", "group"]


class ListItemForm(CustomForm):
    class Meta:
        model = models.ListItem
        fields = ["user", "book", "book_list", "notes"]


class SortListForm(forms.Form):
    sort_by = ChoiceField(
        choices=(
            ("order", _("List Order")),
            ("title", _("Book Title")),
            ("rating", _("Rating")),
        ),
        label=_("Sort By"),
    )
    direction = ChoiceField(
        choices=(
            ("ascending", _("Ascending")),
            ("descending", _("Descending")),
        ),
    )
