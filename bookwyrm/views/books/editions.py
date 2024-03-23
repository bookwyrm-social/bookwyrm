""" the good stuff! the books! """
from functools import reduce
import operator

from django.contrib.auth.decorators import login_required
from django.core.cache import cache as django_cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.views.helpers import is_api_request


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
        languages = set(sum(editions.values_list("languages", flat=True), []))

        editions = editions.filter(**filters)

        query = request.GET.get("q")
        if query:
            searchable_array_fields = ["languages", "publishers"]
            searchable_fields = [
                "title",
                "physical_format",
                "isbn_10",
                "isbn_13",
                "oclc_number",
                "asin",
                "aasin",
                "isfdb",
            ]
            search_filter_entries = [
                {f"{f}__icontains": query} for f in searchable_fields
            ] + [{f"{f}__iexact": query} for f in searchable_array_fields]
            editions = editions.filter(
                reduce(operator.or_, (Q(**f) for f in search_filter_entries))
            )

        paginated = Paginator(editions, PAGE_LENGTH)
        page = paginated.get_page(request.GET.get("page"))
        data = {
            "editions": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "work": work,
            "work_form": forms.EditionFromWorkForm(instance=work),
            "languages": languages,
            "formats": set(
                e.physical_format.lower() for e in editions if e.physical_format
            ),
        }
        return TemplateResponse(request, "book/editions/editions.html", data)


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
                shelved_date=shelfbook.shelved_date,
            )
            shelfbook.delete()

    readthroughs = models.ReadThrough.objects.filter(
        book__parent_work=new_edition.parent_work, user=request.user
    )
    for readthrough in readthroughs.all():
        readthrough.book = new_edition
        readthrough.save()

    django_cache.delete_many(
        [
            f"active_shelf-{request.user.id}-{book_id}"
            for book_id in new_edition.parent_work.editions.values_list("id", flat=True)
        ]
    )

    reviews = models.Review.objects.filter(
        book__parent_work=new_edition.parent_work, user=request.user
    )
    for review in reviews.all():
        # because ratings are a subclass of reviews,
        # this will pick up both ratings and reviews
        review.book = new_edition
        review.save()

    return redirect(f"/book/{new_edition.id}")
