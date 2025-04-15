""" helper functions used in various views """

import re
from datetime import datetime, timedelta
import dateutil.parser
import dateutil.tz
from dateutil.parser import ParserError

from requests import HTTPError
from django.db.models import Q
from django.conf import settings as django_settings
from django.shortcuts import redirect, _get_queryset
from django.http import Http404
from django.utils import translation

from bookwyrm import activitypub, models, settings
from bookwyrm.connectors import ConnectorException, get_data
from bookwyrm.status import create_generated_note
from bookwyrm.utils import regex
from bookwyrm.utils.validate import validate_url_domain


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


def handle_remote_webfinger(query, unknown_only=False, refresh=False):
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

        if refresh:
            # Always fetch the remote info - don't even bother checking the DB
            raise models.User.DoesNotExist("remote_only is set to True")

        user = models.User.objects.get(username__iexact=query)

        if unknown_only:
            # In this case, we only want to know about previously undiscovered users
            # So the fact that we found a match in the database means no results
            return None
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
                        link["href"], model=models.User, refresh=refresh
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
            "stopped-reading": "stopped reading",
        }[shelf.identifier]
    except KeyError:
        # it's a non-standard shelf, don't worry about it
        return

    create_generated_note(user, message, mention_books=[book], privacy=privacy)


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


def maybe_redirect_local_path(request, model):
    """
    if the request had an invalid path, return a permanent redirect response to the
    correct one, including a slug if any.
    if path is valid, returns False.
    """

    # don't redirect empty path for unit tests which currently have this
    if request.path in ("/", model.local_path):
        return False

    new_path = model.local_path
    if len(request.GET) > 0:
        new_path = f"{model.local_path}?{request.GET.urlencode()}"

    return redirect(new_path, permanent=True)


def redirect_to_referer(request, *args, **kwargs):
    """Redirect to the referrer, if it's in our domain, with get params"""
    # make sure the refer is part of this instance
    validated = validate_url_domain(request.headers.get("referer", ""))

    if validated:
        return redirect(validated)

    # if not, use the args passed you'd normally pass to redirect()
    return redirect(*args or "/", **kwargs)


# pylint: disable=redefined-builtin
def get_mergeable_object_or_404(klass, id):
    """variant of get_object_or_404 that also redirects if id has been merged
    into another object"""
    queryset = _get_queryset(klass)
    try:
        return queryset.get(pk=id)
    except queryset.model.DoesNotExist:
        try:
            return queryset.get(absorbed__deleted_id=id)
        except queryset.model.DoesNotExist:
            pass

        raise Http404(f"No {queryset.model} with ID {id} exists")
