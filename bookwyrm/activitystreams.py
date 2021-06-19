""" access the activity streams stored in redis """
from django.dispatch import receiver
from django.db.models import signals, Q

from bookwyrm import models
from bookwyrm.redis_store import RedisStore, r
from bookwyrm.views.helpers import privacy_filter


class ActivityStream(RedisStore):
    """a category of activity stream (like home, local, federated)"""

    def stream_id(self, user):
        """the redis key for this user's instance of this stream"""
        return "{}-{}".format(user.id, self.key)

    def unread_id(self, user):
        """the redis key for this user's unread count for this stream"""
        return "{}-unread".format(self.stream_id(user))

    def get_rank(self, obj):  # pylint: disable=no-self-use
        """statuses are sorted by date published"""
        return obj.published_date.timestamp()

    def add_status(self, status):
        """add a status to users' feeds"""
        # the pipeline contains all the add-to-stream activities
        pipeline = self.add_object_to_related_stores(status, execute=False)

        for user in self.get_audience(status):
            # add to the unread status count
            pipeline.incr(self.unread_id(user))

        # and go!
        pipeline.execute()

    def add_user_statuses(self, viewer, user):
        """add a user's statuses to another user's feed"""
        # only add the statuses that the viewer should be able to see (ie, not dms)
        statuses = privacy_filter(viewer, user.status_set.all())
        self.bulk_add_objects_to_store(statuses, self.stream_id(viewer))

    def remove_user_statuses(self, viewer, user):
        """remove a user's status from another user's feed"""
        # remove all so that followers only statuses are removed
        statuses = user.status_set.all()
        self.bulk_remove_objects_from_store(statuses, self.stream_id(viewer))

    def get_activity_stream(self, user):
        """load the statuses to be displayed"""
        # clear unreads for this feed
        r.set(self.unread_id(user), 0)

        statuses = self.get_store(self.stream_id(user))
        return (
            models.Status.objects.select_subclasses()
            .filter(id__in=statuses)
            .select_related("user", "reply_parent")
            .prefetch_related("mention_books", "mention_users")
            .order_by("-published_date")
        )

    def get_unread_count(self, user):
        """get the unread status count for this user's feed"""
        return int(r.get(self.unread_id(user)) or 0)

    def populate_streams(self, user):
        """go from zero to a timeline"""
        self.populate_store(self.stream_id(user))

    def get_audience(self, status):  # pylint: disable=no-self-use
        """given a status, what users should see it"""
        # direct messages don't appeard in feeds, direct comments/reviews/etc do
        if status.privacy == "direct" and status.status_type == "Note":
            return []

        # everybody who could plausibly see this status
        audience = models.User.objects.filter(
            is_active=True,
            local=True,  # we only create feeds for users of this instance
        ).exclude(
            Q(id__in=status.user.blocks.all()) | Q(blocks=status.user)  # not blocked
        )

        # only visible to the poster and mentioned users
        if status.privacy == "direct":
            audience = audience.filter(
                Q(id=status.user.id)  # if the user is the post's author
                | Q(id__in=status.mention_users.all())  # if the user is mentioned
            )
        # only visible to the poster's followers and tagged users
        elif status.privacy == "followers":
            audience = audience.filter(
                Q(id=status.user.id)  # if the user is the post's author
                | Q(following=status.user)  # if the user is following the author
            )
        return audience.distinct()

    def get_stores_for_object(self, obj):
        return [self.stream_id(u) for u in self.get_audience(obj)]

    def get_statuses_for_user(self, user):  # pylint: disable=no-self-use
        """given a user, what statuses should they see on this stream"""
        return privacy_filter(
            user,
            models.Status.objects.select_subclasses(),
            privacy_levels=["public", "unlisted", "followers"],
        )

    def get_objects_for_store(self, store):
        user = models.User.objects.get(id=store.split("-")[0])
        return self.get_statuses_for_user(user)


class HomeStream(ActivityStream):
    """users you follow"""

    key = "home"

    def get_audience(self, status):
        audience = super().get_audience(status)
        if not audience:
            return []
        return audience.filter(
            Q(id=status.user.id)  # if the user is the post's author
            | Q(following=status.user)  # if the user is following the author
        ).distinct()

    def get_statuses_for_user(self, user):
        return privacy_filter(
            user,
            models.Status.objects.select_subclasses(),
            privacy_levels=["public", "unlisted", "followers"],
            following_only=True,
        )


