""" the good people stuff! the authors! """
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.connectors import connector_manager
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.views.helpers import is_api_request, maybe_redirect_local_path


# pylint: disable= no-self-use
class Author(View):
    """this person wrote a book"""

    # pylint: disable=unused-argument
    def get(self, request, author_id, slug=None):
        """landing page for an author"""
        author = get_object_or_404(models.Author, id=author_id)

        if is_api_request(request):
            return ActivitypubResponse(author.to_activity())

        if redirect_local_path := maybe_redirect_local_path(request, author):
            return redirect_local_path

        books = (
            models.Work.objects.filter(editions__authors=author)
            .order_by("created_date")
            .distinct()
        )

        paginated = Paginator(books, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "author": author,
            "books": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
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

        return redirect(f"/author/{author.id}")


@login_required
@require_POST
@permission_required("bookwyrm.edit_book", raise_exception=True)
# pylint: disable=unused-argument
def update_author_from_remote(request, author_id, connector_identifier):
    """load the remote data for this author"""
    connector = connector_manager.load_connector(
        get_object_or_404(models.Connector, identifier=connector_identifier)
    )
    author = get_object_or_404(models.Author, id=author_id)

    connector.update_author_from_remote(author)

    return redirect("author", author.id)
