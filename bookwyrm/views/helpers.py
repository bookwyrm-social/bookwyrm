""" helper functions used in various views """
import re
from datetime import datetime
import dateutil.parser
import dateutil.tz
from dateutil.parser import ParserError

from requests import HTTPError
from django.core.exceptions import FieldError
from django.db.models import Q
from django.http import Http404

from bookwyrm import activitypub, models
from bookwyrm.connectors import ConnectorException, get_data
from bookwyrm.status import create_generated_note
from bookwyrm.utils import regex


def get_user_from_username(viewer, username):
    """helper function to resolve a localname or a username to a user"""
    if viewer.is_authenticated and viewer.localname == username:
        # that's yourself, fool
        return viewer

    # raises 404 if the user isn't found
    try:
        return models.User.viewer_aware_objects(viewer).get(localname=username)
    except models.User.DoesNotExist:
        pass

    # if the localname didn't match, try the username
    try:
        return models.User.viewer_aware_objects(viewer).get(username=username)
    except models.User.DoesNotExist:
        raise Http404()


def is_api_request(request):
    """check whether a request is asking for html or data"""
    return "json" in request.headers.get("Accept", "") or re.match(
        r".*\.json/?$", request.path
    )


def is_bookwyrm_request(request):
    """check if the request is coming from another bookwyrm instance"""
    user_agent = request.headers.get("User-Agent")
    if user_agent is None or re.search(regex.BOOKWYRM_USER_AGENT, user_agent) is None:
        return False
    return True


def privacy_filter(viewer, queryset, privacy_levels=None, following_only=False):
    """filter objects that have "user" and "privacy" fields"""
    privacy_levels = privacy_levels or ["public", "unlisted", "followers", "direct"]
    # if there'd a deleted field, exclude deleted items
    try:
        queryset = queryset.filter(deleted=False)
    except FieldError:
        pass

    # exclude blocks from both directions
    if not viewer.is_anonymous:
        blocked = models.User.objects.filter(id__in=viewer.blocks.all()).all()
        queryset = queryset.exclude(Q(user__in=blocked) | Q(user__blocks=viewer))

    # you can't see followers only or direct messages if you're not logged in
    if viewer.is_anonymous:
        privacy_levels = [p for p in privacy_levels if not p in ["followers", "direct"]]

    # filter to only privided privacy levels
    queryset = queryset.filter(privacy__in=privacy_levels)

    # only include statuses the user follows
    if following_only:
        queryset = queryset.exclude(
            ~Q(  # remove everythign except
                Q(user__in=viewer.following.all())
                | Q(user=viewer)  # user following
                | Q(mention_users=viewer)  # is self  # mentions user
            ),
        )
    # exclude followers-only statuses the user doesn't follow
    elif "followers" in privacy_levels:
        queryset = queryset.exclude(
            ~Q(  # user isn't following and it isn't their own status
                Q(user__followers=viewer) | Q(user=viewer)
            ),
            privacy="followers",  # and the status is followers only
        )

    # exclude direct messages not intended for the user
    if "direct" in privacy_levels:
        try:
            queryset = queryset.exclude(
                ~Q(Q(user=viewer) | Q(mention_users=viewer)), privacy="direct"
            )
        except FieldError:
            queryset = queryset.exclude(~Q(user=viewer), privacy="direct")

    return queryset


def handle_remote_webfinger(query):
    """webfingerin' other servers"""
    user = None

    # usernames could be @user@domain or user@domain
    if not query:
        return None

    if query[0] == "@":
        query = query[1:]

    try:
        domain = query.split("@")[1]
    except IndexError:
        return None

    try:
        user = models.User.objects.get(username__iexact=query)
    except models.User.DoesNotExist:
        url = f"https://{domain}/.well-known/webfinger?resource=acct:{query}"
        try:
            data = get_data(url)
        except (ConnectorException, HTTPError):
            return None

        for link in data.get("links"):
            if link.get("rel") == "self":
                try:
                    user = activitypub.resolve_remote_id(
                        link["href"], model=models.User
                    )
                except (KeyError, activitypub.ActivitySerializerError):
                    return None
    return user


def get_edition(book_id):
    """look up a book in the db and return an edition"""
    book = models.Book.objects.select_subclasses().get(id=book_id)
    if isinstance(book, models.Work):
        book = book.default_edition
    return book


def handle_reading_status(user, shelf, book, privacy):
    """post about a user reading a book"""
    # tell the world about this cool thing that happened
    try:
        message = {
            "to-read": "wants to read",
            "reading": "started reading",
            "read": "finished reading",
        }[shelf.identifier]
    except KeyError:
        # it's a non-standard shelf, don't worry about it
        return

    status = create_generated_note(user, message, mention_books=[book], privacy=privacy)
    status.save()


def is_blocked(viewer, user):
    """is this viewer blocked by the user?"""
    if viewer.is_authenticated and viewer in user.blocks.all():
        return True
    return False


def get_landing_books():
    """list of books for the landing page"""

    return list(
        set(
            models.Edition.objects.filter(
                review__published_date__isnull=False,
                review__deleted=False,
                review__user__local=True,
                review__privacy__in=["public", "unlisted"],
            )
            .exclude(cover__exact="")
            .distinct()
            .order_by("-review__published_date")[:6]
        )
    )


def load_date_in_user_tz_as_utc(date_str: str, user: models.User) -> datetime:
    """ensures that data is stored consistently in the UTC timezone"""
    if not date_str:
        return None
    user_tz = dateutil.tz.gettz(user.preferred_timezone)
    date = dateutil.parser.parse(date_str, ignoretz=True)
    try:
        return date.replace(tzinfo=user_tz).astimezone(dateutil.tz.UTC)
    except ParserError:
        return None
