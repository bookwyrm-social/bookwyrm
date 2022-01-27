""" book list views"""
from django.core.paginator import Paginator
from django.db.models import Avg, DecimalField
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt

from bookwyrm import models
from bookwyrm.settings import PAGE_LENGTH


# pylint: disable=no-self-use
class EmbedList(View):
    """embeded book list page"""

    def get(self, request, list_id, list_key):
        """display a book list"""
        book_list = get_object_or_404(models.List, id=list_id)

        embed_key = str(book_list.embed_key.hex)

        if list_key != embed_key:
            raise Http404()

        # sort_by shall be "order" unless a valid alternative is given
        sort_by = request.GET.get("sort_by", "order")
        if sort_by not in ("order", "title", "rating"):
            sort_by = "order"

        # direction shall be "ascending" unless a valid alternative is given
        direction = request.GET.get("direction", "ascending")
        if direction not in ("ascending", "descending"):
            direction = "ascending"

        directional_sort_by = {
            "order": "order",
            "title": "book__title",
            "rating": "average_rating",
        }[sort_by]
        if direction == "descending":
            directional_sort_by = "-" + directional_sort_by

        items = book_list.listitem_set.prefetch_related("user", "book", "book__authors")
        if sort_by == "rating":
            items = items.annotate(
                average_rating=Avg(
                    Coalesce("book__review__rating", 0.0),
                    output_field=DecimalField(),
                )
            )
        items = items.filter(approved=True).order_by(directional_sort_by)

        paginated = Paginator(items, PAGE_LENGTH)

        page = paginated.get_page(request.GET.get("page"))

        data = {
            "list": book_list,
            "items": page,
            "page_range": paginated.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
        }
        return TemplateResponse(request, "lists/embed-list.html", data)


@xframe_options_exempt
def unsafe_embed_list(request, *args, **kwargs):
    """allows the EmbedList view to be loaded through unsafe iframe origins"""

    embed_list_view = EmbedList.as_view()
    return embed_list_view(request, *args, **kwargs)
