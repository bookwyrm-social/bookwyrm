"""using django model forms"""

from django.utils.translation import gettext_lazy as _

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
        help_texts = {
            "goodreads_key": _(
                'The GoodReads key for "goodreads.com/author/show/1234567.Example_Author" would be "1234567"'
            ),
            "aliases": _("Separate multiple values with commas."),
            "isni": _("About ISNI"),
            "openlibrary_key": _('Openlibrary keys for authors should end in "A"'),
            "isfdb": _("The Internet Speculative Fiction Database"),
            "bnf_id": _("Bibliothèque nationale de France"),
            "viaf": _("The Virtual International Authority File"),
        }
