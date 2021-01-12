''' helper functions used in various views '''
import re
from requests import HTTPError
from django.db.models import Q

from bookwyrm import activitypub, models
from bookwyrm.connectors import ConnectorException, get_data
from bookwyrm.utils import regex


def get_user_from_username(username):
    ''' helper function to resolve a localname or a username to a user '''
    # raises DoesNotExist if user is now found
    try:
        return models.User.objects.get(localname=username)
    except models.User.DoesNotExist:
        return models.User.objects.get(username=username)


def is_api_request(request):
    ''' check whether a request is asking for html or data '''
    return 'json' in request.headers.get('Accept') or \
            request.path[-5:] == '.json'


def is_bookworm_request(request):
    ''' check if the request is coming from another bookworm instance '''
    user_agent = request.headers.get('User-Agent')
    if user_agent is None or \
            re.search(regex.bookwyrm_user_agent, user_agent) is None:
        return False
    return True


def status_visible_to_user(viewer, status):
    ''' is a user authorized to view a status? '''
    if viewer == status.user or status.privacy in ['public', 'unlisted']:
        return True
    if status.privacy == 'followers' and \
            status.user.followers.filter(id=viewer.id).first():
        return True
    if status.privacy == 'direct' and \
            status.mention_users.filter(id=viewer.id).first():
        return True
    return False

def get_activity_feed(
        user, privacy, local_only=False, following_only=False,
        queryset=models.Status.objects):
    ''' get a filtered queryset of statuses '''
    privacy = privacy if isinstance(privacy, list) else [privacy]
    # if we're looking at Status, we need this. We don't if it's Comment
    if hasattr(queryset, 'select_subclasses'):
        queryset = queryset.select_subclasses()

    # exclude deleted
    queryset = queryset.exclude(deleted=True).order_by('-published_date')

    # you can't see followers only or direct messages if you're not logged in
    if user.is_anonymous:
        privacy = [p for p in privacy if not p in ['followers', 'direct']]

    # filter to only privided privacy levels
    queryset = queryset.filter(privacy__in=privacy)

    # only include statuses the user follows
    if following_only:
        queryset = queryset.exclude(
            ~Q(# remove everythign except
                Q(user__in=user.following.all()) | # user follwoing
                Q(user=user) |# is self
                Q(mention_users=user)# mentions user
            ),
        )
    # exclude followers-only statuses the user doesn't follow
    elif 'followers' in privacy:
        queryset = queryset.exclude(
            ~Q(# user isn't following and it isn't their own status
                Q(user__in=user.following.all()) | Q(user=user)
            ),
            privacy='followers' # and the status is followers only
        )

    # exclude direct messages not intended for the user
    if 'direct' in privacy:
        queryset = queryset.exclude(
            ~Q(
                Q(user=user) | Q(mention_users=user)
            ), privacy='direct'
        )

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
