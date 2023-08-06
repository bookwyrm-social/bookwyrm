""" access the activity streams stored in redis """
from datetime import timedelta
from django.dispatch import receiver
from django.db import transaction
from django.db.models import signals, Q
from django.utils import timezone
from opentelemetry import trace

from bookwyrm import models
from bookwyrm.redis_store import RedisStore, r
from bookwyrm.tasks import app, STREAMS, IMPORT_TRIGGERED
from bookwyrm.telemetry import open_telemetry


tracer = open_telemetry.tracer()


class ActivityStream(RedisStore):
    """a category of activity stream (like home, local, books)"""

    def stream_id(self, user_id):
        """the redis key for this user's instance of this stream"""
        return f"{user_id}-{self.key}"

    def unread_id(self, user_id):
        """the redis key for this user's unread count for this stream"""
        stream_id = self.stream_id(user_id)
        return f"{stream_id}-unread"

    def unread_by_status_type_id(self, user_id):
        """the redis key for this user's unread count for this stream"""
        stream_id = self.stream_id(user_id)
        return f"{stream_id}-unread-by-type"

    def get_rank(self, obj):  # pylint: disable=no-self-use
        """statuses are sorted by date published"""
        return obj.published_date.timestamp()

    def add_status(self, status, increment_unread=False):
        """add a status to users' feeds"""
        audience = self.get_audience(status)
        # the pipeline contains all the add-to-stream activities
        pipeline = self.add_object_to_stores(
            status, self.get_stores_for_users(audience), execute=False
        )

        if increment_unread:
            for user_id in audience:
                # add to the unread status count
                pipeline.incr(self.unread_id(user_id))
                # add to the unread status count for status type
                pipeline.hincrby(
                    self.unread_by_status_type_id(user_id), get_status_type(status), 1
                )

        # and go!
        pipeline.execute()

    def add_user_statuses(self, viewer, user):
        """add a user's statuses to another user's feed"""
        # only add the statuses that the viewer should be able to see (ie, not dms)
        statuses = models.Status.privacy_filter(viewer).filter(user=user)
        self.bulk_add_objects_to_store(statuses, self.stream_id(viewer.id))

    def remove_user_statuses(self, viewer, user):
        """remove a user's status from another user's feed"""
        # remove all so that followers only statuses are removed
        statuses = user.status_set.all()
        self.bulk_remove_objects_from_store(statuses, self.stream_id(viewer.id))

    def get_activity_stream(self, user):
        """load the statuses to be displayed"""
        # clear unreads for this feed
        r.set(self.unread_id(user.id), 0)
        r.delete(self.unread_by_status_type_id(user.id))

        statuses = self.get_store(self.stream_id(user.id))
        return (
            models.Status.objects.select_subclasses()
            .filter(id__in=statuses)
            .select_related(
                "user",
                "reply_parent",
                "comment__book",
                "review__book",
                "quotation__book",
            )
            .prefetch_related("mention_books", "mention_users")
            .order_by("-published_date")
        )

    def get_unread_count(self, user):
        """get the unread status count for this user's feed"""
        return int(r.get(self.unread_id(user.id)) or 0)

    def get_unread_count_by_status_type(self, user):
        """get the unread status count for this user's feed's status types"""
        status_types = r.hgetall(self.unread_by_status_type_id(user.id))
        return {
            str(key.decode("utf-8")): int(value) or 0
            for key, value in status_types.items()
        }

    def populate_streams(self, user):
        """go from zero to a timeline"""
        self.populate_store(self.stream_id(user.id))

    @tracer.start_as_current_span("ActivityStream._get_audience")
    def _get_audience(self, status):  # pylint: disable=no-self-use
        """given a status, what users should see it, excluding the author"""
        trace.get_current_span().set_attribute("status_type", status.status_type)
        trace.get_current_span().set_attribute("status_privacy", status.privacy)
        trace.get_current_span().set_attribute(
            "status_reply_parent_privacy",
            status.reply_parent.privacy if status.reply_parent else None,
        )
        # direct messages don't appear in feeds, direct comments/reviews/etc do
        if status.privacy == "direct" and status.status_type == "Note":
            return models.User.objects.none()

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
                Q(id__in=status.mention_users.all())  # if the user is mentioned
            )

        # don't show replies to statuses the user can't see
        elif status.reply_parent and status.reply_parent.privacy == "followers":
            audience = audience.filter(
                Q(id=status.reply_parent.user.id)  # if the user is the OG author
                | (
                    Q(following=status.user) & Q(following=status.reply_parent.user)
                )  # if the user is following both authors
            ).distinct()

        # only visible to the poster's followers and tagged users
        elif status.privacy == "followers":
            audience = audience.filter(
                Q(following=status.user)  # if the user is following the author
            )
        return audience.distinct()

    @tracer.start_as_current_span("ActivityStream.get_audience")
    def get_audience(self, status):
        """given a status, what users should see it"""
        trace.get_current_span().set_attribute("stream_id", self.key)
        audience = self._get_audience(status).values_list("id", flat=True)
        status_author = models.User.objects.filter(
            is_active=True, local=True, id=status.user.id
        ).values_list("id", flat=True)
        return list(set(list(audience) + list(status_author)))

    def get_stores_for_users(self, user_ids):
        """convert a list of user ids into redis store ids"""
        return [self.stream_id(user_id) for user_id in user_ids]

    def get_statuses_for_user(self, user):  # pylint: disable=no-self-use
        """given a user, what statuses should they see on this stream"""
        return models.Status.privacy_filter(
            user,
            privacy_levels=["public", "unlisted", "followers"],
        )

    def get_objects_for_store(self, store):
        user = models.User.objects.get(id=store.split("-")[0])
        return self.get_statuses_for_user(user)


