""" access the activity streams stored in redis """
from abc import ABC
from django.dispatch import receiver
from django.db.models import signals
from django.db.models import Q
import redis

from bookwyrm import models, settings
from bookwyrm.views.helpers import privacy_filter

r = redis.Redis(
    host=settings.REDIS_ACTIVITY_HOST, port=settings.REDIS_ACTIVITY_PORT, db=0
)


class ActivityStream(ABC):
    """ a category of activity stream (like home, local, federated) """

    def stream_id(self, user):
        """ the redis key for this user's instance of this stream """
        return "{}-{}".format(user.id, self.key)

    def unread_id(self, user):
        """ the redis key for this user's unread count for this stream """
        return "{}-unread".format(self.stream_id(user))

    def add_status(self, status):
        """ add a status to users' feeds """
        # we want to do this as a bulk operation, hence "pipeline"
        pipeline = r.pipeline()
        for user in self.stream_users(status):
            # add the status to the feed
            pipeline.lpush(self.stream_id(user), status.id)
            pipeline.ltrim(self.stream_id(user), 0, settings.MAX_STREAM_LENGTH)

            # add to the unread status count
            pipeline.incr(self.unread_id(user))
        # and go!
        pipeline.execute()

    def get_activity_stream(self, user):
        """ load the ids for statuses to be displayed """
        # clear unreads for this feed
        r.set(self.unread_id(user), 0)

        statuses = r.lrange(self.stream_id(user), 0, -1)
        return (
            models.Status.objects.select_subclasses()
            .filter(id__in=statuses)
            .order_by("-published_date")
        )

    def populate_stream(self, user):
        """ go from zero to a timeline """
        pipeline = r.pipeline()
        statuses = self.stream_statuses(user)

        stream_id = self.stream_id(user)
        for status in statuses.all()[: settings.MAX_STREAM_LENGTH]:
            pipeline.lpush(stream_id, status.id)
        pipeline.execute()

    def stream_users(self, status):  # pylint: disable=no-self-use
        """ given a status, what users should see it """
        # direct messages don't appeard in feeds, direct comments/reviews/etc do
        if status.privacy == "direct" and status.status_type == "Note":
            return None

        # everybody who could plausibly see this status
        audience = models.User.objects.filter(
            is_active=True,
            local=True,  # we only create feeds for users of this instance
        ).exclude(
            Q(id__in=status.user.blocks.all()) | Q(blocks=status.user)  # not blocked
        )

        # only visible to the poster's followers and tagged users
        if status.privacy == "followers":
            audience = audience.filter(
                Q(id=status.user.id)  # if the user is the post's author
                | Q(following=status.user)  # if the user is following the author
            )
        return audience

    def stream_statuses(self, user):  # pylint: disable=no-self-use
        """ given a user, what statuses should they see on this stream """
        return privacy_filter(
            user,
            models.Status.objects.select_subclasses(),
            privacy_levels=["public", "unlisted", "followers"],
        )


class HomeStream(ActivityStream):
    """ users you follow """

    key = "home"

    def stream_users(self, status):
        audience = super().stream_users(status)
        return audience.filter(
            Q(id=status.user.id)  # if the user is the post's author
            | Q(following=status.user)  # if the user is following the author
            | Q(id__in=status.mention_users.all())  # or the user is mentioned
        )

    def stream_statuses(self, user):
        return privacy_filter(
            user,
            models.Status.objects.select_subclasses(),
            privacy_levels=["public", "unlisted", "followers"],
            following_only=True,
        )


class LocalStream(ActivityStream):
    """ users you follow """

    key = "local"

    def stream_users(self, status):
        # this stream wants no part in non-public statuses
        if status.privacy != "public":
            return None
        return super().stream_users(status)

    def stream_statuses(self, user):
        # all public statuses by a local user
        return privacy_filter(
            user,
            models.Status.objects.select_subclasses().filter(user__local=True),
            privacy_levels=["public"],
        )


class FederatedStream(ActivityStream):
    """ users you follow """

    key = "federated"

    def stream_users(self, status):
        # this stream wants no part in non-public statuses
        if status.privacy != "public":
            return None
        return super().stream_users(status)

    def stream_statuses(self, user):
        return privacy_filter(
            user,
            models.Status.objects.select_subclasses(),
            privacy_levels=["public"],
        )


streams = {
    "home": HomeStream(),
    "local": LocalStream(),
    "federated": FederatedStream(),
}


@receiver(signals.post_save)
# pylint: disable=unused-argument
def update_feeds(sender, instance, created, *args, **kwargs):
    """ add statuses to activity feeds """
    # we're only interested in new statuses that aren't dms
    if (
        not created
        or not issubclass(sender, models.Status)
        or instance.privacy == "direct"
    ):
        return

    for stream in streams.values():
        stream.add_status(instance)
