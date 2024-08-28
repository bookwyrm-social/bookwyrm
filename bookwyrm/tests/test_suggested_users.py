""" testing user follow suggestions """
from collections import namedtuple
from unittest.mock import patch

from django.db.models import Q
from django.test import TestCase

from bookwyrm import models
from bookwyrm.suggested_users import suggested_users, get_annotated_users


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
@patch("bookwyrm.activitystreams.add_status_task.delay")
@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.lists_stream.populate_lists_task.delay")
@patch("bookwyrm.activitystreams.add_book_statuses_task.delay")
@patch("bookwyrm.suggested_users.rerank_user_task.delay")
@patch("bookwyrm.suggested_users.remove_user_task.delay")
class SuggestedUsers(TestCase):
    """using redis to build activity streams"""

    def setUp(self):
        """use a test csv"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
            )

    def test_get_rank(self, *_):
        """a float that reflects both the mutuals count and shared books"""
        Mock = namedtuple("AnnotatedUserMock", ("mutuals", "shared_books"))
        annotated_user_mock = Mock(3, 27)
        rank = suggested_users.get_rank(annotated_user_mock)
        self.assertEqual(rank, 3)  # 3.9642857142857144)

    def test_store_id_from_obj(self, *_):
        """redis key generation by user obj"""
        self.assertEqual(
            suggested_users.store_id(self.local_user),
            f"{self.local_user.id}-suggestions",
        )

    def test_store_id_from_id(self, *_):
        """redis key generation by user id"""
        self.assertEqual(
            suggested_users.store_id(self.local_user.id),
            f"{self.local_user.id}-suggestions",
        )

    def test_get_counts_from_rank(self, *_):
        """reverse the rank computation to get the mutuals and shared books counts"""
        counts = suggested_users.get_counts_from_rank(3.9642857142857144)
        self.assertEqual(counts["mutuals"], 3)
        # self.assertEqual(counts["shared_books"], 27)

    def test_get_objects_for_store(self, *_):
        """list of people to follow for a given user"""

        mutual_user = models.User.objects.create_user(
            "rat", "rat@local.rat", "password", local=True, localname="rat"
        )
        suggestable_user = models.User.objects.create_user(
            "nutria",
            "nutria@nutria.nutria",
            "password",
            local=True,
            localname="nutria",
            discoverable=True,
        )

        # you follow rat
        mutual_user.followers.add(self.local_user)
        # rat follows the suggested user
        suggestable_user.followers.add(mutual_user)

        results = suggested_users.get_objects_for_store(
            f"{self.local_user.id}-suggestions"
        )
        self.assertEqual(results.count(), 1)
        match = results.first()
        self.assertEqual(match.id, suggestable_user.id)
        self.assertEqual(match.mutuals, 1)

    def test_get_stores_for_object(self, *_):
        """possible follows"""
        mutual_user = models.User.objects.create_user(
            "rat", "rat@local.rat", "password", local=True, localname="rat"
        )
        suggestable_user = models.User.objects.create_user(
            "nutria",
            "nutria@nutria.nutria",
            "password",
            local=True,
            localname="nutria",
            discoverable=True,
        )

        # you follow rat
        mutual_user.followers.add(self.local_user)
        # rat follows the suggested user
        suggestable_user.followers.add(mutual_user)

        results = suggested_users.get_stores_for_object(self.local_user)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], f"{suggestable_user.id}-suggestions")

    def test_get_users_for_object(self, *_):
        """given a user, who might want to follow them"""
        mutual_user = models.User.objects.create_user(
            "rat", "rat@local.rat", "password", local=True, localname="rat"
        )
        suggestable_user = models.User.objects.create_user(
            "nutria",
            "nutria@nutria.nutria",
            "password",
            local=True,
            localname="nutria",
            discoverable=True,
        )
        # you follow rat
        mutual_user.followers.add(self.local_user)
        # rat follows the suggested user
        suggestable_user.followers.add(mutual_user)

        results = suggested_users.get_users_for_object(self.local_user)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], suggestable_user)

    def test_rerank_user_suggestions(self, *_):
        """does it call the populate store function correctly"""
        with patch(
            "bookwyrm.suggested_users.SuggestedUsers.populate_store"
        ) as store_mock:
            suggested_users.rerank_user_suggestions(self.local_user)
        args = store_mock.call_args[0]
        self.assertEqual(args[0], f"{self.local_user.id}-suggestions")

    def test_get_suggestions(self, *_):
        """load from store"""
        with patch("bookwyrm.suggested_users.SuggestedUsers.get_store") as mock:
            mock.return_value = [(self.local_user.id, 7.9)]
            results = suggested_users.get_suggestions(self.local_user)
        self.assertEqual(results[0], self.local_user)
        self.assertEqual(results[0].mutuals, 7)

    def test_get_annotated_users(self, *_):
        """list of people you might know"""
        user_1 = models.User.objects.create_user(
            "nutria@local.com",
            "nutria@nutria.com",
            "nutriaword",
            local=True,
            localname="nutria",
            discoverable=True,
        )
        user_2 = models.User.objects.create_user(
            "fish@local.com",
            "fish@fish.com",
            "fishword",
            local=True,
            localname="fish",
        )
        work = models.Work.objects.create(title="Test Work")
        book = models.Edition.objects.create(
            title="Test Book",
            remote_id="https://example.com/book/1",
            parent_work=work,
        )
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            # 1 shared follow
            self.local_user.following.add(user_2)
            user_1.followers.add(user_2)

            # 1 shared book
            models.ShelfBook.objects.create(
                user=self.local_user,
                book=book,
                shelf=self.local_user.shelf_set.first(),
            )
            models.ShelfBook.objects.create(
                user=user_1, book=book, shelf=user_1.shelf_set.first()
            )

        result = get_annotated_users(self.local_user)
        self.assertEqual(result.count(), 1)
        self.assertTrue(user_1 in result)
        self.assertFalse(user_2 in result)

        user_1_annotated = result.get(id=user_1.id)
        self.assertEqual(user_1_annotated.mutuals, 1)
        # self.assertEqual(user_1_annotated.shared_books, 1)

    def test_get_annotated_users_counts(self, *_):
        """correct counting for multiple shared attributed"""
        user_1 = models.User.objects.create_user(
            "nutria@local.com",
            "nutria@nutria.com",
            "nutriaword",
            local=True,
            localname="nutria",
            discoverable=True,
        )
        for i in range(3):
            user = models.User.objects.create_user(
                f"{i}@local.com",
                f"{i}@nutria.com",
                "password",
                local=True,
                localname=i,
            )
            user.following.add(user_1)
            user.followers.add(self.local_user)

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            for i in range(3):
                book = models.Edition.objects.create(
                    title=i,
                    parent_work=models.Work.objects.create(title=i),
                )
                models.ShelfBook.objects.create(
                    user=self.local_user,
                    book=book,
                    shelf=self.local_user.shelf_set.first(),
                )
                models.ShelfBook.objects.create(
                    user=user_1, book=book, shelf=user_1.shelf_set.first()
                )

        result = get_annotated_users(
            self.local_user,
            ~Q(id=self.local_user.id),
            ~Q(followers=self.local_user),
        )
        user_1_annotated = result.get(id=user_1.id)
        self.assertEqual(user_1_annotated.mutuals, 3)
