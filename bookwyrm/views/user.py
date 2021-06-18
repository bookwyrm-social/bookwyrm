""" non-interactive pages """
from django.core.paginator import Paginator
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View

from bookwyrm import models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from .helpers import get_user_from_username, is_api_request
from .helpers import privacy_filter


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
            privacy_filter(
                request.user,
                user.status_set.select_subclasses(),
            )
            .select_related("reply_parent")
            .prefetch_related("mention_books", "mention_users")
        )

        paginated = Paginator(activities, PAGE_LENGTH)
        goal = models.AnnualGoal.objects.filter(
            user=user, year=timezone.now().year
        ).first()
        if goal and not goal.visible_to_user(request.user):
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

        paginated = Paginator(user.followers.all(), PAGE_LENGTH)
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

        paginated = Paginator(user.following.all(), PAGE_LENGTH)
        data = {
            "user": user,
            "is_self": request.user.id == user.id,
            "follow_list": paginated.get_page(request.GET.get("page")),
        }
        return TemplateResponse(request, "user/relationships/following.html", data)
