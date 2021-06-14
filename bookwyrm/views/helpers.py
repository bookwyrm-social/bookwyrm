""" helper functions used in various views """
import re
from requests import HTTPError
from django.core.exceptions import FieldError
from django.db.models import Count, Max, Q
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
    return "json" in request.headers.get("Accept", "") or request.path[-5:] == ".json"


def is_bookwyrm_request(request):
    """check if the request is coming from another bookwyrm instance"""
    user_agent = request.headers.get("User-Agent")
    if user_agent is None or re.search(regex.bookwyrm_user_agent, user_agent) is None:
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
                Q(user__in=viewer.following.all()) | Q(user=viewer)
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
        url = "https://%s/.well-known/webfinger?resource=acct:%s" % (domain, query)
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


def get_discover_books():
    """list of books for the discover page"""
    return list(
        set(
            models.Edition.objects.filter(
                review__published_date__isnull=False,
                review__deleted=False,
                review__user__local=True,
                review__privacy__in=["public", "unlisted"],
            )
            .exclude(cover__exact="")
            .annotate(Max("review__published_date"))
            .order_by("-review__published_date__max")[:6]
        )
    )


def get_suggested_users(user):
    """bookwyrm users you don't already know"""
    return (
        get_annotated_users(
            user,
            ~Q(id=user.id),
            ~Q(followers=user),
            ~Q(follower_requests=user),
            bookwyrm_user=True,
        )
        .order_by("-mutuals", "-last_active_date")
        .all()[:5]
    )


def get_annotated_users(user, *args, **kwargs):
    """Users, annotated with things they have in common"""
    return (
        models.User.objects.filter(discoverable=True, is_active=True, *args, **kwargs)
        .exclude(Q(id__in=user.blocks.all()) | Q(blocks=user))
        .annotate(
            mutuals=Count(
                "followers",
                filter=Q(
                    ~Q(id=user.id),
                    ~Q(id__in=user.following.all()),
                    followers__in=user.following.all(),
                ),
                distinct=True,
            ),
            shared_books=Count(
                "shelfbook",
                filter=Q(
                    ~Q(id=user.id),
                    shelfbook__book__parent_work__in=[
                        s.book.parent_work for s in user.shelfbook_set.all()
                    ],
                ),
                distinct=True,
            ),
        )
    )
