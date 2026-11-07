"""Tests for deleting unconfirmed accounts."""

from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from bookwyrm import models
from bookwyrm.management.commands.yeet_stale_accounts import Command, account_row
from bookwyrm.settings import DOMAIN


def _create_user(localname, email, **kwargs):
    return models.User.objects.create_user(
        kwargs.pop("username", f"{localname}@{DOMAIN}"),
        email,
        "password",
        localname=localname,
        local=kwargs.pop("local", True),
        bookwyrm_user=False,
        is_active=kwargs.pop("is_active", False),
        deactivation_reason=kwargs.pop("deactivation_reason", "pending"),
        **kwargs,
    )


@patch("bookwyrm.suggested_users.rerank_suggestions_task.delay")
@patch("bookwyrm.activitystreams.populate_stream_task.delay")
@patch("bookwyrm.lists_stream.populate_lists_task.delay")
class YeetStaleAccounts(TestCase):
    """Remove local users who never confirmed their email."""

    def setUp(self):
        self.stdout = StringIO()
        self.command = Command(stdout=self.stdout)

    def test_account_row_uses_day_count(self, *_):
        """Match the requested preview line, including a single day."""
        now = timezone.now()
        older = SimpleNamespace(
            localname="spamMaster3000",
            username="ignored",
            email="fsadfasdf@gmail.com",
            created_date=now - timedelta(days=29, hours=3),
        )
        single = SimpleNamespace(
            localname="one",
            username="ignored",
            email="one@example.com",
            created_date=now - timedelta(days=1, hours=2),
        )
        self.assertEqual(
            account_row(older, now=now),
            "spamMaster3000 - fsadfasdf@gmail.com - 29 days ago",
        )
        self.assertEqual(
            account_row(single, now=now),
            "one - one@example.com - 1 day ago",
        )

    def test_deletes_unconfirmed_accounts(self, *_):
        """Hard-delete pending users, and the shelves created with them."""
        stale = _create_user("spamMaster3000", "fsadfasdf@gmail.com")
        stale.created_date = timezone.now() - timedelta(days=29)
        stale.save(update_fields=["created_date"])
        shelf_ids = list(stale.shelf_set.values_list("id", flat=True))
        key_pair_id = stale.key_pair_id
        self.assertEqual(len(shelf_ids), 4)

        kept = _create_user(
            "reader",
            "reader@example.com",
            is_active=True,
            deactivation_reason=None,
        )
        deactivated = _create_user(
            "paused",
            "paused@example.com",
            deactivation_reason="self_deactivation",
        )

        self.command.handle(yes=True, days=0)

        output = self.stdout.getvalue()
        self.assertIn("This run would clean the following accounts:", output)
        self.assertIn("Username - Email - Registration date", output)
        self.assertIn(
            "spamMaster3000 - fsadfasdf@gmail.com - 29 days ago",
            output,
        )
        self.assertIn(
            "Permanently delete those unconfirmed users? This action cannot be undone!",
            output,
        )
        self.assertIn("Deleted 1 unconfirmed account.", output)
        self.assertFalse(models.User.objects.filter(id=stale.id).exists())
        self.assertFalse(models.Shelf.objects.filter(id__in=shelf_ids).exists())
        self.assertFalse(models.KeyPair.objects.filter(id=key_pair_id).exists())
        self.assertTrue(models.User.objects.filter(id=kept.id).exists())
        self.assertTrue(models.User.objects.filter(id=deactivated.id).exists())
        self.assertEqual(kept.shelf_set.count(), 4)

    def test_prompt_no_leaves_accounts(self, *_):
        """The default answer is no."""
        user = _create_user("spamMaster3000", "fsadfasdf@gmail.com")
        with patch("builtins.input", return_value=""):
            self.command.handle(yes=False, days=0)
        self.assertTrue(models.User.objects.filter(id=user.id).exists())
        self.assertIn("No accounts were deleted.", self.stdout.getvalue())

    def test_prompt_yes_deletes(self, *_):
        user = _create_user("spamMaster3000", "fsadfasdf@gmail.com")
        with patch("builtins.input", return_value="y"):
            self.command.handle(yes=False, days=0)
        self.assertFalse(models.User.objects.filter(id=user.id).exists())

    def test_days_filter(self, *_):
        """--days keeps recent unconfirmed signups."""
        recent = _create_user("newspam", "new@example.com")
        old = _create_user("oldspam", "old@example.com")
        old.created_date = timezone.now() - timedelta(days=42)
        old.save(update_fields=["created_date"])

        self.command.handle(yes=True, days=30)

        self.assertTrue(models.User.objects.filter(id=recent.id).exists())
        self.assertFalse(models.User.objects.filter(id=old.id).exists())
        self.assertIn(
            "oldspam - old@example.com - 42 days ago",
            self.stdout.getvalue(),
        )
        self.assertNotIn("newspam", self.stdout.getvalue())

    def test_no_matching_accounts(self, *_):
        self.command.handle(yes=True, days=0)
        self.assertEqual(
            self.stdout.getvalue().strip(),
            "No unconfirmed accounts to clean up.",
        )

    @patch("bookwyrm.models.user.set_remote_server.delay")
    def test_ignores_remote_users(self, *_):
        remote = _create_user(
            "rat",
            "rat@rat.rat",
            username="rat",
            local=False,
            remote_id="https://example.com/users/rat",
        )
        self.command.handle(yes=True, days=0)
        self.assertTrue(models.User.objects.filter(id=remote.id).exists())
        self.assertIn("No unconfirmed accounts to clean up.", self.stdout.getvalue())
