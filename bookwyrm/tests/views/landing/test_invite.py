""" test for app action functionality """
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models
from bookwyrm import views
from bookwyrm.tests.validate_html import validate_html


class InviteViews(TestCase):
    """every response to a get request, html or json"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
            )
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_invite_page(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Invite.as_view()
        models.SiteInvite.objects.create(code="hi", user=self.local_user)
        request = self.factory.get("")
        request.user = AnonymousUser
        # why?? this is annoying.
        request.user.is_authenticated = False
        with patch("bookwyrm.models.site.SiteInvite.valid") as invite:
            invite.return_value = True
            result = view(request, "hi")
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_manage_invites(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ManageInvites.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_manage_invites_post(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ManageInvites.as_view()
        form = forms.CreateInviteForm()
        form.data["use_limit"] = 3
        form.data["expiry"] = ""
        request = self.factory.post("", form.data)
        request.user = self.local_user
        request.user.is_superuser = True

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        invite = models.SiteInvite.objects.get()
        self.assertEqual(invite.use_limit, 3)
        self.assertIsNone(invite.expiry)

    def test_invite_request(self):
        """request to join a server"""
        form = forms.InviteRequestForm()
        form.data["email"] = "new@user.email"

        view = views.InviteRequest.as_view()
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request)
        validate_html(result.render())

        req = models.InviteRequest.objects.get()
        self.assertEqual(req.email, "new@user.email")

    def test_invite_request_email_taken(self):
        """request to join a server with an existing user email"""
        form = forms.InviteRequestForm()
        form.data["email"] = "mouse@mouse.mouse"

        view = views.InviteRequest.as_view()
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request)
        validate_html(result.render())

        # no request created
        self.assertFalse(models.InviteRequest.objects.exists())

    def test_manage_invite_requests(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.ManageInviteRequests.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        # now with data
        models.InviteRequest.objects.create(email="fish@example.com")
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_manage_invite_requests_send(self):
        """send an invite"""
        req = models.InviteRequest.objects.create(email="fish@example.com")

        view = views.ManageInviteRequests.as_view()
        request = self.factory.post("", {"invite-request": req.id})
        request.user = self.local_user
        request.user.is_superuser = True

        with patch("bookwyrm.emailing.send_email.delay") as mock:
            view(request)
            self.assertEqual(mock.call_count, 1)
        req.refresh_from_db()
        self.assertIsNotNone(req.invite)

    def test_ignore_invite_request(self):
        """don't invite that jerk"""
        req = models.InviteRequest.objects.create(email="fish@example.com")

        view = views.ignore_invite_request
        request = self.factory.post("", {"invite-request": req.id})
        request.user = self.local_user
        request.user.is_superuser = True

        view(request)
        req.refresh_from_db()
        self.assertTrue(req.ignored)

        view(request)
        req.refresh_from_db()
        self.assertFalse(req.ignored)
