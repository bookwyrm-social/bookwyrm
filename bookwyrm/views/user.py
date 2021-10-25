""" non-interactive pages """
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
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

        # only show other shelves that should be visible
        shelves = user.shelf_set
        is_self = request.user.id == user.id
        if not is_self:
            follower = user.followers.filter(id=request.user.id).exists()
            if follower:
                shelves = shelves.filter(privacy__in=["public", "followers"])
            else:
                shelves = shelves.filter(privacy="public")

        for user_shelf in shelves.all():
            if not user_shelf.books.count():
                continue
            shelf_preview.append(
                {
                    "name": user_shelf.name,
                    "local_path": user_shelf.local_path,
                    "books": user_shelf.books.all()[:3],
                    "size": user_shelf.books.count(),
                }
            )
            if len(shelf_preview) > 2:
                break

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

        paginated = Paginator(
            user.followers.order_by("-created_date").all(), PAGE_LENGTH
        )
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

        paginated = Paginator(
            user.following.order_by("-created_date").all(), PAGE_LENGTH
        )
        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "follow_list": paginated.get_page(request.GET.get("page")),
        }
        return TemplateResponse(request, "user/relationships/following.html", data)


class Groups(View):
    """list of user's groups view"""

    def get(self, request, username):
        """list of groups"""
        user = get_user_from_username(request.user, username)

        paginated = Paginator(
            models.Group.memberships.filter(user=user).order_by("-created_date"),
            PAGE_LENGTH,
        )
        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "group_list": paginated.get_page(request.GET.get("page")),
        }
        return TemplateResponse(request, "user/groups.html", data)


@require_POST
@login_required
def hide_suggestions(request):
    """not everyone wants user suggestions"""
    request.user.show_suggested_users = False
    request.user.save(broadcast=False, update_fields=["show_suggested_users"])
    return redirect(request.headers.get("Referer", "/"))
