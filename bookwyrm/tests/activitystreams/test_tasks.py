""" testing activitystreams """
from unittest.mock import patch
from django.test import TestCase
from bookwyrm import activitystreams, models


class Activitystreams(TestCase):
    """using redis to build activity streams"""

    def setUp(self):
        """use a test csv"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.local_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
            )
            self.another_user = models.User.objects.create_user(
                "nutria",
                "nutria@nutria.nutria",
                "password",
                local=True,
                localname="nutria",
            )
        work = models.Work.objects.create(title="test work")
        self.book = models.Edition.objects.create(title="test book", parent_work=work)
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            self.status = models.Status.objects.create(
                content="hi", user=self.local_user
            )

    def test_add_book_statuses_task(self):
        """statuses related to a book"""
        with patch("bookwyrm.activitystreams.BooksStream.add_book_statuses") as mock:
            activitystreams.add_book_statuses_task(self.local_user.id, self.book.id)
        self.assertTrue(mock.called)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)
        self.assertEqual(args[1], self.book)

    def test_remove_book_statuses_task(self):
        """remove stauses related to a book"""
        with patch("bookwyrm.activitystreams.BooksStream.remove_book_statuses") as mock:
            activitystreams.remove_book_statuses_task(self.local_user.id, self.book.id)
        self.assertTrue(mock.called)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)
        self.assertEqual(args[1], self.book)

    def test_populate_stream_task(self):
        """populate a given stream"""
        with patch("bookwyrm.activitystreams.BooksStream.populate_streams") as mock:
            activitystreams.populate_stream_task("books", self.local_user.id)
        self.assertTrue(mock.called)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)

        with patch("bookwyrm.activitystreams.HomeStream.populate_streams") as mock:
            activitystreams.populate_stream_task("home", self.local_user.id)
        self.assertTrue(mock.called)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)

    def test_remove_status_task(self):
        """remove a status from all streams"""
        with patch(
            "bookwyrm.activitystreams.ActivityStream.remove_object_from_related_stores"
        ) as mock:
            activitystreams.remove_status_task(self.status.id)
        self.assertEqual(mock.call_count, 3)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.status)

    def test_add_status_task(self):
        """add a status to all streams"""
        with patch("bookwyrm.activitystreams.ActivityStream.add_status") as mock:
            activitystreams.add_status_task(self.status.id)
        self.assertEqual(mock.call_count, 3)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.status)

    def test_remove_user_statuses_task(self):
        """remove all statuses by a user from another users' feeds"""
        with patch(
            "bookwyrm.activitystreams.ActivityStream.remove_user_statuses"
        ) as mock:
            activitystreams.remove_user_statuses_task(
                self.local_user.id, self.another_user.id
            )
        self.assertEqual(mock.call_count, 3)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)
        self.assertEqual(args[1], self.another_user)

        with patch("bookwyrm.activitystreams.HomeStream.remove_user_statuses") as mock:
            activitystreams.remove_user_statuses_task(
                self.local_user.id, self.another_user.id, stream_list=["home"]
            )
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)
        self.assertEqual(args[1], self.another_user)

    def test_add_user_statuses_task(self):
        """add a user's statuses to another users feeds"""
        with patch("bookwyrm.activitystreams.ActivityStream.add_user_statuses") as mock:
            activitystreams.add_user_statuses_task(
                self.local_user.id, self.another_user.id
            )
        self.assertEqual(mock.call_count, 3)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)
        self.assertEqual(args[1], self.another_user)

        with patch("bookwyrm.activitystreams.HomeStream.add_user_statuses") as mock:
            activitystreams.add_user_statuses_task(
                self.local_user.id, self.another_user.id, stream_list=["home"]
            )
        self.assertEqual(mock.call_count, 1)
        args = mock.call_args[0]
        self.assertEqual(args[0], self.local_user)
        self.assertEqual(args[1], self.another_user)

    @patch("bookwyrm.activitystreams.LocalStream.remove_object_from_related_stores")
    @patch("bookwyrm.activitystreams.BooksStream.remove_object_from_related_stores")
    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
    def test_boost_to_another_timeline(self, *_):
        """add a boost and deduplicate the boosted status on the timeline"""
        status = models.Status.objects.create(user=self.local_user, content="hi")
        with patch("bookwyrm.activitystreams.handle_boost_task.delay"):
            boost = models.Boost.objects.create(
                boosted_status=status,
                user=self.another_user,
            )
        with patch(
            "bookwyrm.activitystreams.HomeStream.remove_object_from_related_stores"
        ) as mock:
            activitystreams.handle_boost_task(boost.id)

        self.assertTrue(mock.called)
        call_args = mock.call_args
        self.assertEqual(call_args[0][0], status)
        self.assertEqual(
            call_args[1]["stores"], ["{:d}-home".format(self.another_user.id)]
        )

    @patch("bookwyrm.activitystreams.LocalStream.remove_object_from_related_stores")
    @patch("bookwyrm.activitystreams.BooksStream.remove_object_from_related_stores")
    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
    def test_boost_to_following_timeline(self, *_):
        """add a boost and deduplicate the boosted status on the timeline"""
        self.local_user.following.add(self.another_user)
        status = models.Status.objects.create(user=self.local_user, content="hi")
        with patch("bookwyrm.activitystreams.handle_boost_task.delay"):
            boost = models.Boost.objects.create(
                boosted_status=status,
                user=self.another_user,
            )
        with patch(
            "bookwyrm.activitystreams.HomeStream.remove_object_from_related_stores"
        ) as mock:
            activitystreams.handle_boost_task(boost.id)
        self.assertTrue(mock.called)
        call_args = mock.call_args
        self.assertEqual(call_args[0][0], status)
        self.assertTrue(
            "{:d}-home".format(self.another_user.id) in call_args[1]["stores"]
        )
        self.assertTrue(
            "{:d}-home".format(self.local_user.id) in call_args[1]["stores"]
        )

    @patch("bookwyrm.activitystreams.LocalStream.remove_object_from_related_stores")
    @patch("bookwyrm.activitystreams.BooksStream.remove_object_from_related_stores")
    @patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay")
    def test_boost_to_same_timeline(self, *_):
        """add a boost and deduplicate the boosted status on the timeline"""
        status = models.Status.objects.create(user=self.local_user, content="hi")
        with patch("bookwyrm.activitystreams.handle_boost_task.delay"):
            boost = models.Boost.objects.create(
                boosted_status=status,
                user=self.local_user,
            )
        with patch(
            "bookwyrm.activitystreams.HomeStream.remove_object_from_related_stores"
        ) as mock:
            activitystreams.handle_boost_task(boost.id)
        self.assertTrue(mock.called)
        call_args = mock.call_args
        self.assertEqual(call_args[0][0], status)
        self.assertEqual(
            call_args[1]["stores"], ["{:d}-home".format(self.local_user.id)]
        )
