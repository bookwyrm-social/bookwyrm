"""test bookwyrm user export functions"""
import datetime
import json
from unittest.mock import patch

from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase
from django.test.utils import override_settings

from django.utils import timezone

from bookwyrm import models
import bookwyrm.models.bookwyrm_export_job as export_job


class BookwyrmExportJob(TestCase):
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

            self.job = models.BookwyrmExportJob.objects.create(user=self.local_user)

    def test_export_saved_lists_task(self):
        """test saved list task"""

        with patch("bookwyrm.models.bookwyrm_export_job.json_export.delay"):
            models.bookwyrm_export_job.start_export_task(
                job_id=self.job.id, no_children=False
            )
            print(self.job.user)
            print(self.job.export_data)
            print(self.job.export_json)
            # IDK how to test this...
            pass
