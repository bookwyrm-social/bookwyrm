""" using django model forms """

from django import forms

from file_resubmit.widgets import ResubmitImageWidget

from bookwyrm import models
from bookwyrm.settings import DATA_UPLOAD_MAX_MEMORY_SIZE
from .custom_form import CustomForm
from .widgets import ArrayWidget, SelectDateWidget, Select


# pylint: disable=missing-class-docstring
class CoverForm(CustomForm):
    class Meta:
        model = models.Book
        fields = ["cover"]
        help_texts = {f: None for f in fields}


class ResubmitImageWidgetWithWarning(ResubmitImageWidget):
    """Define template to use that shows warning on too big image"""

    template_name = "widgets/clearable_file_input_with_warning.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["attrs"].update(
            {
                "data-max-upload": DATA_UPLOAD_MAX_MEMORY_SIZE,
                "max_mb": DATA_UPLOAD_MAX_MEMORY_SIZE >> 20,
            }
        )
        return context


class EditionForm(CustomForm):
    class Meta:
        model = models.Edition
        fields = [
            "title",
            "sort_title",
            "subtitle",
            "description",
            "series",
            "languages",
            "subjects",
            "publishers",
            "first_published_date",
            "published_date",
            "cover",
            "physical_format",
            "physical_format_detail",
            "pages",
            "isbn_13",
            "isbn_10",
            "openlibrary_key",
            "inventaire_id",
            "goodreads_key",
            "finna_key",
            "oclc_number",
            "asin",
            "aasin",
            "isfdb",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"aria-describedby": "desc_title"}),
            "sort_title": forms.TextInput(
                attrs={"aria-describedby": "desc_sort_title"}
            ),
            "subtitle": forms.TextInput(attrs={"aria-describedby": "desc_subtitle"}),
            "description": forms.Textarea(
                attrs={"aria-describedby": "desc_description"}
            ),
            "series": forms.TextInput(attrs={"aria-describedby": "desc_series"}),
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
            "cover": ResubmitImageWidgetWithWarning(
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
            "goodreads_key": forms.TextInput(
                attrs={"aria-describedby": "desc_goodreads_key"}
            ),
            "oclc_number": forms.TextInput(
                attrs={"aria-describedby": "desc_oclc_number"}
            ),
            "finna_key": forms.TextInput(attrs={"aria-describedby": "desc_finna_key"}),
            "ASIN": forms.TextInput(attrs={"aria-describedby": "desc_ASIN"}),
            "AASIN": forms.TextInput(attrs={"aria-describedby": "desc_AASIN"}),
            "isfdb": forms.TextInput(attrs={"aria-describedby": "desc_isfdb"}),
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
            "sort_title",
            "subtitle",
            "authors",
            "description",
            "languages",
            "series",
            "subjects",
            "subject_places",
            "cover",
            "first_published_date",
        ]
