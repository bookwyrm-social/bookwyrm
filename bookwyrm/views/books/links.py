""" the good stuff! the books! """
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.utils.decorators import method_decorator

from bookwyrm import forms, models


# pylint: disable=no-self-use
class BookFileLinks(View):
    """View all links"""

    def get(self, request, book_id):
        """view links"""
        book = get_object_or_404(models.Edition, id=book_id)
        return TemplateResponse(
            request, "book/file_links/edit_links.html", {"book": book}
        )

    def post(self, request, book_id, link_id):
        """delete link"""
        link = get_object_or_404(models.FileLink, id=link_id, book=book_id)
        link.delete()
        return self.get(request, book_id)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_book", raise_exception=True), name="dispatch"
)
class AddFileLink(View):
    """a book! this is the stuff"""

    def get(self, request, book_id):
        """Create link form"""
        book = get_object_or_404(models.Edition, id=book_id)
        data = {
            "file_link_form": forms.FileLinkForm(),
            "book": book,
        }
        return TemplateResponse(request, "book/file_links/file_link_page.html", data)

    @transaction.atomic
    def post(self, request, book_id, link_id=None):
        """Add a link to a copy of the book you can read"""
        book = get_object_or_404(models.Book.objects.select_subclasses(), id=book_id)
        link = get_object_or_404(models.FileLink, id=link_id) if link_id else None
        form = forms.FileLinkForm(request.POST, instance=link)
        if not form.is_valid():
            data = {"file_link_form": form, "book": book}
            return TemplateResponse(
                request, "book/file_links/file_link_page.html", data
            )

        link = form.save()
        book.file_links.add(link)
        book.last_edited_by = request.user
        book.save()
        return redirect("book", book.id)
