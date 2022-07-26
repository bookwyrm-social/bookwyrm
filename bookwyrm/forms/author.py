""" using django model forms """
from django import forms

from bookwyrm import models
from .custom_form import CustomForm


# pylint: disable=missing-class-docstring
class AuthorForm(CustomForm):
    class Meta:
        model = models.Author
        fields = [
            "last_edited_by",
            "name",
            "aliases",
            "bio",
            "wikipedia_link",
            "born",
            "died",
            "openlibrary_key",
            "inventaire_id",
            "librarything_key",
            "goodreads_key",
            "isni",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"aria-describedby": "desc_name"}),
            "aliases": forms.TextInput(attrs={"aria-describedby": "desc_aliases"}),
            "bio": forms.Textarea(attrs={"aria-describedby": "desc_bio"}),
            "wikipedia_link": forms.TextInput(
                attrs={"aria-describedby": "desc_wikipedia_link"}
            ),
            "born": forms.SelectDateWidget(attrs={"aria-describedby": "desc_born"}),
            "died": forms.SelectDateWidget(attrs={"aria-describedby": "desc_died"}),
            "oepnlibrary_key": forms.TextInput(
                attrs={"aria-describedby": "desc_oepnlibrary_key"}
            ),
            "inventaire_id": forms.TextInput(
                attrs={"aria-describedby": "desc_inventaire_id"}
            ),
            "librarything_key": forms.TextInput(
                attrs={"aria-describedby": "desc_librarything_key"}
            ),
            "goodreads_key": forms.TextInput(
                attrs={"aria-describedby": "desc_goodreads_key"}
            ),
        }
