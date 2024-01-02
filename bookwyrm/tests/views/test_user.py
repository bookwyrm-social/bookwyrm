""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http.response import Http404
from django.template.response import TemplateResponse
from django.test import Client, TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.activitypub import ActivitypubResponse
from bookwyrm.tests.validate_html import validate_html


class UserViews(TestCase):
    """view user and edit profile"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
        """we need basic test data and mocks"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
            self.rat = models.User.objects.create_user(
                "rat@local.com", "rat@rat.rat", "password", local=True, localname="rat"
            )
        self.book = models.Edition.objects.create(
            title="test", parent_work=models.Work.objects.create(title="test work")
        )
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.add_book_statuses_task.delay"
        ):
            models.ShelfBook.objects.create(
                book=self.book,
                user=self.local_user,
                shelf=self.local_user.shelf_set.first(),
            )
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_user_page(self):
        """there are so many views, this just makes sure it LOADS"""
        # extras that are rendered on the user page
        models.AnnualGoal.objects.create(
            user=self.local_user, goal=12, privacy="followers"
        )

        view = views.User.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse")
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_user_page_domain(self):
        """when the user domain has dashes in it"""
        with patch("bookwyrm.models.user.set_remote_server"):
            models.User.objects.create_user(
                "nutria",
                "",
                "nutriaword",
                local=False,
                remote_id="https://ex--ample.co----m/users/nutria",
                inbox="https://ex--ample.co----m/users/nutria/inbox",
                outbox="https://ex--ample.co----m/users/nutria/outbox",
            )

        view = views.User.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "nutria@ex--ample.co----m")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_user_page_blocked(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.User.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        self.rat.blocks.add(self.local_user)
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            with self.assertRaises(Http404):
                view(request, "rat")

    def test_followers_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Relationships.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", "followers")

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_followers_page_ap(self):
        """JSON response"""
        view = views.Relationships.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.relationships.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse", "followers")

        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_followers_page_anonymous(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Relationships.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", "followers")

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_user_page_remote_anonymous(self):
        """when a anonymous user tries to get a remote user"""
        with patch("bookwyrm.models.user.set_remote_server"):
            models.User.objects.create_user(
                "nutria",
                "",
                "nutriaword",
                local=False,
                remote_id="https://example.com/users/nutria",
                inbox="https://example.com/users/nutria/inbox",
                outbox="https://example.com/users/nutria/outbox",
            )

        view = views.User.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "nutria@example.com")
        result.client = Client()
        self.assertRedirects(
            result, "https://example.com/users/nutria", fetch_redirect_response=False
        )

    @patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
    @patch("bookwyrm.activitystreams.populate_stream_task.delay")
    def test_followers_page_blocked(self, *_):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Relationships.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        self.rat.blocks.add(self.local_user)
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            with self.assertRaises(Http404):
                view(request, "rat", "followers")

    def test_following_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Relationships.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", "following")

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_following_page_json(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Relationships.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.relationships.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse", "following")

        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_following_page_anonymous(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Relationships.as_view()
        request = self.factory.get("")
        request.user = self.anonymous_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse", "following")

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_following_page_blocked(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Relationships.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        self.rat.blocks.add(self.local_user)
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            with self.assertRaises(Http404):
                view(request, "rat", "following")

    def test_hide_suggestions(self):
        """update suggestions settings"""
        self.assertTrue(self.local_user.show_suggested_users)
        request = self.factory.post("")
        request.user = self.local_user

        result = views.hide_suggestions(request)
        self.assertEqual(result.status_code, 302)

        self.local_user.refresh_from_db()
        self.assertFalse(self.local_user.show_suggested_users)

    def test_user_redirect(self):
        """test the basic redirect"""
        request = self.factory.get("@mouse")
        request.user = self.anonymous_user
        result = views.user_redirect(request, "mouse")

        self.assertEqual(result.status_code, 302)

    def test_reviews_comments_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.UserReviewsComments.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user
        result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
