""" the good stuff! the books! """
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from bookwyrm import forms, models


# pylint: disable=no-self-use
@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_book", raise_exception=True), name="dispatch"
)
class BookFileLinks(View):
    """View all links"""

    def get(self, request, book_id):
        """view links"""
        book = get_object_or_404(models.Edition, id=book_id)
        annotated_links = get_annotated_links(book)

        data = {"book": book, "links": annotated_links}
        return TemplateResponse(request, "book/file_links/edit_links.html", data)

    def post(self, request, book_id, link_id):
        """Edit a link"""
        link = get_object_or_404(models.FileLink, id=link_id, book=book_id)
        form = forms.FileLinkForm(request.POST, instance=link)
        if form.is_valid():
            form.save(request)
            return redirect("file-link", book_id)

        # this form shouldn't ever really get here, since it's just a dropdown
        # get the data again rather than redirecting
        book = get_object_or_404(models.Edition, id=book_id)
        annotated_links = get_annotated_links(book, form=form)

        data = {"book": book, "links": annotated_links}
        return TemplateResponse(request, "book/file_links/edit_links.html", data)


def get_annotated_links(book, form=None):
    """The links for this book, plus the forms to edit those links"""
    links = book.file_links.order_by("domain__status", "created_date")
    annotated_links = []
    for link in links.all():
        if form and link.id == form.instance.id:
            link.form = form
        else:
            link.form = forms.FileLinkForm(instance=link)
        annotated_links.append(link)
    return annotated_links


@require_POST
@login_required
# pylint: disable=unused-argument
def delete_link(request, book_id, link_id):
    """delete link"""
    link = get_object_or_404(models.FileLink, id=link_id, book=book_id)
    link.delete()
    return redirect("file-link", book_id)


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

        link = form.save(request)
        book.file_links.add(link)
        book.last_edited_by = request.user
        book.save()
        return redirect("book", book.id)
