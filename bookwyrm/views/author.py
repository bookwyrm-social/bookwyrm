""" the good people stuff! the authors! """
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from .helpers import is_api_request


# pylint: disable= no-self-use
class Author(View):
    """this person wrote a book"""

    def get(self, request, author_id):
        """landing page for an author"""
        author = get_object_or_404(models.Author, id=author_id)

        if is_api_request(request):
            return ActivitypubResponse(author.to_activity())

        books = models.Work.objects.filter(
            Q(authors=author) | Q(editions__authors=author)
        ).distinct()
        data = {
            "author": author,
            "books": [b.default_edition for b in books],
        }
        return TemplateResponse(request, "author/author.html", data)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_book", raise_exception=True), name="dispatch"
)
class EditAuthor(View):
    """edit author info"""

    def get(self, request, author_id):
        """info about a book"""
        author = get_object_or_404(models.Author, id=author_id)
        data = {"author": author, "form": forms.AuthorForm(instance=author)}
        return TemplateResponse(request, "author/edit_author.html", data)

    def post(self, request, author_id):
        """edit a author cool"""
        author = get_object_or_404(models.Author, id=author_id)

        form = forms.AuthorForm(request.POST, request.FILES, instance=author)
        if not form.is_valid():
            data = {"author": author, "form": form}
            return TemplateResponse(request, "author/edit_author.html", data)
        author = form.save()

        return redirect("/author/%s" % author.id)
