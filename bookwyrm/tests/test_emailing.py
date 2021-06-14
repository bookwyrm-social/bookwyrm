""" test creating emails """
from unittest.mock import patch

from django.test import TestCase
from django.test.client import RequestFactory
import responses

from bookwyrm import emailing, models


@patch("bookwyrm.emailing.send_email.delay")
class Emailing(TestCase):
    """every response to a get request, html or json"""

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
        models.SiteSettings.objects.create()

    def test_invite_email(self, email_mock):
        """load the invite email"""
        invite_request = models.InviteRequest.objects.create(
            email="test@email.com",
            invite=models.SiteInvite.objects.create(user=self.local_user),
        )

        emailing.invite_email(invite_request)

        self.assertEqual(email_mock.call_count, 1)
        args = email_mock.call_args[0]
        self.assertEqual(args[0], "test@email.com")
        self.assertEqual(args[1], "You're invited to join BookWyrm!")
        self.assertEqual(len(args), 4)

    def test_password_reset_email(self, email_mock):
        """load the password reset email"""
        reset = models.PasswordReset.objects.create(user=self.local_user)
        emailing.password_reset_email(reset)

        self.assertEqual(email_mock.call_count, 1)
        args = email_mock.call_args[0]
        self.assertEqual(args[0], "mouse@mouse.mouse")
        self.assertEqual(args[1], "Reset your BookWyrm password")
        self.assertEqual(len(args), 4)
