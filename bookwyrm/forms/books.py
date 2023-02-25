""" using django model forms """
import copy

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
    def __init__(self, data=None, files=None, instance=None):
        # very ugly for now, but essentially does:
        # - when data is not None we handle a form submit.
        #   This is where we can swoop in and check which day/month/year form fields are set,
        #   set the precision, and set the default value of "1" to the missing day/month fields.
        #
        # - when data is None but instance is not None we handle a form render.
        #   This is where we intercept and change the value date value we send to the widget,
        #   if the precision is "year" we override the value for the date with "{year}-0-0",
        #   and same for precision "month". This will make the widget render the default "not selected"
        #   values for those fields. If the precision is "day" we just let the widget handle the
        #   date as an actual datetime.date

        initial = {}
        # when data present we handle a submitted form
        if data:
            data = copy.deepcopy(data)
            first_published_date_precision = None
            if data.get("first_published_date_day") != "":
                first_published_date_precision = "day"
            elif data.get("first_published_date_month") != "":
                data["first_published_date_day"] = "1"
                first_published_date_precision = "month"
            elif data.get("first_published_date_year") != "":
                data["first_published_date_day"] = "1"
                data["first_published_date_month"] = "1"
                first_published_date_precision = "year"
            data["first_published_date_precision"] = first_published_date_precision

            published_date_precision = None
            if data.get("published_date_day") != "":
                published_date_precision = "day"
            elif data.get("published_date_month") != "":
                data["published_date_day"] = "1"
                published_date_precision = "month"
            elif data.get("published_date_year") != "":
                data["published_date_day"] = "1"
                data["published_date_month"] = "1"
                published_date_precision = "year"
            data["published_date_precision"] = published_date_precision
        # when data not present and instance is not None, handle displaying a form
        elif instance is not None:
            if instance.first_published_date_precision == "year":
                initial["first_published_date"] = f"{instance.first_published_date.year}-0-0"
            elif instance.first_published_date_precision == "month":
                initial["first_published_date"] = f"{instance.first_published_date.year}-{instance.first_published_date.month}-0"

            if instance.published_date_precision == "year":
                initial["published_date"] = f"{instance.published_date.year}-0-0"
            elif instance.published_date_precision == "month":
                initial["published_date"] = f"{instance.published_date.year}-{instance.published_date.month}-0"

        super().__init__(data=data, files=files, initial=initial, instance=instance)
        self.data

    class Meta:
        model = models.Edition
        fields = [
            "title",
            "subtitle",
            "description",
            "series",
            "series_number",
            "languages",
            "subjects",
            "publishers",
            "first_published_date",
            "first_published_date_precision",
            "first_published_loose_date",
            "published_date",
            "published_date_precision",
            "published_loose_date",
            "cover",
            "physical_format",
            "physical_format_detail",
            "pages",
            "isbn_13",
            "isbn_10",
            "openlibrary_key",
            "inventaire_id",
            "goodreads_key",
            "oclc_number",
            "asin",
            "aasin",
            "isfdb",
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
            "first_published_loose_date": SelectDateWidget(
                attrs={"aria-describedby": "desc_first_published_loose_date"}
            ),
            "published_date": SelectDateWidget(
                attrs={"aria-describedby": "desc_published_date"}
            ),
            "published_loose_date": SelectDateWidget(
                attrs={"aria-describedby": "desc_published_loose_date"}
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
            "goodreads_key": forms.TextInput(
                attrs={"aria-describedby": "desc_goodreads_key"}
            ),
            "oclc_number": forms.TextInput(
                attrs={"aria-describedby": "desc_oclc_number"}
            ),
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