class HomeStream(ActivityStream):
    """users you follow"""

    key = "home"

    @tracer.start_as_current_span("HomeStream.get_audience")
    def get_audience(self, status):
        trace.get_current_span().set_attribute("stream_id", self.key)
        audience = super()._get_audience(status)
        if not audience:
            return []
        # if the user is following the author
        audience = audience.filter(following=status.user).values_list("id", flat=True)
        # if the user is the post's author
        status_author = models.User.objects.filter(
            is_active=True, local=True, id=status.user.id
        ).values_list("id", flat=True)
        return list(set(list(audience) + list(status_author)))

    def get_statuses_for_user(self, user):
        return models.Status.privacy_filter(
            user,
            privacy_levels=["public", "unlisted", "followers"],
        ).exclude(
            ~Q(  # remove everything except
                Q(user__followers=user)  # user following
                | Q(user=user)  # is self
                | Q(mention_users=user)  # mentions user
            ),
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
        return models.Status.privacy_filter(
            user,
            privacy_levels=["public"],
        ).filter(user__local=True)


class BooksStream(ActivityStream):
    """books on your shelves"""

    key = "books"

    def _get_audience(self, status):
        """anyone with the mentioned book on their shelves"""
        work = (
            status.book.parent_work
            if hasattr(status, "book")
            else status.mention_books.first().parent_work
        )

        audience = super()._get_audience(status)
        if not audience:
            return models.User.objects.none()
        return audience.filter(shelfbook__book__parent_work=work).distinct()

    def get_audience(self, status):
        # only show public statuses on the books feed,
        # and only statuses that mention books
        if status.privacy != "public" or not (
            status.mention_books.exists() or hasattr(status, "book")
        ):
            return []

        return super().get_audience(status)

    def get_statuses_for_user(self, user):
        """any public status that mentions the user's books"""
        books = user.shelfbook_set.values_list(
            "book__parent_work__id", flat=True
        ).distinct()
        return (
            models.Status.privacy_filter(
                user,
                privacy_levels=["public"],
            )
            .filter(
                Q(comment__book__parent_work__id__in=books)
                | Q(quotation__book__parent_work__id__in=books)
                | Q(review__book__parent_work__id__in=books)
                | Q(mention_books__parent_work__id__in=books)
            )
            .distinct()
        )

    def add_book_statuses(self, user, book):
        """add statuses about a book to a user's feed"""
        work = book.parent_work
        statuses = models.Status.privacy_filter(
            user,
            privacy_levels=["public"],
        )

        book_comments = statuses.filter(Q(comment__book__parent_work=work))
        book_quotations = statuses.filter(Q(quotation__book__parent_work=work))
        book_reviews = statuses.filter(Q(review__book__parent_work=work))
        book_mentions = statuses.filter(Q(mention_books__parent_work=work))

        self.bulk_add_objects_to_store(book_comments, self.stream_id(user.id))
        self.bulk_add_objects_to_store(book_quotations, self.stream_id(user.id))
        self.bulk_add_objects_to_store(book_reviews, self.stream_id(user.id))
        self.bulk_add_objects_to_store(book_mentions, self.stream_id(user.id))

    def remove_book_statuses(self, user, book):
        """add statuses about a book to a user's feed"""
        work = book.parent_work
        statuses = models.Status.privacy_filter(
            user,
            privacy_levels=["public"],
        )

        book_comments = statuses.filter(Q(comment__book__parent_work=work))
        book_quotations = statuses.filter(Q(quotation__book__parent_work=work))
        book_reviews = statuses.filter(Q(review__book__parent_work=work))
        book_mentions = statuses.filter(Q(mention_books__parent_work=work))

        self.bulk_remove_objects_from_store(book_comments, self.stream_id(user.id))
        self.bulk_remove_objects_from_store(book_quotations, self.stream_id(user.id))
        self.bulk_remove_objects_from_store(book_reviews, self.stream_id(user.id))
        self.bulk_remove_objects_from_store(book_mentions, self.stream_id(user.id))


# determine which streams are enabled in settings.py
streams = {
    "home": HomeStream(),
    "local": LocalStream(),
    "books": BooksStream(),
}


@receiver(signals.post_save)
# pylint: disable=unused-argument
def add_status_on_create(sender, instance, created, *args, **kwargs):
    """add newly created statuses to activity feeds"""
    # we're only interested in new statuses
    if not issubclass(sender, models.Status):
        return

    if instance.deleted:
        remove_status_task.delay(instance.id)
        return

    # We don't want to create multiple add_status_tasks for each status, and because
    # the transactions are atomic, on_commit won't run until the status is ready to add.
    if not created:
        return

    # when creating new things, gotta wait on the transaction
    transaction.on_commit(
        lambda: add_status_on_create_command(sender, instance, created)
    )


def add_status_on_create_command(sender, instance, created):
    """runs this code only after the database commit completes"""
    # boosts trigger 'saves" twice, so don't bother duplicating the task
    if sender == models.Boost and not created:
        return

    priority = STREAMS
    # check if this is an old status, de-prioritize if so
    # (this will happen if federation is very slow, or, more expectedly, on csv import)
    if instance.published_date < timezone.now() - timedelta(
        days=1
    ) or instance.created_date < instance.published_date - timedelta(days=1):
        # a backdated status from a local user is an import, don't add it
        if instance.user.local:
            return
        # an out of date remote status is a low priority but should be added
        priority = IMPORT_TRIGGERED

    add_status_task.apply_async(
        args=(instance.id,),
        kwargs={"increment_unread": created},
        queue=priority,
    )

    if sender == models.Boost:
        handle_boost_task.delay(instance.id)


@receiver(signals.post_delete, sender=models.Boost)
# pylint: disable=unused-argument
def remove_boost_on_delete(sender, instance, *args, **kwargs):
    """boosts are deleted"""
    # remove the boost
    remove_status_task.delay(instance.id)
    # re-add the original status
    add_status_task.delay(instance.boosted_status.id)


@receiver(signals.post_save, sender=models.UserFollows)
# pylint: disable=unused-argument
def add_statuses_on_follow(sender, instance, created, *args, **kwargs):
    """add a newly followed user's statuses to feeds"""
    if not created or not instance.user_subject.local:
        return
    add_user_statuses_task.delay(
        instance.user_subject.id, instance.user_object.id, stream_list=["home"]
    )


@receiver(signals.post_delete, sender=models.UserFollows)
# pylint: disable=unused-argument
def remove_statuses_on_unfollow(sender, instance, *args, **kwargs):
    """remove statuses from a feed on unfollow"""
    if not instance.user_subject.local:
        return
    remove_user_statuses_task.delay(
        instance.user_subject.id, instance.user_object.id, stream_list=["home"]
    )


@receiver(signals.post_save, sender=models.UserBlocks)
# pylint: disable=unused-argument
def remove_statuses_on_block(sender, instance, *args, **kwargs):
    """remove statuses from all feeds on block"""
    # blocks apply ot all feeds
    if instance.user_subject.local:
        remove_user_statuses_task.delay(
            instance.user_subject.id, instance.user_object.id
        )

    # and in both directions
    if instance.user_object.local:
        remove_user_statuses_task.delay(
            instance.user_object.id, instance.user_subject.id
        )


@receiver(signals.post_delete, sender=models.UserBlocks)
# pylint: disable=unused-argument
def add_statuses_on_unblock(sender, instance, *args, **kwargs):
    """add statuses back to all feeds on unblock"""
    # make sure there isn't a block in the other direction
    if models.UserBlocks.objects.filter(
        user_subject=instance.user_object,
        user_object=instance.user_subject,
    ).exists():
        return

    public_streams = [k for (k, v) in streams.items() if k != "home"]

    # add statuses back to streams with statuses from anyone
    if instance.user_subject.local:
        add_user_statuses_task.delay(
            instance.user_subject.id,
            instance.user_object.id,
            stream_list=public_streams,
        )

    # add statuses back to streams with statuses from anyone
    if instance.user_object.local:
        add_user_statuses_task.delay(
            instance.user_object.id,
            instance.user_subject.id,
            stream_list=public_streams,
        )


@receiver(signals.post_save, sender=models.User)
# pylint: disable=unused-argument
def populate_streams_on_account_create(sender, instance, created, *args, **kwargs):
    """build a user's feeds when they join"""
    if not created or not instance.local:
        return
    transaction.on_commit(
        lambda: populate_streams_on_account_create_command(instance.id)
    )


def populate_streams_on_account_create_command(instance_id):
    """wait for the transaction to complete"""
    for stream in streams:
        populate_stream_task.delay(stream, instance_id)


@receiver(signals.pre_save, sender=models.ShelfBook)
# pylint: disable=unused-argument
def add_statuses_on_shelve(sender, instance, *args, **kwargs):
    """update books stream when user shelves a book"""
    if not instance.user.local:
        return
    book = instance.book

    # check if the book is already on the user's shelves
    editions = book.parent_work.editions.all()
    if models.ShelfBook.objects.filter(user=instance.user, book__in=editions).exists():
        return

    add_book_statuses_task.delay(instance.user.id, book.id)


@receiver(signals.post_delete, sender=models.ShelfBook)
# pylint: disable=unused-argument
def remove_statuses_on_unshelve(sender, instance, *args, **kwargs):
    """update books stream when user unshelves a book"""
    if not instance.user.local:
        return

    book = instance.book

    # check if the book is actually unshelved, not just moved
    editions = book.parent_work.editions.all()
    if models.ShelfBook.objects.filter(user=instance.user, book__in=editions).exists():
        return

    remove_book_statuses_task.delay(instance.user.id, book.id)


# ---- TASKS


@app.task(queue=STREAMS)
def add_book_statuses_task(user_id, book_id):
    """add statuses related to a book on shelve"""
    user = models.User.objects.get(id=user_id)
    book = models.Edition.objects.get(id=book_id)
    BooksStream().add_book_statuses(user, book)


@app.task(queue=STREAMS)
def remove_book_statuses_task(user_id, book_id):
    """remove statuses about a book from a user's books feed"""
    user = models.User.objects.get(id=user_id)
    book = models.Edition.objects.get(id=book_id)
    BooksStream().remove_book_statuses(user, book)


@app.task(queue=STREAMS)
def populate_stream_task(stream, user_id):
    """background task for populating an empty activitystream"""
    user = models.User.objects.get(id=user_id)
    stream = streams[stream]
    stream.populate_streams(user)


@app.task(queue=STREAMS)
def remove_status_task(status_ids):
    """remove a status from any stream it might be in"""
    # this can take an id or a list of ids
    if not isinstance(status_ids, list):
        status_ids = [status_ids]
    statuses = models.Status.objects.filter(id__in=status_ids)

    for stream in streams.values():
        for status in statuses:
            stream.remove_object_from_stores(
                status, stream.get_stores_for_users(stream.get_audience(status))
            )


@app.task(queue=STREAMS)
def add_status_task(status_id, increment_unread=False):
    """add a status to any stream it should be in"""
    status = models.Status.objects.select_subclasses().get(id=status_id)
    # we don't want to tick the unread count for csv import statuses, idk how better
    # to check than just to see if the states is more than a few days old
    if status.created_date < timezone.now() - timedelta(days=2):
        increment_unread = False
    for stream in streams.values():
        stream.add_status(status, increment_unread=increment_unread)


@app.task(queue=STREAMS)
def remove_user_statuses_task(viewer_id, user_id, stream_list=None):
    """remove all statuses by a user from a viewer's stream"""
    stream_list = [streams[s] for s in stream_list] if stream_list else streams.values()
    viewer = models.User.objects.get(id=viewer_id)
    user = models.User.objects.get(id=user_id)
    for stream in stream_list:
        stream.remove_user_statuses(viewer, user)


@app.task(queue=STREAMS)
def add_user_statuses_task(viewer_id, user_id, stream_list=None):
    """add all statuses by a user to a viewer's stream"""
    stream_list = [streams[s] for s in stream_list] if stream_list else streams.values()
    viewer = models.User.objects.get(id=viewer_id)
    user = models.User.objects.get(id=user_id)
    for stream in stream_list:
        stream.add_user_statuses(viewer, user)


@app.task(queue=STREAMS)
def handle_boost_task(boost_id):
    """remove the original post and other, earlier boosts"""
    instance = models.Status.objects.get(id=boost_id)
    boosted = instance.boost.boosted_status

    # previous boosts of this status
    old_versions = models.Boost.objects.filter(
        boosted_status__id=boosted.id,
        created_date__lt=instance.created_date,
    )

    for stream in streams.values():
        # people who should see the boost (not people who see the original status)
        audience = stream.get_stores_for_users(stream.get_audience(instance))
        stream.remove_object_from_stores(boosted, audience)
        for status in old_versions:
            stream.remove_object_from_stores(status, audience)


def get_status_type(status):
    """return status type even for boosted statuses"""
    status_type = status.status_type.lower()

    # Check if current status is a boost
    if hasattr(status, "boost"):
        # Act in accordance of your findings
        if hasattr(status.boost.boosted_status, "review"):
            status_type = "review"
        if hasattr(status.boost.boosted_status, "comment"):
            status_type = "comment"
        if hasattr(status.boost.boosted_status, "quotation"):
            status_type = "quotation"

    return status_type
