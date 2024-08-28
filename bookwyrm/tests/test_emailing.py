""" test creating emails """
from unittest.mock import patch

from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import emailing, models


@patch("bookwyrm.emailing.send_email.delay")
class Emailing(TestCase):
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
        """other test data"""
        self.factory = RequestFactory()

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

    def test_password_reset_email(self, _):
        """load the password reset email"""
        reset = models.PasswordReset.objects.create(user=self.local_user)

        with patch("bookwyrm.emailing.send_email") as email_mock:
            emailing.password_reset_email(reset)

        self.assertEqual(email_mock.call_count, 1)
        args = email_mock.call_args[0]
        self.assertEqual(args[0], "mouse@mouse.mouse")
        self.assertEqual(args[1], "Reset your BookWyrm password")
        self.assertEqual(len(args), 4)
