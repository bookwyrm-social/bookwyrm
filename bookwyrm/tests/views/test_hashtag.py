""" tests for hashtag view """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.tests.validate_html import validate_html


class HashtagView(TestCase):
    """hashtag view"""

    def setUp(self):
        self.factory = RequestFactory()
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
            self.follower_user = models.User.objects.create_user(
                "follower@local.com",
                "follower@email.com",
                "followerword",
                local=True,
                localname="follower",
                remote_id="https://example.com/users/follower",
            )
            self.local_user.followers.add(self.follower_user)
            self.other_user = models.User.objects.create_user(
                "other@local.com",
                "other@email.com",
                "otherword",
                local=True,
                localname="other",
                remote_id="https://example.com/users/other",
            )

        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )

        self.hashtag_bookclub = models.Hashtag.objects.create(name="#BookClub")
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch("bookwyrm.activitystreams.add_status_task.delay"):
            self.statuses_bookclub = [
                models.Comment.objects.create(
                    book=self.book, user=self.local_user, content="#BookClub"
                ),
            ]
        for status in self.statuses_bookclub:
            status.mention_hashtags.add(self.hashtag_bookclub)

        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create()

    def test_hashtag_page(self):
        """just make sure it loads"""
        view = views.Hashtag.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.hashtag_bookclub.id)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.context_data["activities"]), 1)

    def test_privacy_direct(self):
        """ensure statuses with privacy set to direct are always filtered out"""
        view = views.Hashtag.as_view()
        request = self.factory.get("")

        hashtag = models.Hashtag.objects.create(name="#test")
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Comment.objects.create(
                user=self.local_user, book=self.book, content="#test", privacy="direct"
            )
            status.mention_hashtags.add(hashtag)

        for user in [
            self.local_user,
            self.follower_user,
            self.other_user,
            self.anonymous_user,
        ]:
            request.user = user
            result = view(request, hashtag.id)
            self.assertNotIn(status, result.context_data["activities"])

    def test_privacy_unlisted(self):
        """ensure statuses with privacy set to unlisted are always filtered out"""
        view = views.Hashtag.as_view()
        request = self.factory.get("")

        hashtag = models.Hashtag.objects.create(name="#test")
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Comment.objects.create(
                user=self.local_user,
                book=self.book,
                content="#test",
                privacy="unlisted",
            )
            status.mention_hashtags.add(hashtag)

        for user in [
            self.local_user,
            self.follower_user,
            self.other_user,
            self.anonymous_user,
        ]:
            request.user = user
            result = view(request, hashtag.id)
            self.assertNotIn(status, result.context_data["activities"])

    def test_privacy_following(self):
        """ensure only creator and followers can see statuses with privacy
        set to followers"""
        view = views.Hashtag.as_view()
        request = self.factory.get("")

        hashtag = models.Hashtag.objects.create(name="#test")
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Comment.objects.create(
                user=self.local_user,
                book=self.book,
                content="#test",
                privacy="followers",
            )
            status.mention_hashtags.add(hashtag)

        for user in [self.local_user, self.follower_user]:
            request.user = user
            result = view(request, hashtag.id)
            self.assertIn(status, result.context_data["activities"])

        for user in [self.other_user, self.anonymous_user]:
            request.user = user
            result = view(request, hashtag.id)
            self.assertNotIn(status, result.context_data["activities"])

    def test_not_found(self):
        """make sure 404 is rendered"""
        view = views.Hashtag.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        with self.assertRaises(Http404):
            view(request, 42)

    def test_empty(self):
        """hashtag without any statuses should still render"""
        view = views.Hashtag.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        hashtag_empty = models.Hashtag.objects.create(name="#empty")
        result = view(request, hashtag_empty.id)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.context_data["activities"]), 0)

    def test_logged_out(self):
        """make sure it loads all activities"""
        view = views.Hashtag.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user

        result = view(request, self.hashtag_bookclub.id)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.context_data["activities"]), 1)
