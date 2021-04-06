""" store recommended follows in redis """
import math.floor
from django.dispatch import receiver
from django.db.models import signals, Q

from bookwyrm import models
from bookwyrm.redis_store import RedisStore, r
from bookwyrm.views.helpers import get_annotated_users


class SuggestedUsers(RedisStore):
    """ suggested users for a user """

    max_length = 10

    def get_rank(self, obj):
        """ get computed rank """
        return obj.mutuals + (1.0 - (1.0 / (obj.shared_books + 1)))

    def store_id(self, user):  # pylint: disable=no-self-use
        """ the key used to store this user's recs """
        return "{:d}-suggestions".format(user.id)

    def get_counts_from_rank(self, rank):  # pylint: disable=no-self-use
        """ calculate mutuals count and shared books count from rank """
        return {
            "mutuals": math.floor(rank),
            "shared_books": int(1 / (-1 * (1 % rank - 1))),
        }

    def get_objects_for_store(self, store):
        """ a list of potential follows for a user """
        user = models.User.objects.get(id=store.split("-")[0])

        return get_annotated_users(
            user,
            ~Q(id=user.id),
            ~Q(followers=user),
            ~Q(follower_requests=user),
            bookwyrm_user=True,
        )

    def get_stores_for_object(self, obj):
        """ given a user, who might want to follow them """
        return models.User.objects.filter(
            local=True,
        ).exclude(user_following=obj)

    def rerank_obj(self, obj):
        """ update all the instances of this user with new ranks """
        stores = self.get_stores_for_object(obj)
        pipeline = r.pipeline()
        for store in stores:
            pipeline.zadd(store, self.get_value(obj), xx=True)
        pipeline.execute()

    def rerank_user_suggestions(self, user):
        """ update the ranks of the follows suggested to a user """
        self.populate_store(self.store_id(user))

    def get_suggestions(self, user):
        """ get suggestions """
        values = self.get_store(self.store_id(user), withscores=True)
        results = []
        # annotate users with mutuals and shared book counts
        for user_id, rank in values[:5]:
            counts = self.get_counts_from_rank(rank)
            user = models.User.objects.get(id=user_id)
            user.mutuals = counts["mutuals"]
            user.shared_books = counts["shared_books"]
            results.append(user)
        return results


suggested_users = SuggestedUsers()


@receiver(signals.post_save, sender=models.UserFollows)
# pylint: disable=unused-argument
def update_suggestions_on_follow(sender, instance, created, *args, **kwargs):
    """ remove a follow from the recs and update the ranks"""
    if (
        not created
        or not instance.user_subject.local
        or not instance.user_object.discoverable
    ):
        return
    suggested_users.bulk_remove_objects_from_store(
        [instance.user_object], instance.user_subject
    )
    suggested_users.rerank_obj(instance.user_object)


@receiver(signals.post_save, sender=models.ShelfBook)
@receiver(signals.post_delete, sender=models.ShelfBook)
# pylint: disable=unused-argument
def update_rank_on_shelving(sender, instance, *args, **kwargs):
    """ when a user shelves or unshelves a book, re-compute their rank """
    if not instance.user.discoverable:
        return
    suggested_users.rerank_obj(instance.user)


@receiver(signals.post_save, sender=models.User)
# pylint: disable=unused-argument, too-many-arguments
def add_or_remove_on_discoverability_change(
    sender, instance, created, raw, using, update_fields, **kwargs
):
    """ make a user (un)discoverable """
    if not "discoverable" in update_fields:
        return

    if created:
        suggested_users.rerank_user_suggestions(instance)

    if instance.discoverable:
        suggested_users.add_object_to_related_stores(instance)
    elif not created and not instance.discoverable:
        suggested_users.remove_object_from_related_stores(instance)
