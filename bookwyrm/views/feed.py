""" non-interactive pages """
from datetime import date
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseNotFound, Http404
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm import activitystreams, forms, models
from bookwyrm.models.user import FeedFilterChoices
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.settings import PAGE_LENGTH, STREAMS
from bookwyrm.suggested_users import suggested_users
from .helpers import filter_stream_by_status_type, get_user_from_username
from .helpers import is_api_request, is_bookwyrm_request, maybe_redirect_local_path
from .annual_summary import get_annual_summary_year


# pylint: disable= no-self-use
@method_decorator(login_required, name="dispatch")
class Feed(View):
    """activity stream"""

    def post(self, request, tab):
        """save feed settings form, with a silent validation fail"""
        filters_applied = False
        form = forms.FeedStatusTypesForm(request.POST, instance=request.user)
        if form.is_valid():
            # workaround to avoid broadcasting this change
            user = form.save(request, commit=False)
            user.save(broadcast=False, update_fields=["feed_status_types"])
            filters_applied = True

        return self.get(request, tab, filters_applied)

    def get(self, request, tab, filters_applied=False):
        """user's homepage with activity feed"""
        tab = [s for s in STREAMS if s["key"] == tab]
        tab = tab[0] if tab else STREAMS[0]

        activities = activitystreams.streams[tab["key"]].get_activity_stream(
            request.user
        )
        filtered_activities = filter_stream_by_status_type(
            activities,
            allowed_types=request.user.feed_status_types,
        )
        paginated = Paginator(filtered_activities, PAGE_LENGTH)

        suggestions = suggested_users.get_suggestions(request.user)

        cutoff = (
            date(get_annual_summary_year(), 12, 31)
            if get_annual_summary_year()
            else None
        )
        readthroughs = (
            models.ReadThrough.objects.filter(
                user=request.user, finish_date__lte=cutoff
            )
            if get_annual_summary_year()
            else []
        )

        data = {
            **feed_page_data(request.user),
            **{
                "user": request.user,
                "activities": paginated.get_page(request.GET.get("page")),
                "suggested_users": suggestions,
                "tab": tab,
                "streams": STREAMS,
                "goal_form": forms.GoalForm(),
                "feed_status_types_options": FeedFilterChoices,
                "filters_applied": filters_applied,
                "path": f"/{tab['key']}",
                "annual_summary_year": get_annual_summary_year(),
                "has_tour": True,
                "has_summary_read_throughs": len(readthroughs),
            },
        }
        return TemplateResponse(request, "feed/feed.html", data)


@method_decorator(login_required, name="dispatch")
class DirectMessage(View):
    """dm view"""

    def get(self, request, username=None):
        """like a feed but for dms only"""
        # remove fancy subclasses of status, keep just good ol' notes
        activities = (
            models.Status.privacy_filter(request.user, privacy_levels=["direct"])
            .filter(
                review__isnull=True,
                comment__isnull=True,
                quotation__isnull=True,
                generatednote__isnull=True,
            )
            .order_by("-published_date")
        )

        user = None
        if username:
            try:
                user = get_user_from_username(request.user, username)
            except Http404:
                pass
        if user:
            activities = activities.filter(Q(user=user) | Q(mention_users=user))

        paginated = Paginator(activities, PAGE_LENGTH)
        data = {
            **feed_page_data(request.user),
            **{
                "user": request.user,
                "partner": user,
                "activities": paginated.get_page(request.GET.get("page")),
                "path": "/direct-messages",
            },
        }
        return TemplateResponse(request, "feed/direct_messages.html", data)


