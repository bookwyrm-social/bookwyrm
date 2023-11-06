""" testing migrations """
from unittest.mock import patch

from django.test import TestCase
from django.db.migrations.executor import MigrationExecutor
from django.db import connection

from bookwyrm import models
from bookwyrm.management.commands import initdb
from bookwyrm.settings import DOMAIN

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
class EraseDeletedUserDataMigration(TestCase):

    migrate_from = "0183_auto_20231105_1607"
    migrate_to = "0184_auto_20231106_0421"

    # pylint: disable=invalid-name
    def setUp(self):
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.active_user = models.User.objects.create_user(
                f"activeuser@{DOMAIN}",
                "activeuser@activeuser.activeuser",
                "activeuserword",
                local=True,
                localname="active",
                name="a name",
            )
            self.inactive_user = models.User.objects.create_user(
                f"inactiveuser@{DOMAIN}",
                "inactiveuser@inactiveuser.inactiveuser",
                "inactiveuserword",
                local=True,
                localname="inactive",
                is_active=False,
                deactivation_reason="self_deactivation",
                name="name name",
            )
            self.deleted_user = models.User.objects.create_user(
                f"deleteduser@{DOMAIN}",
                "deleteduser@deleteduser.deleteduser",
                "deleteduserword",
                local=True,
                localname="deleted",
                is_active=False,
                deactivation_reason="self_deletion",
                name="cool name",
            )
        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch("bookwyrm.activitystreams.add_status_task.delay"):
            self.active_status = models.Status.objects.create(
                user=self.active_user, content="don't delete me"
            )
            self.inactive_status = models.Status.objects.create(
                user=self.inactive_user, content="also don't delete me"
            )
            self.deleted_status = models.Status.objects.create(
                user=self.deleted_user, content="yes, delete me"
            )

        initdb.init_groups()
        initdb.init_permissions()

        self.migrate_from = [("bookwyrm", self.migrate_from)]
        self.migrate_to = [("bookwyrm", self.migrate_to)]
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        # Reverse to the original migration
        executor.migrate(self.migrate_from)

        self.setUpBeforeMigration(old_apps)

        # Run the migration to test
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # reload.
        with patch("bookwyrm.activitystreams.remove_status_task.delay"):
            executor.migrate(self.migrate_to)

        self.apps = executor.loader.project_state(self.migrate_to).apps

    def setUpBeforeMigration(self, apps):
        pass

    def test_user_data_deleted(self):
        """Make sure that only the right data was deleted"""
        self.active_user.refresh_from_db()
        self.inactive_user.refresh_from_db()
        self.deleted_user.refresh_from_db()
        self.active_status.refresh_from_db()
        self.inactive_status.refresh_from_db()
        self.deleted_status.refresh_from_db()

        self.assertTrue(self.active_user.is_active)
        self.assertFalse(self.active_user.is_deleted)
        self.assertEqual(self.active_user.name, "a name")
        self.assertNotEqual(self.deleted_user.email, "activeuser@activeuser.activeuser")
        self.assertFalse(self.active_status.deleted)
        self.assertEqual(self.active_status.content, "don't delete me")

        self.assertFalse(self.inactive_user.is_active)
        self.assertFalse(self.inactive_user.is_deleted)
        self.assertEqual(self.inactive_user.name, "name name")
        self.assertNotEqual(
            self.deleted_user.email, "inactiveuser@inactiveuser.inactiveuser"
        )
        self.assertFalse(self.inactive_status.deleted)
        self.assertEqual(self.inactive_status.content, "also don't delete me")

        self.assertFalse(self.deleted_user.is_active)
        self.assertTrue(self.deleted_user.is_deleted)
        self.assertIsNone(self.deleted_user.name)
        self.assertNotEqual(
            self.deleted_user.email, "deleteduser@deleteduser.deleteduser"
        )
        self.assertTrue(self.deleted_status.deleted)
        self.assertIsNone(self.deleted_status.content)
