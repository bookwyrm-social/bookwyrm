""" listing statuses for a given hashtag """
from django.core.paginator import Paginator
from django.db.models import Q
from django.views import View
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from bookwyrm import models
from bookwyrm.settings import PAGE_LENGTH
from bookwyrm.views.helpers import maybe_redirect_local_path


# pylint: disable= no-self-use
class Hashtag(View):
    """listing statuses for a given hashtag"""

    # pylint: disable=unused-argument
    def get(self, request, hashtag_id, slug=None):
        """show hashtag with related statuses"""
        hashtag = get_object_or_404(models.Hashtag, id=hashtag_id)

        if redirect_local_path := maybe_redirect_local_path(request, hashtag):
            return redirect_local_path

        activities = (
            models.Status.privacy_filter(
                request.user,
            )
            .filter(
                Q(mention_hashtags=hashtag),
            )
            .exclude(
                privacy__in=["direct", "unlisted"],
            )
            .select_related(
                "user",
                "reply_parent",
                "review__book",
                "comment__book",
                "quotation__book",
            )
            .prefetch_related(
                "mention_books",
                "mention_users",
                "attachments",
            )
        )
        paginated = Paginator(activities, PAGE_LENGTH)

        data = {
            "hashtag": hashtag.name,
            "activities": paginated.get_page(request.GET.get("page", 1)),
        }
        return TemplateResponse(request, "hashtag.html", data)
