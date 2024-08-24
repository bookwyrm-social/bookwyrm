""" access the list streams stored in redis """
from django.dispatch import receiver
from django.db import transaction
from django.db.models import signals, Count, Q

from bookwyrm import models
from bookwyrm.redis_store import RedisStore
from bookwyrm.tasks import app, LISTS


class ListsStream(RedisStore):
    """all the lists you can see"""

    def stream_id(self, user):  # pylint: disable=no-self-use
        """the redis key for this user's instance of this stream"""
        if isinstance(user, int):
            # allows the function to take an int or an obj
            return f"{user}-lists"
        return f"{user.id}-lists"

    def get_rank(self, obj):
        """lists are sorted by updated date"""
        return obj.updated_date.timestamp()

    def add_list(self, book_list):
        """add a list to users' feeds"""
        self.add_object_to_stores(book_list, self.get_stores_for_object(book_list))

    def add_user_lists(self, viewer, user):
        """add a user's lists to another user's feed"""
        # only add the lists that the viewer should be able to see
        lists = models.List.privacy_filter(viewer).filter(user=user)
        self.bulk_add_objects_to_store(lists, self.stream_id(viewer))

    def remove_user_lists(self, viewer, user, exclude_privacy=None):
        """remove a user's list from another user's feed"""
        # remove all so that followers only lists are removed
        lists = user.list_set
        if exclude_privacy:
            lists = lists.exclude(privacy=exclude_privacy)
        self.bulk_remove_objects_from_store(lists.all(), self.stream_id(viewer))

    def get_list_stream(self, user):
        """load the lists to be displayed"""
        lists = self.get_store(self.stream_id(user))
        return (
            models.List.objects.filter(id__in=lists)
            .annotate(item_count=Count("listitem", filter=Q(listitem__approved=True)))
            # hide lists with no approved books
            .filter(item_count__gt=0)
            .select_related("user")
            .prefetch_related("listitem_set")
            .order_by("-updated_date")
            .distinct()
        )

    def populate_lists(self, user):
        """go from zero to a timeline"""
        self.populate_store(self.stream_id(user))

    def get_audience(self, book_list):  # pylint: disable=no-self-use
        """given a list, what users should see it"""
        # everybody who could plausibly see this list
        audience = models.User.objects.filter(
            is_active=True,
            local=True,  # we only create feeds for users of this instance
        ).exclude(  # not blocked
            Q(id__in=book_list.user.blocks.all()) | Q(blocks=book_list.user)
        )

        group = book_list.group
        # only visible to the poster and mentioned users
        if book_list.privacy == "direct":
            if group:
                audience = audience.filter(
                    Q(id=book_list.user.id)  # if the user is the post's author
                    | ~Q(groups=group.memberships)  # if the user is in the group
                )
            else:
                audience = audience.filter(
                    Q(id=book_list.user.id)  # if the user is the post's author
                )
        # only visible to the poster's followers and tagged users
        elif book_list.privacy == "followers":
            if group:
                audience = audience.filter(
                    Q(id=book_list.user.id)  # if the user is the list's owner
                    | Q(following=book_list.user)  # if the user is following the owner
                    # if a user is in the group
                    | Q(memberships__group__id=book_list.group.id)
                )
            else:
                audience = audience.filter(
                    Q(id=book_list.user.id)  # if the user is the list's owner
                    | Q(following=book_list.user)  # if the user is following the owner
                )
        return audience.distinct()

    def get_stores_for_object(self, obj):
        """the stores that an object belongs in"""
        return [self.stream_id(u) for u in self.get_audience(obj)]

    def get_lists_for_user(self, user):  # pylint: disable=no-self-use
        """given a user, what lists should they see on this stream"""
        return models.List.privacy_filter(
            user,
            privacy_levels=["public", "followers"],
        )

    def get_objects_for_store(self, store):
        user = models.User.objects.get(id=store.split("-")[0])
        return self.get_lists_for_user(user)


@receiver(signals.post_save, sender=models.List)
# pylint: disable=unused-argument
def add_list_on_create(sender, instance, created, *args, update_fields=None, **kwargs):
    """add newly created lists streams"""
    if created:
        # when creating new things, gotta wait on the transaction
        transaction.on_commit(lambda: add_list_on_create_command(instance.id))
        return

    # if update_fields was specified, we can check if privacy was updated, but if
    # it wasn't specified (ie, by an activitypub update), there's no way to know
    if update_fields and "privacy" not in update_fields:
        return

    # the privacy may have changed, so we need to re-do the whole thing
    remove_list_task.delay(instance.id, re_add=True)


