''' helper functions used in various views '''
import re
from requests import HTTPError
from django.db.models import Q

from bookwyrm import activitypub, models
from bookwyrm.connectors import ConnectorException, get_data
from bookwyrm.status import create_generated_note
from bookwyrm.utils import regex


def get_user_from_username(viewer, username):
    ''' helper function to resolve a localname or a username to a user '''
    # raises DoesNotExist if user is now found
    try:
        return models.User.viewer_aware_objects(viewer).get(localname=username)
    except models.User.DoesNotExist:
        return models.User.viewer_aware_objects(viewer).get(username=username)


def is_api_request(request):
    ''' check whether a request is asking for html or data '''
    return 'json' in request.headers.get('Accept') or \
            request.path[-5:] == '.json'


def is_bookwyrm_request(request):
    ''' check if the request is coming from another bookwyrm instance '''
    user_agent = request.headers.get('User-Agent')
    if user_agent is None or \
            re.search(regex.bookwyrm_user_agent, user_agent) is None:
        return False
    return True


def object_visible_to_user(viewer, obj):
    ''' is a user authorized to view an object? '''
    if not obj:
        return False

    # viewer can't see it if the object's owner blocked them
    if viewer in obj.user.blocks.all():
        return False

    # you can see your own posts and any public or unlisted posts
    if viewer == obj.user or obj.privacy in ['public', 'unlisted']:
        return True

    # you can see the followers only posts of people you follow
    if obj.privacy == 'followers' and \
            obj.user.followers.filter(id=viewer.id).first():
        return True

    # you can see dms you are tagged in
    if isinstance(obj, models.Status):
        if obj.privacy == 'direct' and \
                obj.mention_users.filter(id=viewer.id).first():
            return True
    return False


def privacy_filter(viewer, queryset, privacy_levels, following_only=False):
    ''' filter objects that have "user" and "privacy" fields '''
    # exclude blocks from both directions
    if not viewer.is_anonymous:
        blocked = models.User.objects.filter(id__in=viewer.blocks.all()).all()
        queryset = queryset.exclude(
            Q(user__in=blocked) | Q(user__blocks=viewer))

    # you can't see followers only or direct messages if you're not logged in
    if viewer.is_anonymous:
        privacy_levels = [p for p in privacy_levels if \
            not p in ['followers', 'direct']]

    # filter to only privided privacy levels
    queryset = queryset.filter(privacy__in=privacy_levels)

    # only include statuses the user follows
    if following_only:
        queryset = queryset.exclude(
            ~Q(# remove everythign except
                Q(user__in=viewer.following.all()) | # user following
                Q(user=viewer) |# is self
                Q(mention_users=viewer)# mentions user
            ),
        )
    # exclude followers-only statuses the user doesn't follow
    elif 'followers' in privacy_levels:
        queryset = queryset.exclude(
            ~Q(# user isn't following and it isn't their own status
                Q(user__in=viewer.following.all()) | Q(user=viewer)
            ),
            privacy='followers' # and the status is followers only
        )

    # exclude direct messages not intended for the user
    if 'direct' in privacy_levels:
        queryset = queryset.exclude(
            ~Q(
                Q(user=viewer) | Q(mention_users=viewer)
            ), privacy='direct'
        )
    return queryset


def get_activity_feed(
        user, privacy, local_only=False, following_only=False,
        queryset=models.Status.objects):
    ''' get a filtered queryset of statuses '''
    # if we're looking at Status, we need this. We don't if it's Comment
    if hasattr(queryset, 'select_subclasses'):
        queryset = queryset.select_subclasses()

    # exclude deleted
    queryset = queryset.exclude(deleted=True).order_by('-published_date')

    # apply privacy filters
    privacy = privacy if isinstance(privacy, list) else [privacy]
    queryset = privacy_filter(
        user, queryset, privacy, following_only=following_only)

    # filter for only local status
    if local_only:
        queryset = queryset.filter(user__local=True)

    # remove statuses that have boosts in the same queryset
    try:
        queryset = queryset.filter(~Q(boosters__in=queryset))
    except ValueError:
        pass

    return queryset


def handle_remote_webfinger(query):
    ''' webfingerin' other servers '''
    user = None

    # usernames could be @user@domain or user@domain
    if not query:
        return None

    if query[0] == '@':
        query = query[1:]

    try:
        domain = query.split('@')[1]
    except IndexError:
        return None

    try:
        user = models.User.objects.get(username=query)
    except models.User.DoesNotExist:
        url = 'https://%s/.well-known/webfinger?resource=acct:%s' % \
            (domain, query)
        try:
            data = get_data(url)
        except (ConnectorException, HTTPError):
            return None

        for link in data.get('links'):
            if link.get('rel') == 'self':
                try:
                    user = activitypub.resolve_remote_id(
                        models.User, link['href']
                    )
                except KeyError:
                    return None
    return user


def get_edition(book_id):
    ''' look up a book in the db and return an edition '''
    book = models.Book.objects.select_subclasses().get(id=book_id)
    if isinstance(book, models.Work):
        book = book.get_default_edition()
    return book


def handle_reading_status(user, shelf, book, privacy):
    ''' post about a user reading a book '''
    # tell the world about this cool thing that happened
    try:
        message = {
            'to-read': 'wants to read',
            'reading': 'started reading',
            'read': 'finished reading'
        }[shelf.identifier]
    except KeyError:
        # it's a non-standard shelf, don't worry about it
        return

    status = create_generated_note(
        user,
        message,
        mention_books=[book],
        privacy=privacy
    )
    status.save()


def is_blocked(viewer, user):
    ''' is this viewer blocked by the user? '''
    if viewer.is_authenticated and viewer in user.blocks.all():
        return True
    return False
