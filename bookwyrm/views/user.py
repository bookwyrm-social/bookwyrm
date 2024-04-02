""" The user profile """
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST

from bookwyrm import models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH, INSTANCE_ACTOR_USERNAME
from .helpers import get_user_from_username, is_api_request


# pylint: disable=no-self-use
class User(View):
    """user profile page"""

    def get(self, request, username):
        """profile page for a user"""
        user = get_user_from_username(request.user, username)

        if not user.local and not request.user.is_authenticated:
            return redirect(user.remote_id)

        if is_api_request(request):
            # we have a json request
            return ActivitypubResponse(user.to_activity())
        # otherwise we're at a UI view

        # if it's not an API request, never show the instance actor profile page
        if user.localname == INSTANCE_ACTOR_USERNAME:
            raise Http404()

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
            .exclude(
                privacy="direct",
                review__isnull=True,
                comment__isnull=True,
                quotation__isnull=True,
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


class UserReviewsComments(View):
    """user's activity filtered by reviews and comments"""

    def get(self, request, username):
        """user's activity filtered by reviews and comments"""
        user = get_user_from_username(request.user, username)
        is_self = request.user.id == user.id

        activities = (
            models.Status.privacy_filter(
                request.user,
            )
            .filter(
                Q(review__isnull=False) | Q(comment__isnull=False),
                user=user,
            )
            .exclude(
                privacy="direct",
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
            "user": user,
            "is_self": is_self,
            "activities": paginated.get_page(request.GET.get("page", 1)),
        }
        return TemplateResponse(request, "user/reviews_comments.html", data)


@require_POST
@login_required
def hide_suggestions(request):
    """not everyone wants user suggestions"""
    request.user.show_suggested_users = False
    request.user.save(broadcast=False, update_fields=["show_suggested_users"])
    return redirect("/")


# pylint: disable=unused-argument
def user_redirect(request, username):
    """redirect to a user's feed"""
    return redirect("user-feed", username=username)


@login_required
def toggle_guided_tour(request, tour):
    """most people don't want a tour every time they load a page"""

    request.user.show_guided_tour = tour
    request.user.save(broadcast=False, update_fields=["show_guided_tour"])
    return redirect("/")
