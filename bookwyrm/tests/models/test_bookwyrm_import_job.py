""" testing models """

import json
import os
import pathlib
from unittest.mock import patch

from django.core.files import File
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.test import TestCase

from bookwyrm import activitypub, models
from bookwyrm.utils.tar import BookwyrmTarFile
from bookwyrm.models import bookwyrm_import_job


class BookwyrmImport(TestCase):  # pylint: disable=too-many-public-methods
    """testing user import functions"""

    def setUp(self):
        """setting stuff up"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
            patch("bookwyrm.suggested_users.rerank_user_task.delay"),
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
                show_goal=True,
                show_suggested_users=True,
                discoverable=True,
                preferred_timezone="America/Los Angeles",
                default_post_privacy="public",
            )

            self.rat_user = models.User.objects.create_user(
                "rat", "rat@rat.rat", "password", local=True, localname="rat"
            )

            self.badger_user = models.User.objects.create_user(
                "badger",
                "badger@badger.badger",
                "password",
                local=False,
                localname="badger",
                remote_id="badger@remote.remote",
            )

            self.work = models.Work.objects.create(title="Sand Talk")

            self.book = models.Edition.objects.create(
                title="Sand Talk",
                remote_id="https://example.com/book/1234",
                openlibrary_key="OL28216445M",
                inventaire_id="isbn:9780062975645",
                isbn_13="9780062975645",
                parent_work=self.work,
            )

        self.json_file = pathlib.Path(__file__).parent.joinpath(
            "../data/user_import.json"
        )

        with open(self.json_file, "r", encoding="utf-8") as jsonfile:
            self.json_data = json.loads(jsonfile.read())

        self.archive_file_path = os.path.relpath(
            pathlib.Path(__file__).parent.joinpath(
                "../data/bookwyrm_account_export.tar.gz"
            )
        )

        self.job = bookwyrm_import_job.BookwyrmImportJob.objects.create(
            user=self.local_user, required=[]
        )

    def test_update_user_profile(self):
        """Test update the user's profile from import data"""

        with (
            patch("bookwyrm.suggested_users.remove_user_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
            patch("bookwyrm.suggested_users.rerank_user_task.delay"),
        ):
            with (
                open(self.archive_file_path, "rb") as fileobj,
                BookwyrmTarFile.open(mode="r:gz", fileobj=fileobj) as tarfile,
            ):
                models.bookwyrm_import_job.update_user_profile(
                    self.local_user, tarfile, self.json_data
                )

            self.local_user.refresh_from_db()

            self.assertEqual(
                self.local_user.username, "mouse"
            )  # username should not change
            self.assertEqual(self.local_user.name, "Rat")
            self.assertEqual(
                self.local_user.summary,
                "I love to make soup in Paris and eat pizza in New York",
            )

    def test_update_user_settings(self):
        """Test updating the user's settings from import data"""

        with (
            patch("bookwyrm.suggested_users.remove_user_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
            patch("bookwyrm.suggested_users.rerank_user_task.delay"),
        ):
            models.bookwyrm_import_job.update_user_settings(
                self.local_user, self.json_data
            )
            self.local_user.refresh_from_db()

            self.assertEqual(self.local_user.manually_approves_followers, True)
            self.assertEqual(self.local_user.hide_follows, True)
            self.assertEqual(self.local_user.show_goal, False)
            self.assertEqual(self.local_user.show_suggested_users, False)
            self.assertEqual(self.local_user.discoverable, False)
            self.assertEqual(self.local_user.preferred_timezone, "Australia/Adelaide")
            self.assertEqual(self.local_user.default_post_privacy, "followers")

    def test_update_goals(self):
        """Test update the user's goals from import data"""

        models.AnnualGoal.objects.create(
            user=self.local_user,
            year=2023,
            goal=999,
            privacy="public",
        )

        goals = [{"goal": 12, "year": 2023, "privacy": "followers"}]

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):

            models.bookwyrm_import_job.update_goals(self.local_user, goals)

        self.local_user.refresh_from_db()
        goal = models.AnnualGoal.objects.get()
        self.assertEqual(goal.year, 2023)
        self.assertEqual(goal.goal, 12)
        self.assertEqual(goal.privacy, "followers")

    def test_upsert_saved_lists_existing(self):
        """Test upserting an existing saved list"""

        with (
            patch("bookwyrm.lists_stream.remove_list_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
        ):
            book_list = models.List.objects.create(
                name="My cool list",
                user=self.rat_user,
                remote_id="https://local.lists/9999",
            )

        self.assertFalse(self.local_user.saved_lists.filter(id=book_list.id).exists())

        self.local_user.saved_lists.add(book_list)

        self.assertTrue(self.local_user.saved_lists.filter(id=book_list.id).exists())

        with patch("bookwyrm.activitypub.base_activity.resolve_remote_id"):
            models.bookwyrm_import_job.upsert_saved_lists(
                self.local_user, ["https://local.lists/9999"]
            )
        saved_lists = self.local_user.saved_lists.filter(
            remote_id="https://local.lists/9999"
        ).all()
        self.assertEqual(len(saved_lists), 1)

    def test_upsert_saved_lists_not_existing(self):
        """Test upserting a new saved list"""

        with (
            patch("bookwyrm.lists_stream.remove_list_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
        ):
            book_list = models.List.objects.create(
                name="My cool list",
                user=self.rat_user,
                remote_id="https://local.lists/9999",
            )

        self.assertFalse(self.local_user.saved_lists.filter(id=book_list.id).exists())

        with patch("bookwyrm.activitypub.base_activity.resolve_remote_id"):
            models.bookwyrm_import_job.upsert_saved_lists(
                self.local_user, ["https://local.lists/9999"]
            )

        self.assertTrue(self.local_user.saved_lists.filter(id=book_list.id).exists())

    def test_follow_relationship(self):
        """Test take a remote ID and create a follow"""

        task = bookwyrm_import_job.UserRelationshipImport.objects.create(
            parent_job=self.job,
            relationship="follow",
            remote_id="https://blah.blah/user/rat",
        )

        before_follow = models.UserFollows.objects.filter(
            user_subject=self.local_user, user_object=self.rat_user
        ).exists()

        self.assertFalse(before_follow)

        with (
            patch("bookwyrm.activitystreams.add_user_statuses_task.delay"),
            patch("bookwyrm.lists_stream.add_user_lists_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
            patch("bookwyrm.activitypub.resolve_remote_id", return_value=self.rat_user),
        ):

            bookwyrm_import_job.import_user_relationship_task(child_id=task.id)

        after_follow = models.UserFollows.objects.filter(
            user_subject=self.local_user, user_object=self.rat_user
        ).exists()
        self.assertTrue(after_follow)

    def test_import_book_task_existing_author(self):
        """Test importing a book with an author
        already known to the server does not overwrite"""

        self.assertEqual(models.Author.objects.count(), 0)
        models.Author.objects.create(
            id=1,
            name="James C. Scott",
            wikipedia_link="https://en.wikipedia.org/wiki/James_C._Scott",
            wikidata="Q3025403",
            aliases=["Test Alias"],
        )

        with open(self.archive_file_path, "rb") as fileobj:
            self.job.archive_file = File(fileobj)
            self.job.save()
        task = bookwyrm_import_job.UserImportBook.objects.create(
            parent_job=self.job, book_data=self.json_data.get("books")[0]
        )

        self.assertEqual(models.Edition.objects.count(), 1)

        # run the task
        bookwyrm_import_job.import_book_task(child_id=task.id)

        self.assertTrue(models.Edition.objects.filter(isbn_13="9780300070163").exists())
        self.assertEqual(models.Edition.objects.count(), 2)

        # Check the existing author did not get overwritten
        author = models.Author.objects.first()
        self.assertEqual(author.name, "James C. Scott")
        self.assertIn(author.aliases[0], "Test Alias")

    def test_import_book_task_existing_edition(self):
        """Test importing a book with an edition
        already known to the server does not overwrite"""

        with open(self.archive_file_path, "rb") as fileobj:
            self.job.archive_file = File(fileobj)
            self.job.save()
        task = bookwyrm_import_job.UserImportBook.objects.create(
            parent_job=self.job, book_data=self.json_data.get("books")[1]
        )

        self.assertEqual(models.Edition.objects.count(), 1)
        self.assertTrue(models.Edition.objects.filter(isbn_13="9780062975645").exists())

        # run the task
        bookwyrm_import_job.import_book_task(child_id=task.id)

        # Check the existing Edition did not get overwritten
        self.assertEqual(models.Edition.objects.count(), 1)
        self.assertEqual(models.Edition.objects.first().title, "Sand Talk")

    def test_import_book_task_existing_work(self):
        """Test importing a book with a work unknown to the server"""

        with open(self.archive_file_path, "rb") as fileobj:
            self.job.archive_file = File(fileobj)
            self.job.save()
        task = bookwyrm_import_job.UserImportBook.objects.create(
            parent_job=self.job, book_data=self.json_data.get("books")[1]
        )

        self.assertEqual(models.Work.objects.count(), 1)

        # run the task
        bookwyrm_import_job.import_book_task(child_id=task.id)

        # Check the existing Work did not get overwritten
        self.assertEqual(models.Work.objects.count(), 1)
        self.assertNotEqual(
            self.json_data.get("books")[1]["work"]["title"], models.Work.objects.first()
        )

    def test_import_book_task_new_author(self):
        """Test importing a book with author not known
        to the server imports the new author"""

        with open(self.archive_file_path, "rb") as fileobj:
            self.job.archive_file = File(fileobj)
            self.job.save()
        task = bookwyrm_import_job.UserImportBook.objects.create(
            parent_job=self.job, book_data=self.json_data.get("books")[0]
        )

        self.assertEqual(models.Edition.objects.count(), 1)

        # run the task
        bookwyrm_import_job.import_book_task(child_id=task.id)

        self.assertTrue(models.Edition.objects.filter(isbn_13="9780300070163").exists())
        self.assertEqual(models.Edition.objects.count(), 2)

        # Check the author was created
        author = models.Author.objects.get()
        self.assertEqual(author.name, "James C. Scott")
        self.assertIn(author.aliases[0], "James Campbell Scott")

    def test_import_book_task_new_edition(self):
        """Test importing a book with an edition
        unknown to the server"""

        with open(self.archive_file_path, "rb") as fileobj:
            self.job.archive_file = File(fileobj)
            self.job.save()
        task = bookwyrm_import_job.UserImportBook.objects.create(
            parent_job=self.job, book_data=self.json_data.get("books")[0]
        )

        self.assertEqual(models.Edition.objects.count(), 1)
        self.assertFalse(
            models.Edition.objects.filter(isbn_13="9780300070163").exists()
        )

        # run the task
        bookwyrm_import_job.import_book_task(child_id=task.id)

        # Check the Edition was added
        self.assertEqual(models.Edition.objects.count(), 2)
        self.assertEqual(models.Edition.objects.first().title, "Sand Talk")
        self.assertEqual(models.Edition.objects.last().title, "Seeing Like A State")
        self.assertTrue(models.Edition.objects.filter(isbn_13="9780300070163").exists())

    def test_import_book_task_new_work(self):
        """Test importing a book with a work unknown to the server"""

        with open(self.archive_file_path, "rb") as fileobj:
            self.job.archive_file = File(fileobj)
            self.job.save()
        task = bookwyrm_import_job.UserImportBook.objects.create(
            parent_job=self.job, book_data=self.json_data.get("books")[0]
        )

        self.assertEqual(models.Work.objects.count(), 1)

        # run the task
        bookwyrm_import_job.import_book_task(child_id=task.id)

        # Check the Work was added
        self.assertEqual(models.Work.objects.count(), 2)
        self.assertEqual(models.Work.objects.first().title, "Sand Talk")
        self.assertEqual(models.Work.objects.last().title, "Seeing Like a State")

    def test_block_relationship(self):
        """test adding blocks for users"""

        task = bookwyrm_import_job.UserRelationshipImport.objects.create(
            parent_job=self.job,
            relationship="block",
            remote_id="https://blah.blah/user/badger",
        )

        blocked_before = models.UserBlocks.objects.filter(
            Q(
                user_subject=self.local_user,
                user_object=self.badger_user,
            )
        ).exists()
        self.assertFalse(blocked_before)

        with (
            patch("bookwyrm.suggested_users.remove_suggestion_task.delay"),
            patch("bookwyrm.activitystreams.remove_user_statuses_task.delay"),
            patch("bookwyrm.lists_stream.remove_user_lists_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
            patch(
                "bookwyrm.activitypub.resolve_remote_id", return_value=self.badger_user
            ),
        ):
            bookwyrm_import_job.import_user_relationship_task(child_id=task.id)

        blocked_after = models.UserBlocks.objects.filter(
            Q(
                user_subject=self.local_user,
                user_object=self.badger_user,
            )
        ).exists()
        self.assertTrue(blocked_after)

    def test_get_or_create_edition_existing(self):
        """Test import existing book"""

        task = bookwyrm_import_job.UserImportBook.objects.create(
            parent_job=self.job,
            book_data=self.json_data["books"][1],
        )

        self.assertEqual(models.Edition.objects.count(), 1)

        bookwyrm_import_job.import_book_task(child_id=task.id)

        self.assertEqual(models.Edition.objects.count(), 1)

    def test_get_or_create_edition_not_existing(self):
        """Test import new book"""

        task = bookwyrm_import_job.UserImportBook.objects.create(
            parent_job=self.job,
            book_data=self.json_data["books"][0],
        )

        self.assertEqual(models.Edition.objects.count(), 1)
        bookwyrm_import_job.import_book_task(child_id=task.id)
        self.assertTrue(models.Edition.objects.filter(isbn_13="9780300070163").exists())
        self.assertEqual(models.Edition.objects.count(), 2)

    def test_upsert_readthroughs(self):
        """Test take a JSON string of readthroughs, find or create the
        instances in the database and return a list of saved instances"""

        readthroughs = [
            {
                "id": 1,
                "created_date": "2023-08-24T10:18:45.923Z",
                "updated_date": "2023-08-24T10:18:45.928Z",
                "remote_id": "https://example.com/mouse/readthrough/1",
                "user_id": 1,
                "book_id": 1234,
                "progress": 23,
                "progress_mode": "PG",
                "start_date": "2022-12-31T13:30:00Z",
                "finish_date": "2023-08-23T14:30:00Z",
                "stopped_date": None,
                "is_active": False,
            }
        ]

        self.assertEqual(models.ReadThrough.objects.count(), 0)
        bookwyrm_import_job.upsert_readthroughs(
            self.local_user, self.book.id, readthroughs
        )

        self.assertEqual(models.ReadThrough.objects.count(), 1)
        self.assertEqual(models.ReadThrough.objects.first().progress_mode, "PG")
        self.assertEqual(
            models.ReadThrough.objects.first().start_date,
            parse_datetime("2022-12-31T13:30:00Z"),
        )
        self.assertEqual(models.ReadThrough.objects.first().book_id, self.book.id)
        self.assertEqual(models.ReadThrough.objects.first().user, self.local_user)

    def test_get_or_create_review(self):
        """Test upsert_status_task with a review"""

        task = bookwyrm_import_job.UserImportPost.objects.create(
            parent_job=self.job,
            book=self.book,
            json=self.json_data["books"][0]["reviews"][0],
            status_type="review",
        )

        self.assertEqual(models.Review.objects.filter(user=self.local_user).count(), 0)

        with patch("bookwyrm.models.bookwyrm_import_job.is_alias", return_value=True):
            bookwyrm_import_job.upsert_status_task(child_id=task.id)

        self.assertEqual(models.Review.objects.filter(user=self.local_user).count(), 1)
        self.assertEqual(
            models.Review.objects.filter(book=self.book).first().content,
            "<p>I like it</p>",
        )
        self.assertEqual(
            models.Review.objects.filter(book=self.book).first().content_warning,
            "Here's a spoiler alert",
        )
        self.assertEqual(
            models.Review.objects.filter(book=self.book).first().sensitive, True
        )
        self.assertEqual(
            models.Review.objects.filter(book=self.book).first().name, "great book"
        )
        self.assertAlmostEqual(
            models.Review.objects.filter(book=self.book).first().rating, 5.00
        )

        self.assertEqual(
            models.Review.objects.filter(book=self.book).first().privacy, "followers"
        )

    def test_get_or_create_comment(self):
        """Test upsert_status_task with a comment"""

        task = bookwyrm_import_job.UserImportPost.objects.create(
            parent_job=self.job,
            book=self.book,
            json=self.json_data["books"][1]["comments"][0],
            status_type="comment",
        )

        self.assertEqual(models.Comment.objects.filter(user=self.local_user).count(), 0)

        with patch("bookwyrm.models.bookwyrm_import_job.is_alias", return_value=True):
            bookwyrm_import_job.upsert_status_task(child_id=task.id)

        self.assertEqual(models.Comment.objects.filter(user=self.local_user).count(), 1)
        self.assertEqual(
            models.Comment.objects.filter(book=self.book).first().content,
            "<p>this is a comment about an amazing book</p>",
        )
        self.assertEqual(
            models.Comment.objects.filter(book=self.book).first().content_warning, None
        )
        self.assertEqual(
            models.Comment.objects.filter(book=self.book).first().sensitive, False
        )
        self.assertEqual(
            models.Comment.objects.filter(book=self.book).first().progress_mode, "PG"
        )

    def test_get_or_create_quote(self):
        """Test upsert_status_task with a quote"""

        task = bookwyrm_import_job.UserImportPost.objects.create(
            parent_job=self.job,
            book=self.book,
            json=self.json_data["books"][1]["quotations"][0],
            status_type="quote",
        )

        self.assertEqual(
            models.Quotation.objects.filter(user=self.local_user).count(), 0
        )

        with patch("bookwyrm.models.bookwyrm_import_job.is_alias", return_value=True):
            bookwyrm_import_job.upsert_status_task(child_id=task.id)

        self.assertEqual(
            models.Quotation.objects.filter(user=self.local_user).count(), 1
        )
        self.assertEqual(
            models.Quotation.objects.filter(book=self.book).first().content,
            "<p>not actually from this book lol</p>",
        )
        self.assertEqual(
            models.Quotation.objects.filter(book=self.book).first().content_warning,
            "spoiler ahead!",
        )
        self.assertEqual(
            models.Quotation.objects.filter(book=self.book).first().quote,
            "<p>To be or not to be</p>",
        )
        self.assertEqual(
            models.Quotation.objects.filter(book=self.book).first().position_mode, "PG"
        )

    def test_get_or_create_quote_unauthorized(self):
        """Test upsert_status_task with a quote but not authorized"""

        task = bookwyrm_import_job.UserImportPost.objects.create(
            parent_job=self.job,
            book=self.book,
            json=self.json_data["books"][1]["quotations"][0],
            status="quote",
        )

        self.assertEqual(
            models.Quotation.objects.filter(user=self.local_user).count(), 0
        )
        with patch("bookwyrm.models.bookwyrm_import_job.is_alias", return_value=False):
            bookwyrm_import_job.upsert_status_task(child_id=task.id)
        self.assertEqual(
            models.Quotation.objects.filter(user=self.local_user).count(), 0
        )

    def test_upsert_list_existing(self):
        """Take a list and ListItems as JSON and create DB entries
        if they don't already exist"""

        other_book = models.Edition.objects.create(
            title="Another Book", remote_id="https://example.com/book/9876"
        )

        with (
            patch("bookwyrm.lists_stream.remove_list_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
        ):
            book_list = models.List.objects.create(
                name="my list of books", user=self.local_user
            )

            models.ListItem.objects.create(
                book=self.book, book_list=book_list, user=self.local_user, order=1
            )

        self.assertTrue(models.List.objects.filter(id=book_list.id).exists())
        self.assertEqual(models.List.objects.filter(user=self.local_user).count(), 1)
        self.assertEqual(
            models.ListItem.objects.filter(
                user=self.local_user, book_list=book_list
            ).count(),
            1,
        )

        with (
            patch("bookwyrm.lists_stream.remove_list_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
        ):
            bookwyrm_import_job.upsert_lists(
                self.local_user,
                other_book.id,
                self.json_data["books"][0]["lists"],
            )

        self.assertEqual(models.List.objects.filter(user=self.local_user).count(), 1)
        self.assertEqual(models.List.objects.filter(user=self.local_user).count(), 1)
        self.assertEqual(
            models.ListItem.objects.filter(
                user=self.local_user, book_list=book_list
            ).count(),
            2,
        )

    def test_upsert_list_not_existing(self):
        """Take a list and ListItems as JSON and create DB entries
        if they don't already exist"""

        self.assertEqual(models.List.objects.filter(user=self.local_user).count(), 0)
        self.assertFalse(models.ListItem.objects.filter(book=self.book.id).exists())

        with (
            patch("bookwyrm.lists_stream.remove_list_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
        ):
            bookwyrm_import_job.upsert_lists(
                self.local_user,
                self.book.id,
                self.json_data["books"][0]["lists"],
            )

        self.assertEqual(models.List.objects.filter(user=self.local_user).count(), 1)
        self.assertEqual(
            models.ListItem.objects.filter(user=self.local_user).count(), 1
        )

    def test_upsert_shelves_existing(self):
        """Take shelf and ShelfBooks JSON objects and create
        DB entries if they don't already exist"""

        self.assertEqual(
            models.ShelfBook.objects.filter(user=self.local_user.id).count(), 0
        )

        shelf = models.Shelf.objects.get(name="Read", user=self.local_user)

        with (
            patch("bookwyrm.activitystreams.add_book_statuses_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
        ):
            models.ShelfBook.objects.create(
                book=self.book, shelf=shelf, user=self.local_user
            )

        with (
            patch("bookwyrm.activitystreams.add_book_statuses_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
        ):
            bookwyrm_import_job.upsert_shelves(
                self.local_user, self.book, self.json_data["books"][0].get("shelves")
            )

        self.assertEqual(
            models.ShelfBook.objects.filter(user=self.local_user.id).count(), 2
        )

    def test_upsert_shelves_not_existing(self):
        """Take shelf and ShelfBooks JSON objects and create
        DB entries if they don't already exist"""

        self.assertEqual(
            models.ShelfBook.objects.filter(user=self.local_user.id).count(), 0
        )

        with (
            patch("bookwyrm.activitystreams.add_book_statuses_task.delay"),
            patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"),
        ):
            bookwyrm_import_job.upsert_shelves(
                self.local_user, self.book, self.json_data["books"][0].get("shelves")
            )

        self.assertEqual(
            models.ShelfBook.objects.filter(user=self.local_user.id).count(), 2
        )

        # check we didn't create an extra shelf
        self.assertEqual(
            models.Shelf.objects.filter(user=self.local_user.id).count(), 4
        )

    def test_update_followers_address(self):
        """test updating followers address to local"""

        user = self.local_user
        followers = ["https://old.address/user/oldusername/followers"]
        new_followers = bookwyrm_import_job.update_followers_address(user, followers)

        self.assertEqual(new_followers, [f"{self.local_user.remote_id}/followers"])

    def test_is_alias(self):
        """test checking for valid alias"""

        self.rat_user.also_known_as.add(self.local_user)

        with patch(
            "bookwyrm.activitypub.resolve_remote_id", return_value=self.rat_user
        ):

            alias = bookwyrm_import_job.is_alias(
                self.local_user, self.rat_user.remote_id
            )

            self.assertTrue(alias)

    def test_status_already_exists(self):
        """test status checking"""

        string = '{"id":"https://www.example.com/user/rat/comment/4","type":"Comment","published":"2023-08-14T04:48:18.746+00:00","attributedTo":"https://www.example.com/user/rat","content":"<p>this is a comment about an amazing book</p>","to":["https://www.w3.org/ns/activitystreams#Public"],"cc":["https://www.example.com/user/rat/followers"],"replies":{"id":"https://www.example.com/user/rat/comment/4/replies","type":"OrderedCollection","totalItems":0,"first":"https://www.example.com/user/rat/comment/4/replies?page=1","last":"https://www.example.com/user/rat/comment/4/replies?page=1","@context":"https://www.w3.org/ns/activitystreams"},"tag":[],"attachment":[],"sensitive":false,"inReplyToBook":"https://www.example.com/book/4","readingStatus":null,"@context":"https://www.w3.org/ns/activitystreams"}'  # pylint: disable=line-too-long

        status = json.loads(string)
        parsed = activitypub.parse(status)
        exists = bookwyrm_import_job.status_already_exists(self.local_user, parsed)

        self.assertFalse(exists)

        comment = models.Comment.objects.create(
            user=self.local_user, book=self.book, content="<p>hi</p>"
        )
        status_two = comment.to_activity()
        parsed_two = activitypub.parse(status_two)
        exists_two = bookwyrm_import_job.status_already_exists(
            self.local_user, parsed_two
        )

        self.assertTrue(exists_two)
