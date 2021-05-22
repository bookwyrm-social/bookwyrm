""" store recommended follows in redis """
import math
from django.dispatch import receiver
from django.db.models import signals, Count, Q

from bookwyrm import models
from bookwyrm.redis_store import RedisStore, r


class SuggestedUsers(RedisStore):
    """suggested users for a user"""

    max_length = 30

    def get_rank(self, obj):
        """get computed rank"""
        return obj.mutuals + (1.0 - (1.0 / (obj.shared_books + 1)))

    def store_id(self, user):  # pylint: disable=no-self-use
        """the key used to store this user's recs"""
        return "{:d}-suggestions".format(user.id)

    def get_counts_from_rank(self, rank):  # pylint: disable=no-self-use
        """calculate mutuals count and shared books count from rank"""
        return {
            "mutuals": math.floor(rank),
            "shared_books": int(1 / (-1 * (rank % 1 - 1))) - 1,
        }

    def get_objects_for_store(self, store):
        """a list of potential follows for a user"""
        user = models.User.objects.get(id=store.split("-")[0])

        return get_annotated_users(
            user,
            ~Q(id=user.id),
            ~Q(followers=user),
            ~Q(follower_requests=user),
            bookwyrm_user=True,
        )

    def get_stores_for_object(self, obj):
        return [self.store_id(u) for u in self.get_users_for_object(obj)]

    def get_users_for_object(self, obj):  # pylint: disable=no-self-use
        """given a user, who might want to follow them"""
        return models.User.objects.filter(
            local=True,
        ).exclude(following=obj)

    def rerank_obj(self, obj, update_only=True):
        """update all the instances of this user with new ranks"""
        pipeline = r.pipeline()
        for store_user in self.get_users_for_object(obj):
            annotated_user = get_annotated_users(
                store_user,
                id=obj.id,
            ).first()

            pipeline.zadd(
                self.store_id(store_user),
                self.get_value(annotated_user),
                xx=update_only,
            )
        pipeline.execute()

    def rerank_user_suggestions(self, user):
        """update the ranks of the follows suggested to a user"""
        if not user.local:
            raise ValueError("Trying to create suggestions for remote user: ", user.id)
        self.populate_store(self.store_id(user))

    def get_suggestions(self, user):
        """get suggestions"""
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


def get_annotated_users(viewer, *args, **kwargs):
    """Users, annotated with things they have in common"""
    return (
        models.User.objects.filter(discoverable=True, is_active=True, *args, **kwargs)
        .exclude(Q(id__in=viewer.blocks.all()) | Q(blocks=viewer))
        .annotate(
            mutuals=Count(
                "followers",
                filter=Q(
                    ~Q(id=viewer.id),
                    ~Q(id__in=viewer.following.all()),
                    followers__in=viewer.following.all(),
                ),
                distinct=True,
            ),
            shared_books=Count(
                "shelfbook",
                filter=Q(
                    ~Q(id=viewer.id),
                    shelfbook__book__parent_work__in=[
                        s.book.parent_work for s in viewer.shelfbook_set.all()
                    ],
                ),
                distinct=True,
            ),
        )
    )


suggested_users = SuggestedUsers()


@receiver(signals.post_save, sender=models.UserFollows)
# pylint: disable=unused-argument
def update_suggestions_on_follow(sender, instance, created, *args, **kwargs):
    """remove a follow from the recs and update the ranks"""
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
    """when a user shelves or unshelves a book, re-compute their rank"""
    if not instance.user.discoverable:
        return
    suggested_users.rerank_obj(instance.user)


@receiver(signals.post_save, sender=models.User)
# pylint: disable=unused-argument, too-many-arguments
def add_new_user(sender, instance, created, **kwargs):
    """a new user, wow how cool"""
    if created and instance.local:
        # a new user is found, create suggestions for them
        suggested_users.rerank_user_suggestions(instance)

    # TODO: this happens on every save, not just when discoverability changes
    if instance.discoverable:
        suggested_users.rerank_obj(instance, update_only=False)
    elif not created:
        suggested_users.remove_object_from_related_stores(instance)