class LocalStream(ActivityStream):
    """users you follow"""

    key = "local"

    def get_audience(self, status):
        # this stream wants no part in non-public statuses
        if status.privacy != "public" or not status.user.local:
            return []
        return super().get_audience(status)

    def get_statuses_for_user(self, user):
        # all public statuses by a local user
        return privacy_filter(
            user,
            models.Status.objects.select_subclasses().filter(user__local=True),
            privacy_levels=["public"],
        )


class FederatedStream(ActivityStream):
    """users you follow"""

    key = "federated"

    def get_audience(self, status):
        # this stream wants no part in non-public statuses
        if status.privacy != "public":
            return []
        return super().get_audience(status)

    def get_statuses_for_user(self, user):
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
def add_status_on_create(sender, instance, created, *args, **kwargs):
    """add newly created statuses to activity feeds"""
    # we're only interested in new statuses
    if not issubclass(sender, models.Status):
        return

    if instance.deleted:
        for stream in streams.values():
            stream.remove_object_from_related_stores(instance)
        return

    if not created:
        return

    # iterates through Home, Local, Federated
    for stream in streams.values():
        stream.add_status(instance)

    if sender != models.Boost:
        return
    # remove the original post and other, earlier boosts
    boosted = instance.boost.boosted_status
    old_versions = models.Boost.objects.filter(
        boosted_status__id=boosted.id,
        created_date__lt=instance.created_date,
    )
    for stream in streams.values():
        stream.remove_object_from_related_stores(boosted)
        for status in old_versions:
            stream.remove_object_from_related_stores(status)


@receiver(signals.post_delete, sender=models.Boost)
# pylint: disable=unused-argument
def remove_boost_on_delete(sender, instance, *args, **kwargs):
    """boosts are deleted"""
    # we're only interested in new statuses
    for stream in streams.values():
        # remove the boost
        stream.remove_object_from_related_stores(instance)
        # re-add the original status
        stream.add_status(instance.boosted_status)


@receiver(signals.post_save, sender=models.UserFollows)
# pylint: disable=unused-argument
def add_statuses_on_follow(sender, instance, created, *args, **kwargs):
    """add a newly followed user's statuses to feeds"""
    if not created or not instance.user_subject.local:
        return
    HomeStream().add_user_statuses(instance.user_subject, instance.user_object)


@receiver(signals.post_delete, sender=models.UserFollows)
# pylint: disable=unused-argument
def remove_statuses_on_unfollow(sender, instance, *args, **kwargs):
    """remove statuses from a feed on unfollow"""
    if not instance.user_subject.local:
        return
    HomeStream().remove_user_statuses(instance.user_subject, instance.user_object)


@receiver(signals.post_save, sender=models.UserBlocks)
# pylint: disable=unused-argument
def remove_statuses_on_block(sender, instance, *args, **kwargs):
    """remove statuses from all feeds on block"""
    # blocks apply ot all feeds
    if instance.user_subject.local:
        for stream in streams.values():
            stream.remove_user_statuses(instance.user_subject, instance.user_object)

    # and in both directions
    if instance.user_object.local:
        for stream in streams.values():
            stream.remove_user_statuses(instance.user_object, instance.user_subject)


@receiver(signals.post_delete, sender=models.UserBlocks)
# pylint: disable=unused-argument
def add_statuses_on_unblock(sender, instance, *args, **kwargs):
    """remove statuses from all feeds on block"""
    public_streams = [LocalStream(), FederatedStream()]
    # add statuses back to streams with statuses from anyone
    if instance.user_subject.local:
        for stream in public_streams:
            stream.add_user_statuses(instance.user_subject, instance.user_object)

    # add statuses back to streams with statuses from anyone
    if instance.user_object.local:
        for stream in public_streams:
            stream.add_user_statuses(instance.user_object, instance.user_subject)


@receiver(signals.post_save, sender=models.User)
# pylint: disable=unused-argument
def populate_streams_on_account_create(sender, instance, created, *args, **kwargs):
    """build a user's feeds when they join"""
    if not created or not instance.local:
        return

    for stream in streams.values():
        stream.populate_streams(instance)
