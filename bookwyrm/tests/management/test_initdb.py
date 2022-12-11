""" test populating user streams """
from django.contrib.auth.models import Group, Permission
from django.test import TestCase

from bookwyrm import models
from bookwyrm.management.commands import initdb


class InitDB(TestCase):
    """gotta init that db"""

    def test_init_groups(self):
        """Create groups"""
        initdb.init_groups()
        self.assertEqual(Group.objects.count(), 4)
        self.assertTrue(Group.objects.filter(name="admin").exists())
        self.assertTrue(Group.objects.filter(name="moderator").exists())
        self.assertTrue(Group.objects.filter(name="editor").exists())

    def test_init_permissions(self):
        """User permissions"""
        initdb.init_groups()
        initdb.init_permissions()

        group = Group.objects.get(name="admin")
        self.assertTrue(
            group.permissions.filter(codename="edit_instance_settings").exists()
        )
        self.assertTrue(group.permissions.filter(codename="set_user_group").exists())
        self.assertTrue(
            group.permissions.filter(codename="control_federation").exists()
        )
        self.assertTrue(group.permissions.filter(codename="create_invites").exists())
        self.assertTrue(group.permissions.filter(codename="moderate_user").exists())
        self.assertTrue(group.permissions.filter(codename="moderate_post").exists())
        self.assertTrue(group.permissions.filter(codename="edit_book").exists())

        group = Group.objects.get(name="moderator")
        self.assertTrue(group.permissions.filter(codename="set_user_group").exists())
        self.assertTrue(
            group.permissions.filter(codename="control_federation").exists()
        )
        self.assertTrue(group.permissions.filter(codename="create_invites").exists())
        self.assertTrue(group.permissions.filter(codename="moderate_user").exists())
        self.assertTrue(group.permissions.filter(codename="moderate_post").exists())
        self.assertTrue(group.permissions.filter(codename="edit_book").exists())

        group = Group.objects.get(name="editor")
        self.assertTrue(group.permissions.filter(codename="edit_book").exists())

    def test_init_connectors(self):
        """Outside data sources"""
        initdb.init_connectors()
        self.assertTrue(
            models.Connector.objects.filter(identifier="bookwyrm.social").exists()
        )
        self.assertTrue(
            models.Connector.objects.filter(identifier="inventaire.io").exists()
        )
        self.assertTrue(
            models.Connector.objects.filter(identifier="openlibrary.org").exists()
        )

    def test_init_settings(self):
        """Create the settings file"""
        initdb.init_settings()
        settings = models.SiteSettings.objects.get()
        self.assertEqual(settings.name, "BookWyrm")

    def test_init_link_domains(self):
        """Common trusted domains for links"""
        initdb.init_link_domains()
        self.assertTrue(
            models.LinkDomain.objects.filter(
                status="approved", domain="standardebooks.org"
            ).exists()
        )
        self.assertTrue(
            models.LinkDomain.objects.filter(
                status="approved", domain="theanarchistlibrary.org"
            ).exists()
        )

    def test_command_no_args(self):
        """command line calls"""
        command = initdb.Command()
        command.handle()

        # everything should have been called
        self.assertEqual(Group.objects.count(), 4)
        self.assertTrue(Permission.objects.exists())
        self.assertEqual(models.Connector.objects.count(), 3)
        self.assertEqual(models.SiteSettings.objects.count(), 1)
        self.assertEqual(models.LinkDomain.objects.count(), 5)

    def test_command_with_args(self):
        """command line calls"""
        command = initdb.Command()
        command.handle(limit="group")

        # everything should have been called
        self.assertEqual(Group.objects.count(), 4)
        self.assertEqual(models.Connector.objects.count(), 0)
        self.assertEqual(models.SiteSettings.objects.count(), 0)
        self.assertEqual(models.LinkDomain.objects.count(), 0)

    def test_command_invalid_args(self):
        """command line calls"""
        command = initdb.Command()
        with self.assertRaises(Exception):
            command.handle(limit="sdkfjhsdkjf")
