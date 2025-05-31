"""test bookwyrm user export functions"""
import datetime
import json
import pathlib

from unittest.mock import patch

from django.utils import timezone
from django.test import TestCase

from bookwyrm import models
from bookwyrm.utils.tar import BookwyrmTarFile


class BookwyrmExportJob(TestCase):
    """testing user export functions"""

    def setUp(self):
        """lots of stuff to set up for a user export"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
            patch("bookwyrm.suggested_users.rerank_user_task.delay"),
            patch("bookwyrm.lists_stream.remove_list_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
            patch("bookwyrm.activitystreams.add_book_statuses_task"),
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
            avatar_path = pathlib.Path(__file__).parent.joinpath(
                "../../static/images/default_avi.jpg"
            )
            with open(avatar_path, "rb") as avatar_file:
                self.local_user.avatar.save("mouse-avatar.jpg", avatar_file)

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

            # edition cover
            cover_path = pathlib.Path(__file__).parent.joinpath(
                "../../static/images/default_avi.jpg"
            )
            with open(cover_path, "rb") as cover_file:
                self.edition.cover.save("tèst.jpg", cover_file)

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
            # deleted comment
            models.Comment.objects.create(
                content="so far",
                user=self.local_user,
                book=self.edition,
                progress=5,
                deleted=True,
            )
            # quote
            models.Quotation.objects.create(
                content="check this out",
                quote="A rose by any other name",
                user=self.local_user,
                book=self.edition,
            )
            # deleted quote
            models.Quotation.objects.create(
                content="check this out",
                quote="A rose by any other name",
                user=self.local_user,
                book=self.edition,
                deleted=True,
            )

            self.job = models.BookwyrmExportJob.objects.create(user=self.local_user)

            # run the first stage of the export
            with patch("bookwyrm.models.bookwyrm_export_job.create_archive_task.delay"):
                models.bookwyrm_export_job.create_export_json_task(job_id=self.job.id)
            self.job.refresh_from_db()

    def test_add_book_to_user_export_job(self):
        """does AddBookToUserExportJob ...add the book to the export?"""
        self.assertIsNotNone(self.job.export_json["books"])
        self.assertEqual(len(self.job.export_json["books"]), 1)
        book = self.job.export_json["books"][0]

        self.assertEqual(book["work"]["id"], self.work.remote_id)
        self.assertEqual(len(book["authors"]), 1)
        self.assertEqual(len(book["shelves"]), 1)
        self.assertEqual(len(book["lists"]), 1)
        self.assertEqual(len(book["comments"]), 1)
        self.assertEqual(len(book["reviews"]), 1)
        self.assertEqual(len(book["quotations"]), 1)
        self.assertEqual(len(book["readthroughs"]), 1)

        self.assertEqual(book["edition"]["id"], self.edition.remote_id)
        self.assertEqual(
            book["edition"]["cover"]["url"], f"images/{self.edition.cover.name}"
        )

    def test_start_export_task(self):
        """test saved list task saves initial json and data"""
        self.assertIsNotNone(self.job.export_data)
        self.assertIsNotNone(self.job.export_json)
        self.assertEqual(self.job.export_json["name"], self.local_user.name)

    def test_export_saved_lists_task(self):
        """test export_saved_lists_task adds the saved lists"""
        self.assertIsNotNone(self.job.export_json["saved_lists"])
        self.assertEqual(
            self.job.export_json["saved_lists"][0], self.saved_list.remote_id
        )

    def test_export_follows_task(self):
        """test export_follows_task adds the follows"""
        self.assertIsNotNone(self.job.export_json["follows"])
        self.assertEqual(self.job.export_json["follows"][0], self.rat_user.remote_id)

    def test_export_blocks_task(self):
        """test export_blocks_task adds the blocks"""
        self.assertIsNotNone(self.job.export_json["blocks"])
        self.assertEqual(self.job.export_json["blocks"][0], self.badger_user.remote_id)

    def test_export_reading_goals_task(self):
        """test export_reading_goals_task adds the goals"""
        self.assertIsNotNone(self.job.export_json["goals"])
        self.assertEqual(self.job.export_json["goals"][0]["goal"], 128937123)

    def test_json_export(self):
        """test json_export job adds settings"""
        self.assertIsNotNone(self.job.export_json["settings"])
        self.assertFalse(self.job.export_json["settings"]["show_goal"])
        self.assertEqual(
            self.job.export_json["settings"]["preferred_timezone"],
            "America/Los Angeles",
        )
        self.assertEqual(
            self.job.export_json["settings"]["default_post_privacy"], "followers"
        )
        self.assertFalse(self.job.export_json["settings"]["show_suggested_users"])

    def test_get_books_for_user(self):
        """does get_books_for_user get all the books"""

        data = models.bookwyrm_export_job.get_books_for_user(self.local_user)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0].title, "Example Edition")

    def test_archive(self):
        """actually create the TAR file"""
        models.bookwyrm_export_job.create_archive_task(job_id=self.job.id)
        self.job.refresh_from_db()

        with (
            self.job.export_data.open("rb") as tar_file,
            BookwyrmTarFile.open(mode="r", fileobj=tar_file) as tar,
        ):
            archive_json_file = tar.extractfile("archive.json")
            data = json.load(archive_json_file)

            # JSON from the archive should be what we want it to be
            self.assertEqual(data, self.job.export_json)

            # User avatar should be present in archive
            with self.local_user.avatar.open() as expected_avatar:
                archive_avatar = tar.extractfile(data["icon"]["url"])
                self.assertEqual(expected_avatar.read(), archive_avatar.read())

            # Edition cover should be present in archive
            with self.edition.cover.open() as expected_cover:
                archive_cover = tar.extractfile(
                    data["books"][0]["edition"]["cover"]["url"]
                )
                self.assertEqual(expected_cover.read(), archive_cover.read())
