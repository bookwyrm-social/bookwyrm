""" testing models """
from unittest.mock import patch
from django.test import TestCase

from bookwyrm import models


@patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async")
class Group(TestCase):
    """some activitypub oddness ahead"""

    def setUp(self):
        """Set up for tests"""

        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.owner_user = models.User.objects.create_user(
                "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
            )

        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.rat = models.User.objects.create_user(
                "rat", "rat@rat.rat", "ratword", local=True, localname="rat"
            )

        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.badger = models.User.objects.create_user(
                "badger",
                "badger@badger.badger",
                "badgerword",
                local=True,
                localname="badger",
            )

        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ):
            self.capybara = models.User.objects.create_user(
                "capybara",
                "capybara@capybara.capybara",
                "capybaraword",
                local=True,
                localname="capybara",
            )

        self.public_group = models.Group.objects.create(
            name="Public Group",
            description="Initial description",
            user=self.owner_user,
            privacy="public",
        )

        self.private_group = models.Group.objects.create(
            name="Private Group",
            description="Top secret",
            user=self.owner_user,
            privacy="direct",
        )

        self.followers_only_group = models.Group.objects.create(
            name="Followers Group",
            description="No strangers",
            user=self.owner_user,
            privacy="followers",
        )

        models.GroupMember.objects.create(group=self.private_group, user=self.badger)
        models.GroupMember.objects.create(
            group=self.followers_only_group, user=self.badger
        )
        models.GroupMember.objects.create(group=self.public_group, user=self.capybara)

    def test_group_members_can_see_private_groups(self, _):
        """direct privacy group should not be excluded from group listings for group
        members viewing"""

        rat_groups = models.Group.privacy_filter(self.rat).all()
        badger_groups = models.Group.privacy_filter(self.badger).all()

        self.assertFalse(self.private_group in rat_groups)
        self.assertTrue(self.private_group in badger_groups)

    def test_group_members_can_see_followers_only_lists(self, _):
        """follower-only group booklists should not be excluded from group booklist
        listing for group members who do not follower list owner"""

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            followers_list = models.List.objects.create(
                name="Followers List",
                curation="group",
                privacy="followers",
                group=self.public_group,
                user=self.owner_user,
            )

        rat_lists = models.List.privacy_filter(self.rat).all()
        badger_lists = models.List.privacy_filter(self.badger).all()
        capybara_lists = models.List.privacy_filter(self.capybara).all()

        self.assertFalse(followers_list in rat_lists)
        self.assertFalse(followers_list in badger_lists)
        self.assertTrue(followers_list in capybara_lists)

    def test_group_members_can_see_private_lists(self, _):
        """private group booklists should not be excluded from group booklist listing
        for group members"""

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):

            private_list = models.List.objects.create(
                name="Private List",
                privacy="direct",
                curation="group",
                group=self.public_group,
                user=self.owner_user,
            )

        rat_lists = models.List.privacy_filter(self.rat).all()
        badger_lists = models.List.privacy_filter(self.badger).all()
        capybara_lists = models.List.privacy_filter(self.capybara).all()

        self.assertFalse(private_list in rat_lists)
        self.assertFalse(private_list in badger_lists)
        self.assertTrue(private_list in capybara_lists)
