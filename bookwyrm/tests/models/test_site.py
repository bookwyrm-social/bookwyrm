""" testing models """
from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from bookwyrm import models, settings


class SiteModels(TestCase):
    """tests for site models"""

    def setUp(self):
        """we need basic test data and mocks"""
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

    def test_site_settings_absent(self):
        """create and load site settings"""
        self.assertFalse(models.SiteSettings.objects.exists())
        result = models.SiteSettings.get()
        self.assertTrue(models.SiteSettings.objects.exists())
        self.assertEqual(result.id, 1)
        self.assertEqual(result.name, "BookWyrm")

    def test_site_settings_present(self):
        """load site settings"""
        models.SiteSettings.objects.create(id=1, name="Fish Town")
        result = models.SiteSettings.get()
        self.assertEqual(result.id, 1)
        self.assertEqual(result.name, "Fish Town")
        self.assertEqual(models.SiteSettings.objects.all().count(), 1)

    def test_site_invite(self):
        """default invite"""
        invite = models.SiteInvite.objects.create(
            user=self.local_user,
        )
        self.assertTrue(invite.valid())

    def test_site_invite_with_limit(self):
        """with use limit"""
        # valid
        invite = models.SiteInvite.objects.create(user=self.local_user, use_limit=1)
        self.assertTrue(invite.valid())

        # invalid
        invite = models.SiteInvite.objects.create(user=self.local_user, use_limit=0)
        self.assertFalse(invite.valid())
        invite = models.SiteInvite.objects.create(
            user=self.local_user, use_limit=1, times_used=1
        )
        self.assertFalse(invite.valid())

    def test_site_invite_with_expiry(self):
        """with expiration date"""
        date = timezone.now() + timedelta(days=1)
        invite = models.SiteInvite.objects.create(user=self.local_user, expiry=date)
        self.assertTrue(invite.valid())

        date = timezone.now() - timedelta(days=1)
        invite = models.SiteInvite.objects.create(user=self.local_user, expiry=date)
        self.assertFalse(invite.valid())

    def test_site_invite_link(self):
        """invite link generator"""
        invite = models.SiteInvite.objects.create(user=self.local_user, code="hello")
        self.assertEqual(invite.link, f"https://{settings.DOMAIN}/invite/hello")

    def test_invite_request(self):
        """someone wants an invite"""
        # normal and good
        request = models.InviteRequest.objects.create(email="mouse.reeve@gmail.com")
        self.assertIsNone(request.invite)

        # already in use
        with self.assertRaises(IntegrityError):
            request = models.InviteRequest.objects.create(email="mouse@mouse.com")

    def test_password_reset(self):
        """password reset token"""
        token = models.PasswordReset.objects.create(user=self.local_user, code="hello")
        self.assertTrue(token.valid())
        self.assertEqual(token.link, f"https://{settings.DOMAIN}/password-reset/hello")

    @patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
    @patch("bookwyrm.suggested_users.remove_user_task.delay")
    @patch("bookwyrm.activitystreams.populate_stream_task.delay")
    @patch("bookwyrm.lists_stream.populate_lists_task.delay")
    def test_change_confirmation_scheme(self, *_):
        """Switch from requiring email confirmation to not"""
        site = models.SiteSettings.objects.create(
            id=1, name="Fish Town", require_confirm_email=True
        )
        banned_user = models.User.objects.create_user(
            "rat@local.com",
            "rat@rat.com",
            "ratword",
            local=True,
            localname="rat",
            remote_id="https://example.com/users/rat",
            confirmation_code="HELLO",
        )
        banned_user.is_active = False
        banned_user.deactivation_reason = "banned"
        banned_user.save(broadcast=False)

        pending_user = models.User.objects.create_user(
            "nutria@local.com",
            "nutria@nutria.com",
            "nutriaword",
            local=True,
            localname="nutria",
            remote_id="https://example.com/users/nutria",
            confirmation_code="HELLO",
        )
        pending_user.is_active = False
        pending_user.deactivation_reason = "pending"
        pending_user.save(broadcast=False)
        site.require_confirm_email = False
        site.save()

        pending_user.refresh_from_db()
        self.assertTrue(pending_user.is_active)
        self.assertIsNone(pending_user.deactivation_reason)

        banned_user.refresh_from_db()
        self.assertFalse(banned_user.is_active)
        self.assertIsNotNone(banned_user.deactivation_reason)
