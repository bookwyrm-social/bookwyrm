""" store recommended follows in redis """
import math
import logging
from django.dispatch import receiver
from django.db.models import signals, Count, Q

from bookwyrm import models
from bookwyrm.redis_store import RedisStore, r
from bookwyrm.tasks import app


logger = logging.getLogger(__name__)


class SuggestedUsers(RedisStore):
    """suggested users for a user"""

    max_length = 30

    def get_rank(self, obj):
        """get computed rank"""
        return obj.mutuals  # + (1.0 - (1.0 / (obj.shared_books + 1)))

    def store_id(self, user):  # pylint: disable=no-self-use
        """the key used to store this user's recs"""
        if isinstance(user, int):
            return f"{user}-suggestions"
        return f"{user.id}-suggestions"

    def get_counts_from_rank(self, rank):  # pylint: disable=no-self-use
        """calculate mutuals count and shared books count from rank"""
        return {
            "mutuals": math.floor(rank),
            # "shared_books": int(1 / (-1 * (rank % 1 - 1))) - 1,
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
        return models.User.objects.filter(local=True,).exclude(
            Q(id=obj.id) | Q(followers=obj) | Q(id__in=obj.blocks.all()) | Q(blocks=obj)
        )

    def rerank_obj(self, obj, update_only=True):
        """update all the instances of this user with new ranks"""
        pipeline = r.pipeline()
        for store_user in self.get_users_for_object(obj):
            annotated_user = get_annotated_users(
                store_user,
                id=obj.id,
            ).first()
            if not annotated_user:
                continue

            pipeline.zadd(
                self.store_id(store_user),
                self.get_value(annotated_user),
                xx=update_only,
            )
        pipeline.execute()

    def rerank_user_suggestions(self, user):
        """update the ranks of the follows suggested to a user"""
        self.populate_store(self.store_id(user))

    def remove_suggestion(self, user, suggested_user):
        """take a user out of someone's suggestions"""
        self.bulk_remove_objects_from_store([suggested_user], self.store_id(user))

    def get_suggestions(self, user):
        """get suggestions"""
        values = self.get_store(self.store_id(user), withscores=True)
        results = []
        # annotate users with mutuals and shared book counts
        for user_id, rank in values:
            counts = self.get_counts_from_rank(rank)
            try:
                user = models.User.objects.get(
                    id=user_id, is_active=True, bookwyrm_user=True
                )
            except models.User.DoesNotExist as err:
                # if this happens, the suggestions are janked way up
                logger.exception(err)
                continue
            user.mutuals = counts["mutuals"]
            # user.shared_books = counts["shared_books"]
            results.append(user)
            if len(results) >= 5:
                break
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
            #             shared_books=Count(
            #                 "shelfbook",
            #                 filter=Q(
            #                     ~Q(id=viewer.id),
            #                     shelfbook__book__parent_work__in=[
            #                         s.book.parent_work for s in viewer.shelfbook_set.all()
            #                     ],
            #                 ),
            #                 distinct=True,
            #             ),
        )
    )


suggested_users = SuggestedUsers()


@receiver(signals.post_save, sender=models.UserFollows)
# pylint: disable=unused-argument
def update_suggestions_on_follow(sender, instance, created, *args, **kwargs):
    """remove a follow from the recs and update the ranks"""
    if not created or not instance.user_object.discoverable:
        return

    if instance.user_subject.local:
        remove_suggestion_task.delay(instance.user_subject.id, instance.user_object.id)
    rerank_user_task.delay(instance.user_object.id, update_only=False)


@receiver(signals.post_save, sender=models.UserBlocks)
# pylint: disable=unused-argument
def update_suggestions_on_block(sender, instance, *args, **kwargs):
    """remove blocked users from recs"""
    if instance.user_subject.local and instance.user_object.discoverable:
        remove_suggestion_task.delay(instance.user_subject.id, instance.user_object.id)
    if instance.user_object.local and instance.user_subject.discoverable:
        remove_suggestion_task.delay(instance.user_object.id, instance.user_subject.id)


@receiver(signals.post_delete, sender=models.UserFollows)
# pylint: disable=unused-argument
def update_suggestions_on_unfollow(sender, instance, **kwargs):
    """update rankings, but don't re-suggest because it was probably intentional"""
    if instance.user_object.discoverable:
        rerank_user_task.delay(instance.user_object.id, update_only=False)


# @receiver(signals.post_save, sender=models.ShelfBook)
# @receiver(signals.post_delete, sender=models.ShelfBook)
# # pylint: disable=unused-argument
# def update_rank_on_shelving(sender, instance, *args, **kwargs):
#     """when a user shelves or unshelves a book, re-compute their rank"""
#     # if it's a local user, re-calculate who is rec'ed to them
#     if instance.user.local:
#         rerank_suggestions_task.delay(instance.user.id)
#
#     # if the user is discoverable, update their rankings
#     if instance.user.discoverable:
#         rerank_user_task.delay(instance.user.id)


@receiver(signals.post_save, sender=models.User)
# pylint: disable=unused-argument, too-many-arguments
def update_user(sender, instance, created, update_fields=None, **kwargs):
    """an updated user, neat"""
    # a new user is found, create suggestions for them
    if created and instance.local:
        rerank_suggestions_task.delay(instance.id)

    # we know what fields were updated and discoverability didn't change
    if not instance.bookwyrm_user or (
        update_fields and not "discoverable" in update_fields
    ):
        return

    # deleted the user
    if not created and not instance.is_active:
        remove_user_task.delay(instance.id)
        return

    # this happens on every save, not just when discoverability changes, annoyingly
    if instance.discoverable:
        rerank_user_task.delay(instance.id, update_only=False)
    elif not created:
        remove_user_task.delay(instance.id)


@receiver(signals.post_save, sender=models.FederatedServer)
def domain_level_update(sender, instance, created, update_fields=None, **kwargs):
    """remove users on a domain block"""
    if (
        not update_fields
        or "status" not in update_fields
        or instance.application_type != "bookwyrm"
    ):
        return

    if instance.status == "blocked":
        bulk_remove_instance_task.delay(instance.id)
        return
    bulk_add_instance_task.delay(instance.id)


# ------------------- TASKS


@app.task(queue="low_priority")
def rerank_suggestions_task(user_id):
    """do the hard work in celery"""
    suggested_users.rerank_user_suggestions(user_id)


@app.task(queue="low_priority")
def rerank_user_task(user_id, update_only=False):
    """do the hard work in celery"""
    user = models.User.objects.get(id=user_id)
    suggested_users.rerank_obj(user, update_only=update_only)


@app.task(queue="low_priority")
def remove_user_task(user_id):
    """do the hard work in celery"""
    user = models.User.objects.get(id=user_id)
    suggested_users.remove_object_from_related_stores(user)


@app.task(queue="medium_priority")
def remove_suggestion_task(user_id, suggested_user_id):
    """remove a specific user from a specific user's suggestions"""
    suggested_user = models.User.objects.get(id=suggested_user_id)
    suggested_users.remove_suggestion(user_id, suggested_user)


@app.task(queue="low_priority")
def bulk_remove_instance_task(instance_id):
    """remove a bunch of users from recs"""
    for user in models.User.objects.filter(federated_server__id=instance_id):
        suggested_users.remove_object_from_related_stores(user)


@app.task(queue="low_priority")
def bulk_add_instance_task(instance_id):
    """remove a bunch of users from recs"""
    for user in models.User.objects.filter(federated_server__id=instance_id):
        suggested_users.rerank_obj(user, update_only=False)
