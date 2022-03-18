""" non-interactive pages """
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from .helpers import get_user_from_username, is_api_request


# pylint: disable=no-self-use
class User(View):
    """user profile page"""

    def get(self, request, username):
        """profile page for a user"""
        user = get_user_from_username(request.user, username)

        if is_api_request(request):
            # we have a json request
            return ActivitypubResponse(user.to_activity())
        # otherwise we're at a UI view

        shelf_preview = []

        # only show shelves that should be visible
        is_self = request.user.id == user.id
        if not is_self:
            shelves = (
                models.Shelf.privacy_filter(
                    request.user, privacy_levels=["public", "followers"]
                )
                .filter(user=user, books__isnull=False)
                .distinct()
            )
        else:
            shelves = user.shelf_set.filter(books__isnull=False).distinct()

        for user_shelf in shelves.all()[:3]:
            shelf_preview.append(
                {
                    "name": user_shelf.name,
                    "local_path": user_shelf.local_path,
                    "books": user_shelf.books.all()[:3],
                    "size": user_shelf.books.count(),
                }
            )

        # user's posts
        activities = (
            models.Status.privacy_filter(
                request.user,
            )
            .filter(user=user)
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
        goal = models.AnnualGoal.objects.filter(
            user=user, year=timezone.now().year
        ).first()
        if goal:
            try:
                goal.raise_visible_to_user(request.user)
            except Http404:
                goal = None

        data = {
            "user": user,
            "is_self": is_self,
            "shelves": shelf_preview,
            "shelf_count": shelves.count(),
            "activities": paginated.get_page(request.GET.get("page", 1)),
            "goal": goal,
        }

        return TemplateResponse(request, "user/user.html", data)


class Followers(View):
    """list of followers view"""

    def get(self, request, username):
        """list of followers"""
        user = get_user_from_username(request.user, username)

        if is_api_request(request):
            return ActivitypubResponse(user.to_followers_activity(**request.GET))

        if user.hide_follows:
            raise PermissionDenied()

        followers = annotate_if_follows(request.user, user.followers)
        paginated = Paginator(followers.all(), PAGE_LENGTH)
        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "follow_list": paginated.get_page(request.GET.get("page")),
        }
        return TemplateResponse(request, "user/relationships/followers.html", data)


class Following(View):
    """list of following view"""

    def get(self, request, username):
        """list of followers"""
        user = get_user_from_username(request.user, username)

        if is_api_request(request):
            return ActivitypubResponse(user.to_following_activity(**request.GET))

        if user.hide_follows:
            raise PermissionDenied()

        following = annotate_if_follows(request.user, user.following)
        paginated = Paginator(following.all(), PAGE_LENGTH)
        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "follow_list": paginated.get_page(request.GET.get("page")),
        }
        return TemplateResponse(request, "user/relationships/following.html", data)


def annotate_if_follows(user, queryset):
    """Sort a list of users by if you follow them"""
    if not user.is_authenticated:
        return queryset.order_by("-created_date")

    return queryset.annotate(
        request_user_follows=Count("followers", filter=Q(followers=user))
    ).order_by("-request_user_follows", "-created_date")


@require_POST
@login_required
def hide_suggestions(request):
    """not everyone wants user suggestions"""
    request.user.show_suggested_users = False
    request.user.save(broadcast=False, update_fields=["show_suggested_users"])
    return redirect(request.headers.get("Referer", "/"))


# pylint: disable=unused-argument
def user_redirect(request, username):
    """redirect to a user's feed"""
    return redirect("user-feed", username=username)
