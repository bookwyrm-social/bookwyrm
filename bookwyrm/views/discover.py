""" What's up locally """
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import activitystreams


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Discover(View):
    """preview of recently reviewed books"""

    def get(self, request):
        """tiled book activity page"""
        # all activities in the "federated" feed associated with a book
        activities = (
            activitystreams.streams["local"]
            .get_activity_stream(request.user)
            .filter(
                Q(comment__isnull=False)
                | Q(review__isnull=False)
                | Q(quotation__isnull=False)
                | Q(mention_books__isnull=False)
            )
        )

        large_activities = Paginator(
            activities.filter(mention_books__isnull=True)
            # exclude statuses with no user-provided content for large panels
            .exclude(
                Q(Q(content="") | Q(content__isnull=True)) & Q(quotation__isnull=True),
            ),
            6,
        )
        small_activities = Paginator(
            activities.filter(
                Q(mention_books__isnull=False)
                | Q(
                    Q(Q(content="") | Q(content__isnull=True))
                    & Q(quotation__isnull=True),
                )
            ),
            4,
        )

        page = request.GET.get("page")
        data = {
            "large_activities": large_activities.get_page(page),
            "small_activities": small_activities.get_page(page),
        }
        return TemplateResponse(request, "discover/discover.html", data)