class Status(View):
    """get posting"""

    # pylint: disable=unused-argument
    def get(self, request, username, status_id, slug=None):
        """display a particular status (and replies, etc)"""
        user = get_user_from_username(request.user, username)
        status = get_object_or_404(
            models.Status.objects.select_subclasses(),
            user=user,
            id=status_id,
            deleted=False,
        )
        # make sure the user is authorized to see the status
        status.raise_visible_to_user(request.user)

        if is_api_request(request):
            return ActivitypubResponse(
                status.to_activity(pure=not is_bookwyrm_request(request))
            )

        if redirect_local_path := maybe_redirect_local_path(request, status):
            return redirect_local_path

        visible_thread = (
            models.Status.privacy_filter(request.user)
            .filter(thread_id=status.thread_id)
            .values_list("id", flat=True)
        )
        visible_thread = list(visible_thread)

        ancestors = models.Status.objects.select_subclasses().raw(
            """
            WITH RECURSIVE get_thread(depth, id, path) AS (

                SELECT 1, st.id, ARRAY[st.id]
                FROM bookwyrm_status st
                WHERE id = '%s' AND id = ANY(%s)

                UNION

                SELECT (gt.depth + 1), st.reply_parent_id, path || st.id
                FROM get_thread gt, bookwyrm_status st

                WHERE st.id = gt.id AND depth < 5 AND st.id = ANY(%s)

            )

            SELECT * FROM get_thread ORDER BY path DESC;
        """,
            params=[status.reply_parent_id or 0, visible_thread, visible_thread],
        )
        children = models.Status.objects.select_subclasses().raw(
            """
            WITH RECURSIVE get_thread(depth, id, path) AS (

                SELECT 1, st.id, ARRAY[st.id]
                FROM bookwyrm_status st
                WHERE reply_parent_id = '%s' AND id = ANY(%s)

                UNION

                SELECT (gt.depth + 1), st.id, path || st.id
                FROM get_thread gt, bookwyrm_status st

                WHERE st.reply_parent_id = gt.id AND depth < 5 AND st.id = ANY(%s)

            )

            SELECT * FROM get_thread ORDER BY path;
        """,
            params=[status.id, visible_thread, visible_thread],
        )

        preview = None
        if hasattr(status, "book"):
            preview = status.book.preview_image
        elif status.mention_books.exists():
            preview = status.mention_books.first().preview_image

        data = {
            **feed_page_data(request.user),
            **{
                "status": status,
                "children": children,
                "ancestors": ancestors,
                "preview": preview,
            },
        }
        return TemplateResponse(request, "feed/status.html", data)


class Replies(View):
    """replies page (a json view of status)"""

    def get(self, request, username, status_id):
        """ordered collection of replies to a status"""
        # the html view is the same as Status
        if not is_api_request(request):
            status_view = Status.as_view()
            return status_view(request, username, status_id)

        # the json view is different than Status
        status = models.Status.objects.get(id=status_id)
        if status.user.localname != username:
            return HttpResponseNotFound()
        status.raise_visible_to_user(request.user)

        return ActivitypubResponse(status.to_replies(**request.GET))


def feed_page_data(user):
    """info we need for every feed page"""
    if not user.is_authenticated:
        return {}

    goal = models.AnnualGoal.objects.filter(user=user, year=timezone.now().year).first()
    return {
        "goal": goal,
        "goal_form": forms.GoalForm(),
    }


def get_suggested_books(user, max_books=5):
    """helper to get a user's recent books"""
    book_count = 0
    preset_shelves = {"reading": max_books, "read": 2, "to-read": max_books}
    suggested_books = []

    user_shelves = {
        shelf.identifier: shelf
        for shelf in user.shelf_set.filter(
            identifier__in=preset_shelves.keys()
        ).exclude(books__isnull=True)
    }

    for preset, shelf_max in preset_shelves.items():
        limit = (
            shelf_max
            if shelf_max < (max_books - book_count)
            else max_books - book_count
        )
        shelf = user_shelves.get(preset, None)
        if not shelf:
            continue

        shelf_preview = {
            "name": shelf.name,
            "identifier": shelf.identifier,
            "books": models.Edition.viewer_aware_objects(user)
            .filter(
                shelfbook__shelf=shelf,
            )
            .order_by("-shelfbook__shelved_date")
            .prefetch_related("authors")[:limit],
        }
        suggested_books.append(shelf_preview)
        book_count += len(shelf_preview["books"])
    return suggested_books
