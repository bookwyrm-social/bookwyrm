"""test bookwyrm user export functions"""
import datetime
import json
from unittest.mock import patch

from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase
from django.utils import timezone

from bookwyrm import models
import bookwyrm.models.bookwyrm_export_job as export_job


class BookwyrmExport(TestCase):
    """testing user export functions"""

    def setUp(self):
        """lots of stuff to set up for a user export"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"), patch(
            "bookwyrm.suggested_users.rerank_user_task.delay"
        ), patch(
            "bookwyrm.lists_stream.remove_list_task.delay"
        ), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ), patch(
            "bookwyrm.activitystreams.add_book_statuses_task"
        ):

            self.local_user = models.User.objects.create_user(
                "mouse",
                "mouse@mouse.mouse",
                "password",
                local=True,
                localname="mouse",
                name="Mouse",
                summary="I'm a real bookmouse",
                manually_approves_followers=False,
                hide_follows=False,
                show_goal=False,
                show_suggested_users=False,
                discoverable=True,
                preferred_timezone="America/Los Angeles",
                default_post_privacy="followers",
            )

            self.rat_user = models.User.objects.create_user(
                "rat", "rat@rat.rat", "ratword", local=True, localname="rat"
            )

            self.badger_user = models.User.objects.create_user(
                "badger",
                "badger@badger.badger",
                "badgerword",
                local=True,
                localname="badger",
            )

            models.AnnualGoal.objects.create(
                user=self.local_user,
                year=timezone.now().year,
                goal=128937123,
                privacy="followers",
            )

            self.list = models.List.objects.create(
                name="My excellent list",
                user=self.local_user,
                remote_id="https://local.lists/1111",
            )

            self.saved_list = models.List.objects.create(
                name="My cool list",
                user=self.rat_user,
                remote_id="https://local.lists/9999",
            )

            self.local_user.saved_lists.add(self.saved_list)
            self.local_user.blocks.add(self.badger_user)
            self.rat_user.followers.add(self.local_user)

            # book, edition, author
            self.author = models.Author.objects.create(name="Sam Zhu")
            self.work = models.Work.objects.create(
                title="Example Work", remote_id="https://example.com/book/1"
            )
            self.edition = models.Edition.objects.create(
                title="Example Edition", parent_work=self.work
            )

            self.edition.authors.add(self.author)

            # readthrough
            self.readthrough_start = timezone.now()
            finish = self.readthrough_start + datetime.timedelta(days=1)
            models.ReadThrough.objects.create(
                user=self.local_user,
                book=self.edition,
                start_date=self.readthrough_start,
                finish_date=finish,
            )

            # shelve
            read_shelf = models.Shelf.objects.get(
                user=self.local_user, identifier="read"
            )
            models.ShelfBook.objects.create(
                book=self.edition, shelf=read_shelf, user=self.local_user
            )

            # add to list
            models.ListItem.objects.create(
                book_list=self.list,
                user=self.local_user,
                book=self.edition,
                approved=True,
                order=1,
            )

            # review
            models.Review.objects.create(
                content="awesome",
                name="my review",
                rating=5,
                user=self.local_user,
                book=self.edition,
            )
            # comment
            models.Comment.objects.create(
                content="ok so far",
                user=self.local_user,
                book=self.edition,
                progress=15,
            )
            # quote
            models.Quotation.objects.create(
                content="check this out",
                quote="A rose by any other name",
                user=self.local_user,
                book=self.edition,
            )

    def test_json_export_user_settings(self):
        """Test the json export function for basic user info"""
        data = export_job.json_export(self.local_user)
        user_data = json.loads(data)
        self.assertEqual(user_data["preferredUsername"], "mouse")
        self.assertEqual(user_data["name"], "Mouse")
        self.assertEqual(user_data["summary"], "<p>I'm a real bookmouse</p>")
        self.assertEqual(user_data["manuallyApprovesFollowers"], False)
        self.assertEqual(user_data["hideFollows"], False)
        self.assertEqual(user_data["discoverable"], True)
        self.assertEqual(user_data["settings"]["show_goal"], False)
        self.assertEqual(user_data["settings"]["show_suggested_users"], False)
        self.assertEqual(
            user_data["settings"]["preferred_timezone"], "America/Los Angeles"
        )
        self.assertEqual(user_data["settings"]["default_post_privacy"], "followers")

    def test_json_export_extended_user_data(self):
        """Test the json export function for other non-book user info"""
        data = export_job.json_export(self.local_user)
        json_data = json.loads(data)

        # goal
        self.assertEqual(len(json_data["goals"]), 1)
        self.assertEqual(json_data["goals"][0]["goal"], 128937123)
        self.assertEqual(json_data["goals"][0]["year"], timezone.now().year)
        self.assertEqual(json_data["goals"][0]["privacy"], "followers")

        # saved lists
        self.assertEqual(len(json_data["saved_lists"]), 1)
        self.assertEqual(json_data["saved_lists"][0], "https://local.lists/9999")

        # follows
        self.assertEqual(len(json_data["follows"]), 1)
        self.assertEqual(json_data["follows"][0], "https://your.domain.here/user/rat")
        # blocked users
        self.assertEqual(len(json_data["blocks"]), 1)
        self.assertEqual(json_data["blocks"][0], "https://your.domain.here/user/badger")

    def test_json_export_books(self):
        """Test the json export function for extended user info"""

        data = export_job.json_export(self.local_user)
        json_data = json.loads(data)
        start_date = json_data["books"][0]["readthroughs"][0]["start_date"]

        self.assertEqual(len(json_data["books"]), 1)
        self.assertEqual(json_data["books"][0]["edition"]["title"], "Example Edition")
        self.assertEqual(len(json_data["books"][0]["authors"]), 1)
        self.assertEqual(json_data["books"][0]["authors"][0]["name"], "Sam Zhu")

        self.assertEqual(
            f'"{start_date}"', DjangoJSONEncoder().encode(self.readthrough_start)
        )

        self.assertEqual(json_data["books"][0]["shelves"][0]["name"], "Read")

        self.assertEqual(len(json_data["books"][0]["lists"]), 1)
        self.assertEqual(json_data["books"][0]["lists"][0]["name"], "My excellent list")
        self.assertEqual(
            json_data["books"][0]["lists"][0]["list_item"]["book"],
            self.edition.remote_id,
            self.edition.id,
        )

        self.assertEqual(len(json_data["books"][0]["reviews"]), 1)
        self.assertEqual(len(json_data["books"][0]["comments"]), 1)
        self.assertEqual(len(json_data["books"][0]["quotations"]), 1)

        self.assertEqual(json_data["books"][0]["reviews"][0]["name"], "my review")
        self.assertEqual(
            json_data["books"][0]["reviews"][0]["content"], "<p>awesome</p>"
        )
        self.assertEqual(json_data["books"][0]["reviews"][0]["rating"], 5.0)

        self.assertEqual(
            json_data["books"][0]["comments"][0]["content"], "<p>ok so far</p>"
        )
        self.assertEqual(json_data["books"][0]["comments"][0]["progress"], 15)
        self.assertEqual(json_data["books"][0]["comments"][0]["progress_mode"], "PG")

        self.assertEqual(
            json_data["books"][0]["quotations"][0]["content"], "<p>check this out</p>"
        )
        self.assertEqual(
            json_data["books"][0]["quotations"][0]["quote"],
            "<p>A rose by any other name</p>",
        )
