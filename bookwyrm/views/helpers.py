""" helper functions used in various views """
import re
from datetime import datetime, timedelta
import dateutil.parser
import dateutil.tz
from dateutil.parser import ParserError

from requests import HTTPError
from django.db.models import Q
from django.conf import settings as django_settings
from django.http import Http404
from django.utils import translation

from bookwyrm import activitypub, models, settings
from bookwyrm.connectors import ConnectorException, get_data
from bookwyrm.status import create_generated_note
from bookwyrm.utils import regex


# pylint: disable=unnecessary-pass
class WebFingerError(Exception):
    """empty error class for problems finding user information with webfinger"""

    pass


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


def subscribe_remote_webfinger(query):
    """get subscribe template from other servers"""
    template = None
    # usernames could be @user@domain or user@domain
    if not query:
        return WebFingerError("invalid_username")

    if query[0] == "@":
        query = query[1:]

    try:
        domain = query.split("@")[1]
    except IndexError:
        return WebFingerError("invalid_username")

    url = f"https://{domain}/.well-known/webfinger?resource=acct:{query}"

    try:
        data = get_data(url)
    except (ConnectorException, HTTPError):
        return WebFingerError("user_not_found")

    for link in data.get("links"):
        if link.get("rel") == "http://ostatus.org/schema/1.0/subscribe":
            template = link["template"]

    return template


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


def set_language(user, response):
    """Updates a user's language"""
    if user.preferred_language:
        translation.activate(user.preferred_language)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        user.preferred_language,
        expires=datetime.now() + timedelta(seconds=django_settings.SESSION_COOKIE_AGE),
    )
    return response


def filter_stream_by_status_type(activities, allowed_types=None):
    """filter out activities based on types"""
    if not allowed_types:
        allowed_types = []

    if "review" not in allowed_types:
        activities = activities.filter(
            Q(review__isnull=True), Q(boost__boosted_status__review__isnull=True)
        )
    if "comment" not in allowed_types:
        activities = activities.filter(
            Q(comment__isnull=True), Q(boost__boosted_status__comment__isnull=True)
        )
    if "quotation" not in allowed_types:
        activities = activities.filter(
            Q(quotation__isnull=True), Q(boost__boosted_status__quotation__isnull=True)
        )
    if "everything" not in allowed_types:
        activities = activities.filter(
            Q(generatednote__isnull=True),
            Q(boost__boosted_status__generatednote__isnull=True),
        )

    return activities
