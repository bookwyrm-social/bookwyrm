""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http.response import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.activitypub import ActivitypubResponse


class UserViews(TestCase):
    """view user and edit profile"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
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
        self.book = models.Edition.objects.create(title="test")
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.delay"):
            models.ShelfBook.objects.create(
                book=self.book,
                user=self.local_user,
                shelf=self.local_user.shelf_set.first(),
            )

        models.SiteSettings.objects.create()
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False

    def test_user_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.User.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse")
        self.assertIsInstance(result, ActivitypubResponse)
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
        view = views.Followers.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse")
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_followers_page_blocked(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Followers.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        self.rat.blocks.add(self.local_user)
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            with self.assertRaises(Http404):
                view(request, "rat")

    def test_following_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Following.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            result = view(request, "mouse")
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = True
            result = view(request, "mouse")
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

    def test_following_page_blocked(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Following.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        self.rat.blocks.add(self.local_user)
        with patch("bookwyrm.views.user.is_api_request") as is_api:
            is_api.return_value = False
            with self.assertRaises(Http404):
                view(request, "rat")
