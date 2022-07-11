""" Following and followers lists """
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.template.response import TemplateResponse
from django.views import View

from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from .helpers import get_user_from_username, is_api_request


# pylint: disable=no-self-use
class Relationships(View):
    """list of followers/following view"""

    def get(self, request, username, direction):
        """list of followers"""
        user = get_user_from_username(request.user, username)

        if is_api_request(request):
            if direction == "followers":
                return ActivitypubResponse(user.to_followers_activity(**request.GET))
            return ActivitypubResponse(user.to_following_activity(**request.GET))

        if user.hide_follows and user != request.user:
            raise PermissionDenied()

        annotation_queryset = (
            user.followers if direction == "followers" else user.following
        )
        follows = annotate_if_follows(request.user, annotation_queryset)

        paginated = Paginator(follows.all(), PAGE_LENGTH)
        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "follow_list": paginated.get_page(request.GET.get("page")),
        }
        return TemplateResponse(request, f"user/relationships/{direction}.html", data)


def annotate_if_follows(user, queryset):
    """Sort a list of users by if you follow them"""
    if not user.is_authenticated:
        return queryset.order_by("-created_date")

    return queryset.annotate(
        request_user_follows=Count("followers", filter=Q(followers=user))
    ).order_by("-request_user_follows", "-created_date")
