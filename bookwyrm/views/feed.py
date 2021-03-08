""" non-interactive pages """
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseNotFound
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View

from bookwyrm import forms, models
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH
from .helpers import get_activity_feed, get_user_from_username
from .helpers import is_api_request, is_bookwyrm_request, object_visible_to_user


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Feed(View):
    """ activity stream """

    def get(self, request, tab):
        """ user's homepage with activity feed """
        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1

        if tab == "home":
            activities = get_activity_feed(request.user, following_only=True)
            tab_title = _("Home")
        elif tab == "local":
            activities = get_activity_feed(
                request.user, privacy=["public", "followers"], local_only=True
            )
            tab_title = _("Local")
        else:
            activities = get_activity_feed(
                request.user, privacy=["public", "followers"]
            )
            tab_title = _("Federated")
        paginated = Paginator(activities, PAGE_LENGTH)

        data = {
            **feed_page_data(request.user),
            **{
                "user": request.user,
                "activities": paginated.page(page),
                "tab": tab,
                "tab_title": tab_title,
                "goal_form": forms.GoalForm(),
                "path": "/%s" % tab,
            },
        }
        return TemplateResponse(request, "feed/feed.html", data)


@method_decorator(login_required, name="dispatch")
class DirectMessage(View):
    """ dm view """

    def get(self, request, username=None):
        """ like a feed but for dms only """
        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1

        queryset = models.Status.objects

        user = None
        if username:
            try:
                user = get_user_from_username(request.user, username)
            except models.User.DoesNotExist:
                pass
        if user:
            queryset = queryset.filter(Q(user=user) | Q(mention_users=user))

        activities = get_activity_feed(
            request.user, privacy=["direct"], queryset=queryset
        )

        paginated = Paginator(activities, PAGE_LENGTH)
        activity_page = paginated.page(page)
        data = {
            **feed_page_data(request.user),
            **{
                "user": request.user,
                "partner": user,
                "activities": activity_page,
                "path": "/direct-messages",
            },
        }
        return TemplateResponse(request, "feed/direct_messages.html", data)


class Status(View):
    """ get posting """

    def get(self, request, username, status_id):
        """ display a particular status (and replies, etc) """
        try:
            user = get_user_from_username(request.user, username)
            status = models.Status.objects.select_subclasses().get(
                id=status_id, deleted=False
            )
        except ValueError:
            return HttpResponseNotFound()

        # the url should have the poster's username in it
        if user != status.user:
            return HttpResponseNotFound()

        # make sure the user is authorized to see the status
        if not object_visible_to_user(request.user, status):
            return HttpResponseNotFound()

        if is_api_request(request):
            return ActivitypubResponse(
                status.to_activity(pure=not is_bookwyrm_request(request))
            )

        data = {
            **feed_page_data(request.user),
            **{
                "status": status,
            },
        }
        return TemplateResponse(request, "feed/status.html", data)


class Replies(View):
    """ replies page (a json view of status) """

    def get(self, request, username, status_id):
        """ ordered collection of replies to a status """
        # the html view is the same as Status
        if not is_api_request(request):
            status_view = Status.as_view()
            return status_view(request, username, status_id)

        # the json view is different than Status
        status = models.Status.objects.get(id=status_id)
        if status.user.localname != username:
            return HttpResponseNotFound()

        return ActivitypubResponse(status.to_replies(**request.GET))


def feed_page_data(user):
    """ info we need for every feed page """
    if not user.is_authenticated:
        return {}

    goal = models.AnnualGoal.objects.filter(user=user, year=timezone.now().year).first()
    return {
        "suggested_books": get_suggested_books(user),
        "goal": goal,
        "goal_form": forms.GoalForm(),
    }


def get_suggested_books(user, max_books=5):
    """ helper to get a user's recent books """
    book_count = 0
    preset_shelves = [("reading", max_books), ("read", 2), ("to-read", max_books)]
    suggested_books = []
    for (preset, shelf_max) in preset_shelves:
        limit = (
            shelf_max
            if shelf_max < (max_books - book_count)
            else max_books - book_count
        )
        shelf = user.shelf_set.get(identifier=preset)

        shelf_books = shelf.shelfbook_set.order_by("-updated_date").all()[:limit]
        if not shelf_books:
            continue
        shelf_preview = {
            "name": shelf.name,
            "identifier": shelf.identifier,
            "books": [s.book for s in shelf_books],
        }
        suggested_books.append(shelf_preview)
        book_count += len(shelf_preview["books"])
    return suggested_books
