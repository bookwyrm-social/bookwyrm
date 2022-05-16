""" using django model forms """
from django import forms

from bookwyrm import models
from bookwyrm.models.fields import ClearableFileInputWithWarning
from .custom_form import CustomForm
from .widgets import ArrayWidget, SelectDateWidget, Select


# pylint: disable=missing-class-docstring
class CoverForm(CustomForm):
    class Meta:
        model = models.Book
        fields = ["cover"]
        help_texts = {f: None for f in fields}


class EditionForm(CustomForm):
    class Meta:
        model = models.Edition
        exclude = [
            "remote_id",
            "origin_id",
            "created_date",
            "updated_date",
            "edition_rank",
            "authors",
            "parent_work",
            "shelves",
            "connector",
            "search_vector",
            "links",
            "file_links",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"aria-describedby": "desc_title"}),
            "subtitle": forms.TextInput(attrs={"aria-describedby": "desc_subtitle"}),
            "description": forms.Textarea(
                attrs={"aria-describedby": "desc_description"}
            ),
            "series": forms.TextInput(attrs={"aria-describedby": "desc_series"}),
            "series_number": forms.TextInput(
                attrs={"aria-describedby": "desc_series_number"}
            ),
            "subjects": ArrayWidget(),
            "languages": forms.TextInput(
                attrs={"aria-describedby": "desc_languages_help desc_languages"}
            ),
            "publishers": forms.TextInput(
                attrs={"aria-describedby": "desc_publishers_help desc_publishers"}
            ),
            "first_published_date": SelectDateWidget(
                attrs={"aria-describedby": "desc_first_published_date"}
            ),
            "published_date": SelectDateWidget(
                attrs={"aria-describedby": "desc_published_date"}
            ),
            "cover": ClearableFileInputWithWarning(
                attrs={"aria-describedby": "desc_cover"}
            ),
            "physical_format": Select(
                attrs={"aria-describedby": "desc_physical_format"}
            ),
            "physical_format_detail": forms.TextInput(
                attrs={"aria-describedby": "desc_physical_format_detail"}
            ),
            "pages": forms.NumberInput(attrs={"aria-describedby": "desc_pages"}),
            "isbn_13": forms.TextInput(attrs={"aria-describedby": "desc_isbn_13"}),
            "isbn_10": forms.TextInput(attrs={"aria-describedby": "desc_isbn_10"}),
            "openlibrary_key": forms.TextInput(
                attrs={"aria-describedby": "desc_openlibrary_key"}
            ),
            "inventaire_id": forms.TextInput(
                attrs={"aria-describedby": "desc_inventaire_id"}
            ),
            "oclc_number": forms.TextInput(
                attrs={"aria-describedby": "desc_oclc_number"}
            ),
            "ASIN": forms.TextInput(attrs={"aria-describedby": "desc_ASIN"}),
        }


class EditionFromWorkForm(CustomForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # make all fields hidden
        for visible in self.visible_fields():
            visible.field.widget = forms.HiddenInput()

    class Meta:
        model = models.Work
        fields = [
            "title",
            "subtitle",
            "authors",
            "description",
            "languages",
            "series",
            "series_number",
            "subjects",
            "subject_places",
            "cover",
            "first_published_date",
        ]
