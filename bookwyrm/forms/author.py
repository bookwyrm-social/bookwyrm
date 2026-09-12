"""using django model forms"""

from bookwyrm import models
from .custom_form import CustomForm
from .widgets import SelectDateWidget


class AuthorForm(CustomForm):
    class Meta:
        model = models.Author
        fields = [
            "last_edited_by",
            "name",
            "aliases",
            "bio",
            "wikipedia_link",
            "wikidata",
            "website",
            "born",
            "died",
            "openlibrary_key",
            "inventaire_id",
            "librarything_key",
            "goodreads_key",
            "isfdb",
            "isni",
            "bnf_id",
            "viaf",
        ]
        widgets = {
            "born": SelectDateWidget(),
            "died": SelectDateWidget(),
        }
