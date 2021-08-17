""" the good stuff! the books! """
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from .helpers import is_api_request


# pylint: disable=no-self-use
class Editions(View):
    """list of editions"""

    def get(self, request, book_id):
        """list of editions of a book"""
        work = get_object_or_404(models.Work, id=book_id)

        if is_api_request(request):
            return ActivitypubResponse(work.to_edition_list(**request.GET))
        filters = {}

        if request.GET.get("language"):
            filters["languages__contains"] = [request.GET.get("language")]
        if request.GET.get("format"):
            filters["physical_format__iexact"] = request.GET.get("format")

        editions = work.editions.order_by("-edition_rank")
        languages = set(sum([e.languages for e in editions], []))

        paginated = Paginator(editions.filter(**filters), PAGE_LENGTH)
        data = {
            "editions": paginated.get_page(request.GET.get("page")),
            "work": work,
            "languages": languages,
            "formats": set(
                e.physical_format.lower() for e in editions if e.physical_format
            ),
        }
        return TemplateResponse(request, "book/editions.html", data)


@login_required
@require_POST
@transaction.atomic
def switch_edition(request):
    """switch your copy of a book to a different edition"""
    edition_id = request.POST.get("edition")
    new_edition = get_object_or_404(models.Edition, id=edition_id)
    shelfbooks = models.ShelfBook.objects.filter(
        book__parent_work=new_edition.parent_work, shelf__user=request.user
    )
    for shelfbook in shelfbooks.all():
        with transaction.atomic():
            models.ShelfBook.objects.create(
                created_date=shelfbook.created_date,
                user=shelfbook.user,
                shelf=shelfbook.shelf,
                book=new_edition,
            )
            shelfbook.delete()

    readthroughs = models.ReadThrough.objects.filter(
        book__parent_work=new_edition.parent_work, user=request.user
    )
    for readthrough in readthroughs.all():
        readthrough.book = new_edition
        readthrough.save()

    return redirect("/book/%d" % new_edition.id)
