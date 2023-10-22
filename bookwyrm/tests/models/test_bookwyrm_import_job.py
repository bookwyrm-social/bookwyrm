""" testing models """

import json
import pathlib
from unittest.mock import patch

from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.test import TestCase

from bookwyrm import models
from bookwyrm.utils.tar import BookwyrmTarFile
from bookwyrm.models import bookwyrm_import_job


class BookwyrmImport(TestCase):
    """testing user import functions"""

    def setUp(self):
        """setting stuff up"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"), patch(
            "bookwyrm.suggested_users.rerank_user_task.delay"
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
                local=True,
                localname="badger",
            )

            self.work = models.Work.objects.create(title="Test Book")

            self.book = models.Edition.objects.create(
                title="Test Book",
                remote_id="https://example.com/book/1234",
                openlibrary_key="OL28216445M",
                parent_work=self.work,
            )

        archive_file = pathlib.Path(__file__).parent.joinpath(
            "../data/bookwyrm_account_export.tar.gz"
        )
        self.tarfile = BookwyrmTarFile.open(
            mode="r:gz", fileobj=open(archive_file, "rb")
        )
        self.import_data = json.loads(self.tarfile.read("archive.json").decode("utf-8"))

    def test_update_user_profile(self):
        """Test update the user's profile from import data"""

        with patch("bookwyrm.suggested_users.remove_user_task.delay"), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ):

            models.bookwyrm_import_job.update_user_profile(
                self.local_user, self.tarfile, self.import_data.get("user")
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

        with patch("bookwyrm.suggested_users.remove_user_task.delay"), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ):

            models.bookwyrm_import_job.update_user_settings(
                self.local_user, self.import_data.get("user")
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

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):

            models.bookwyrm_import_job.update_goals(
                self.local_user, self.import_data.get("goals")
            )

        self.local_user.refresh_from_db()
        goal = models.AnnualGoal.objects.get()
        self.assertEqual(goal.year, 2023)
        self.assertEqual(goal.goal, 12)
        self.assertEqual(goal.privacy, "followers")

    def test_upsert_saved_lists_existing(self):
        """Test upserting an existing saved list"""

        with patch("bookwyrm.lists_stream.remove_list_task.delay"), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
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

        with patch("bookwyrm.lists_stream.remove_list_task.delay"), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
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

    def test_upsert_follows(self):
        """Test take a list of remote ids and add as follows"""

        before_follow = models.UserFollows.objects.filter(
            user_subject=self.local_user, user_object=self.rat_user
        ).exists()

        self.assertFalse(before_follow)

        with patch("bookwyrm.activitystreams.add_user_statuses_task.delay"), patch(
            "bookwyrm.lists_stream.add_user_lists_task.delay"
        ), patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            models.bookwyrm_import_job.upsert_follows(
                self.local_user, self.import_data.get("follows")
            )

        after_follow = models.UserFollows.objects.filter(
            user_subject=self.local_user, user_object=self.rat_user
        ).exists()
        self.assertTrue(after_follow)

    def test_upsert_user_blocks(self):
        """test adding blocked users"""

        blocked_before = models.UserBlocks.objects.filter(
            Q(
                user_subject=self.local_user,
                user_object=self.badger_user,
            )
        ).exists()
        self.assertFalse(blocked_before)

        with patch("bookwyrm.suggested_users.remove_suggestion_task.delay"), patch(
            "bookwyrm.activitystreams.remove_user_statuses_task.delay"
        ), patch("bookwyrm.lists_stream.remove_user_lists_task.delay"), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ):
            models.bookwyrm_import_job.upsert_user_blocks(
                self.local_user, self.import_data.get("blocked_users")
            )

        blocked_after = models.UserBlocks.objects.filter(
            Q(
                user_subject=self.local_user,
                user_object=self.badger_user,
            )
        ).exists()
        self.assertTrue(blocked_after)

    def test_get_or_create_authors(self):
        """Test taking a JSON string of authors find or create the authors
        in the database and returning a list of author instances"""

        author_exists = models.Author.objects.filter(isni="0000000108973024").exists()
        self.assertFalse(author_exists)

        authors = self.import_data.get("books")[0]["authors"]
        bookwyrm_import_job.get_or_create_authors(authors)

        author = models.Author.objects.get(isni="0000000108973024")
        self.assertEqual(author.name, "James C. Scott")

    def test_get_or_create_edition_existing(self):
        """Test take a JSON string of books and editions,
        find or create the editions in the database and
        return a list of edition instances"""

        self.assertEqual(models.Edition.objects.count(), 1)
        self.assertEqual(models.Edition.objects.count(), 1)

        bookwyrm_import_job.get_or_create_edition(
            self.import_data["books"][1], self.tarfile
        )  # Sand Talk

        self.assertEqual(models.Edition.objects.count(), 1)

    def test_get_or_create_edition_not_existing(self):
        """Test take a JSON string of books and editions,
        find or create the editions in the database and
        return a list of edition instances"""

        self.assertEqual(models.Edition.objects.count(), 1)

        bookwyrm_import_job.get_or_create_edition(
            self.import_data["books"][0], self.tarfile
        )  # Seeing like a state

        self.assertTrue(models.Edition.objects.filter(isbn_13="9780300070163").exists())
        self.assertEqual(models.Edition.objects.count(), 2)

    def test_clean_values(self):
        """test clean values we don't want when creating new instances"""

        author = self.import_data.get("books")[0]["authors"][0]
        edition = self.import_data.get("books")[0]["edition"]

        cleaned_author = bookwyrm_import_job.clean_values(author)
        cleaned_edition = bookwyrm_import_job.clean_values(edition)

        self.assertEqual(cleaned_author["name"], "James C. Scott")
        self.assertEqual(cleaned_author.get("id"), None)
        self.assertEqual(cleaned_author.get("remote_id"), None)
        self.assertEqual(cleaned_author.get("last_edited_by"), None)
        self.assertEqual(cleaned_author.get("last_edited_by_id"), None)

        self.assertEqual(cleaned_edition.get("title"), "Seeing Like a State")
        self.assertEqual(cleaned_edition.get("id"), None)
        self.assertEqual(cleaned_edition.get("remote_id"), None)
        self.assertEqual(cleaned_edition.get("last_edited_by"), None)
        self.assertEqual(cleaned_edition.get("last_edited_by_id"), None)
        self.assertEqual(cleaned_edition.get("cover"), None)
        self.assertEqual(cleaned_edition.get("preview_image "), None)
        self.assertEqual(cleaned_edition.get("user"), None)
        self.assertEqual(cleaned_edition.get("book_list"), None)
        self.assertEqual(cleaned_edition.get("shelf_book"), None)

    def test_find_existing(self):
        """Given a book or author, find any existing model instances"""

        self.assertEqual(models.Book.objects.count(), 2)  # includes Work
        self.assertEqual(models.Edition.objects.count(), 1)
        self.assertEqual(models.Edition.objects.first().title, "Test Book")
        self.assertEqual(models.Edition.objects.first().openlibrary_key, "OL28216445M")

        existing = bookwyrm_import_job.find_existing(
            models.Edition, {"openlibrary_key": "OL28216445M", "isbn_10": None}
        )
        self.assertEqual(existing.title, "Test Book")

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
                "progress": None,
                "progress_mode": "PG",
                "start_date": "2022-12-31T13:30:00Z",
                "finish_date": "2023-08-23T14:30:00Z",
                "stopped_date": None,
                "is_active": False,
            }
        ]

        self.assertEqual(models.ReadThrough.objects.count(), 0)
        bookwyrm_import_job.upsert_readthroughs(
            readthroughs, self.local_user, self.book.id
        )

        self.assertEqual(models.ReadThrough.objects.count(), 1)
        self.assertEqual(models.ReadThrough.objects.first().progress_mode, "PG")
        self.assertEqual(
            models.ReadThrough.objects.first().start_date,
            parse_datetime("2022-12-31T13:30:00Z"),
        )
        self.assertEqual(models.ReadThrough.objects.first().book_id, self.book.id)
        self.assertEqual(models.ReadThrough.objects.first().user, self.local_user)

    def test_get_or_create_review_status(self):
        """Test get_or_create_review_status with a review"""

        self.assertEqual(models.Review.objects.filter(user=self.local_user).count(), 0)
        reviews = self.import_data["books"][0]["reviews"]
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            bookwyrm_import_job.get_or_create_statuses(
                self.local_user, models.Review, reviews, self.book.id
            )
        self.assertEqual(models.Review.objects.filter(user=self.local_user).count(), 1)
        self.assertEqual(
            models.Review.objects.filter(book=self.book).first().raw_content,
            "I like it",
        )
        self.assertEqual(
            models.Review.objects.filter(book=self.book).first().content_warning,
            "Here's a spoiler alert",
        )
        self.assertEqual(
            models.Review.objects.filter(book=self.book).first().sensitive, True
        )
        self.assertEqual(
            models.Review.objects.filter(book=self.book).first().published_date,
            parse_datetime("2023-08-14T04:09:18.343Z"),
        )
        self.assertEqual(
            models.Review.objects.filter(book=self.book).first().name, "great book"
        )
        self.assertEqual(
            models.Review.objects.filter(book=self.book).first().rating, 5.00
        )

    def test_get_or_create_comment_status(self):
        """Test get_or_create_review_status with a comment"""

        self.assertEqual(models.Comment.objects.filter(user=self.local_user).count(), 0)
        comments = self.import_data["books"][1]["comments"]
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            bookwyrm_import_job.get_or_create_statuses(
                self.local_user, models.Comment, comments, self.book.id
            )
        self.assertEqual(models.Comment.objects.filter(user=self.local_user).count(), 1)
        self.assertEqual(
            models.Comment.objects.filter(book=self.book).first().raw_content,
            "this is a comment about an amazing book",
        )
        self.assertEqual(
            models.Comment.objects.filter(book=self.book).first().content_warning, None
        )
        self.assertEqual(
            models.Comment.objects.filter(book=self.book).first().sensitive, False
        )
        self.assertEqual(
            models.Comment.objects.filter(book=self.book).first().published_date,
            parse_datetime("2023-08-14T04:48:18.746Z"),
        )
        self.assertEqual(
            models.Comment.objects.filter(book=self.book).first().progress_mode, "PG"
        )

    def test_get_or_create_comment_quote(self):
        """Test get_or_create_review_status with a quote"""

        self.assertEqual(
            models.Quotation.objects.filter(user=self.local_user).count(), 0
        )
        quotes = self.import_data["books"][1]["quotes"]
        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            bookwyrm_import_job.get_or_create_statuses(
                self.local_user, models.Quotation, quotes, self.book.id
            )
        self.assertEqual(
            models.Quotation.objects.filter(user=self.local_user).count(), 1
        )
        self.assertEqual(
            models.Quotation.objects.filter(book=self.book).first().raw_content,
            "not actually from this book lol",
        )
        self.assertEqual(
            models.Quotation.objects.filter(book=self.book).first().content_warning,
            "spoiler ahead!",
        )
        self.assertEqual(
            models.Quotation.objects.filter(book=self.book).first().raw_quote,
            "To be or not to be",
        )
        self.assertEqual(
            models.Quotation.objects.filter(book=self.book).first().published_date,
            parse_datetime("2023-08-14T04:48:50.207Z"),
        )
        self.assertEqual(
            models.Quotation.objects.filter(book=self.book).first().position_mode, "PG"
        )
        self.assertEqual(
            models.Quotation.objects.filter(book=self.book).first().position, 1
        )

    def test_upsert_list_existing(self):
        """Take a list and ListItems as JSON and create DB entries
        if they don't already exist"""

        book_data = self.import_data["books"][0]

        other_book = models.Edition.objects.create(
            title="Another Book", remote_id="https://example.com/book/9876"
        )

        with patch("bookwyrm.lists_stream.remove_list_task.delay"), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
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

        with patch("bookwyrm.lists_stream.remove_list_task.delay"), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ):
            bookwyrm_import_job.upsert_lists(
                self.local_user,
                book_data["lists"],
                book_data["list_items"],
                other_book.id,
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

        book_data = self.import_data["books"][0]

        self.assertEqual(models.List.objects.filter(user=self.local_user).count(), 0)
        self.assertFalse(models.ListItem.objects.filter(book=self.book.id).exists())

        with patch("bookwyrm.lists_stream.remove_list_task.delay"), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ):
            bookwyrm_import_job.upsert_lists(
                self.local_user,
                book_data["lists"],
                book_data["list_items"],
                self.book.id,
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

        with patch("bookwyrm.activitystreams.add_book_statuses_task.delay"), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ):
            models.ShelfBook.objects.create(
                book=self.book, shelf=shelf, user=self.local_user
            )

        book_data = self.import_data["books"][0]
        with patch("bookwyrm.activitystreams.add_book_statuses_task.delay"), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ):
            bookwyrm_import_job.upsert_shelves(self.book, self.local_user, book_data)

        self.assertEqual(
            models.ShelfBook.objects.filter(user=self.local_user.id).count(), 2
        )

    def test_upsert_shelves_not_existing(self):
        """Take shelf and ShelfBooks JSON objects and create
        DB entries if they don't already exist"""

        self.assertEqual(
            models.ShelfBook.objects.filter(user=self.local_user.id).count(), 0
        )

        book_data = self.import_data["books"][0]

        with patch("bookwyrm.activitystreams.add_book_statuses_task.delay"), patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ):
            bookwyrm_import_job.upsert_shelves(self.book, self.local_user, book_data)

        self.assertEqual(
            models.ShelfBook.objects.filter(user=self.local_user.id).count(), 2
        )

        # check we didn't create an extra shelf
        self.assertEqual(
            models.Shelf.objects.filter(user=self.local_user.id).count(), 4
        )
