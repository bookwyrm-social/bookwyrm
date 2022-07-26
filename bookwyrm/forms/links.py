""" using django model forms """
from urllib.parse import urlparse

from django.utils.translation import gettext_lazy as _

from bookwyrm import models
from .custom_form import CustomForm


# pylint: disable=missing-class-docstring
class LinkDomainForm(CustomForm):
    class Meta:
        model = models.LinkDomain
        fields = ["name"]


class FileLinkForm(CustomForm):
    class Meta:
        model = models.FileLink
        fields = ["url", "filetype", "availability", "book", "added_by"]

    def clean(self):
        """make sure the domain isn't blocked or pending"""
        cleaned_data = super().clean()
        url = cleaned_data.get("url")
        filetype = cleaned_data.get("filetype")
        book = cleaned_data.get("book")
        domain = urlparse(url).netloc
        if models.LinkDomain.objects.filter(domain=domain).exists():
            status = models.LinkDomain.objects.get(domain=domain).status
            if status == "blocked":
                # pylint: disable=line-too-long
                self.add_error(
                    "url",
                    _(
                        "This domain is blocked. Please contact your administrator if you think this is an error."
                    ),
                )
            elif models.FileLink.objects.filter(
                url=url, book=book, filetype=filetype
            ).exists():
                # pylint: disable=line-too-long
                self.add_error(
                    "url",
                    _(
                        "This link with file type has already been added for this book. If it is not visible, the domain is still pending."
                    ),
                )