@receiver(signals.post_delete, sender=models.List)
# pylint: disable=unused-argument
def remove_list_on_delete(sender, instance, *args, **kwargs):
    """remove deleted lists to streams"""
    remove_list_task.delay(instance.id)


def add_list_on_create_command(instance_id):
    """runs this code only after the database commit completes"""
    add_list_task.delay(instance_id)


@receiver(signals.post_save, sender=models.UserFollows)
# pylint: disable=unused-argument
def add_lists_on_follow(sender, instance, created, *args, **kwargs):
    """add a newly followed user's lists to feeds"""
    if not created or not instance.user_subject.local:
        return
    add_user_lists_task.delay(instance.user_subject.id, instance.user_object.id)


@receiver(signals.post_delete, sender=models.UserFollows)
# pylint: disable=unused-argument
def remove_lists_on_unfollow(sender, instance, *args, **kwargs):
    """remove lists from a feed on unfollow"""
    if not instance.user_subject.local:
        return
    # remove all but public lists
    remove_user_lists_task.delay(
        instance.user_subject.id, instance.user_object.id, exclude_privacy="public"
    )


@receiver(signals.post_save, sender=models.UserBlocks)
# pylint: disable=unused-argument
def remove_lists_on_block(sender, instance, *args, **kwargs):
    """remove lists from all feeds on block"""
    # blocks apply ot all feeds
    if instance.user_subject.local:
        remove_user_lists_task.delay(instance.user_subject.id, instance.user_object.id)

    # and in both directions
    if instance.user_object.local:
        remove_user_lists_task.delay(instance.user_object.id, instance.user_subject.id)


@receiver(signals.post_delete, sender=models.UserBlocks)
# pylint: disable=unused-argument
def add_lists_on_unblock(sender, instance, *args, **kwargs):
    """add lists back to all feeds on unblock"""
    # make sure there isn't a block in the other direction
    if models.UserBlocks.objects.filter(
        user_subject=instance.user_object,
        user_object=instance.user_subject,
    ).exists():
        return

    # add lists back to streams with lists from anyone
    if instance.user_subject.local:
        add_user_lists_task.delay(
            instance.user_subject.id,
            instance.user_object.id,
        )

    # add lists back to streams with lists from anyone
    if instance.user_object.local:
        add_user_lists_task.delay(
            instance.user_object.id,
            instance.user_subject.id,
        )


@receiver(signals.post_save, sender=models.User)
# pylint: disable=unused-argument
def populate_lists_on_account_create(sender, instance, created, *args, **kwargs):
    """build a user's feeds when they join"""
    if not created or not instance.local:
        return
    transaction.on_commit(lambda: add_list_on_account_create_command(instance.id))


def add_list_on_account_create_command(user_id):
    """wait for the transaction to complete"""
    populate_lists_task.delay(user_id)


# ---- TASKS
@app.task(queue=LISTS)
def populate_lists_task(user_id):
    """background task for populating an empty list stream"""
    user = models.User.objects.get(id=user_id)
    ListsStream().populate_lists(user)


@app.task(queue=LISTS)
def remove_list_task(list_id, re_add=False):
    """remove a list from any stream it might be in"""
    stores = models.User.objects.filter(local=True, is_active=True).values_list(
        "id", flat=True
    )

    # delete for every store
    stores = [ListsStream().stream_id(idx) for idx in stores]
    ListsStream().remove_object_from_stores(list_id, stores)

    if re_add:
        add_list_task.delay(list_id)


@app.task(queue=LISTS)
def add_list_task(list_id):
    """add a list to any stream it should be in"""
    book_list = models.List.objects.get(id=list_id)
    ListsStream().add_list(book_list)


@app.task(queue=LISTS)
def remove_user_lists_task(viewer_id, user_id, exclude_privacy=None):
    """remove all lists by a user from a viewer's stream"""
    viewer = models.User.objects.get(id=viewer_id)
    user = models.User.objects.get(id=user_id)
    ListsStream().remove_user_lists(viewer, user, exclude_privacy=exclude_privacy)


@app.task(queue=LISTS)
def add_user_lists_task(viewer_id, user_id):
    """add all lists by a user to a viewer's stream"""
    viewer = models.User.objects.get(id=viewer_id)
    user = models.User.objects.get(id=user_id)
    ListsStream().add_user_lists(viewer, user)
