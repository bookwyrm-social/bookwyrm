''' helper functions used in various views '''
from django.db.models import Q
from bookwyrm import models

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
