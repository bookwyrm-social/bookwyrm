"""using django model forms"""

from django import forms

from file_resubmit.widgets import ResubmitImageWidget

from bookwyrm import models
from bookwyrm.settings import DATA_UPLOAD_MAX_MEMORY_SIZE
from .custom_form import CustomForm
from .widgets import ArrayWidget, SelectDateWidget, Select


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
            "series_number",
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
            "libris_key",
            "oclc_number",
            "asin",
            "aasin",
            "isfdb",
        ]
        widgets = {
            "subjects": ArrayWidget(),
            "physical_format": Select(),
            "first_published_date": SelectDateWidget(),
            "published_date": SelectDateWidget(),
            "cover": ResubmitImageWidgetWithWarning(),
        }


class WorkForm(CustomForm):
    class Meta:
        model = models.Work
        fields = [
            "title",
            "sort_title",
            "subtitle",
            "description",
            "series",
            "series_number",
            "languages",
            "subjects",
            "cover",
            "lccn",
            "openlibrary_key",
            "inventaire_id",
            "goodreads_key",
            "finna_key",
            "libris_key",
            "asin",
            "aasin",
            "isfdb",
        ]
        widgets = {
            "subjects": ArrayWidget(),
            "cover": ResubmitImageWidgetWithWarning(),
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
            "series_number",
            "subjects",
            "subject_places",
            "cover",
            "first_published_date",
        ]


class SeriesForm(CustomForm):
    class Meta:
        model = models.Series
        fields = [
            "name",
            "alternative_names",
            "inventaire_id",
            "wikidata",
            "isfdb",
        ]
