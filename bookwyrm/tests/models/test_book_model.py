""" testing models """
import pathlib

import pytest

from dateutil.parser import parse
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from bookwyrm import models, settings
from bookwyrm.models.book import (
    isbn_10_to_13,
    isbn_13_to_10,
    normalize_isbn,
    validate_isbn10,
    validate_isbn13,
)
from bookwyrm.settings import ENABLE_THUMBNAIL_GENERATION


class Book(TestCase):
    """not too much going on in the books model but here we are"""

    @classmethod
    def setUpTestData(cls):
        """we'll need some books"""
        cls.work = models.Work.objects.create(
            title="Example Work", remote_id="https://example.com/book/1"
        )
        cls.first_edition = models.Edition.objects.create(
            title="Example Edition", parent_work=cls.work
        )
        cls.second_edition = models.Edition.objects.create(
            title="Another Example Edition",
            parent_work=cls.work,
        )

    def test_remote_id(self):
        """fanciness with remote/origin ids"""
        remote_id = f"{settings.BASE_URL}/book/{self.work.id}"
        self.assertEqual(self.work.get_remote_id(), remote_id)
        self.assertEqual(self.work.remote_id, remote_id)

    def test_generated_links(self):
        """links produced from identifiers"""
        book = models.Edition.objects.create(
            title="ExEd",
            parent_work=self.work,
            openlibrary_key="OL123M",
            inventaire_id="isbn:123",
        )
        self.assertEqual(book.openlibrary_link, "https://openlibrary.org/books/OL123M")
        self.assertEqual(book.inventaire_link, "https://inventaire.io/entity/isbn:123")

    def test_create_book_invalid(self):
        """you shouldn't be able to create Books (only editions and works)"""
        self.assertRaises(ValueError, models.Book.objects.create, title="Invalid Book")

    def test_isbn_10_to_13(self):
        """checksums and so on"""
        isbn_10 = "178816167X"
        isbn_13 = isbn_10_to_13(isbn_10)
        self.assertEqual(isbn_13, "9781788161671")

        isbn_10 = "1-788-16167-X"
        isbn_13 = isbn_10_to_13(isbn_10)
        self.assertEqual(isbn_13, "9781788161671")

        # test checksum 0 case
        isbn_10 = "1-788-16164-5"
        isbn_13 = isbn_10_to_13(isbn_10)
        self.assertEqual(isbn_13, "9781788161640")

    def test_isbn_13_to_10(self):
        """checksums and so on"""
        isbn_13 = "9781788161671"
        isbn_10 = isbn_13_to_10(isbn_13)
        self.assertEqual(isbn_10, "178816167X")

        isbn_13 = "978-1788-16167-1"
        isbn_10 = isbn_13_to_10(isbn_13)
        self.assertEqual(isbn_10, "178816167X")

    def test_normalize_isbn(self):
        """Remove misc characters from ISBNs"""
        self.assertEqual(normalize_isbn("978-0-4633461-1-2"), "9780463346112")

    def test_validate_isbn10(self):
        """ISBN10 validation"""
        invalid_isbn10 = [
            ("0123", "too short"),
            ("97801X45", "too short, invalid char"),
            ("012345678999", "too long"),
            ("01234V6789", "invalid char"),
            ("0123456788", "invalid checksum"),
            ("012345678Y", "invalid checksum char"),
        ]
        validate_isbn10("123456789")
        validate_isbn10("0123456789")
        validate_isbn10("123456789X")
        validate_isbn10("0-201-53082-1")

        for isbn, _desc in invalid_isbn10:
            with self.subTest(isbn=isbn):
                with self.assertRaises(ValidationError):
                    validate_isbn10(isbn)

    def test_validate_isbn13(self):
        """ISBN13 validation"""
        invalid_isbn13 = [
            ("978-12-3456-789-X", "invalid char"),
            ("9741234567897", "invalid prefix"),
            ("978-84-17121-94-2", "invalid checksum"),
        ]
        validate_isbn13("9781234567897")
        validate_isbn13("9781234567880")
        validate_isbn13("9791234567880")
        validate_isbn13("978-84-17121-94-5")

        for isbn, _desc in invalid_isbn13:
            with self.subTest(isbn=isbn):
                with self.assertRaises(ValidationError):
                    validate_isbn13(isbn)

    def test_get_edition_info(self):
        """text slug about an edition"""
        book = models.Edition.objects.create(title="Test Edition")
        self.assertEqual(book.edition_info, "")

        book.physical_format = "worm"
        book.save()
        self.assertEqual(book.edition_info, "worm")

        book.languages = ["English"]
        book.save()
        self.assertEqual(book.edition_info, "worm")

        book.languages = ["Glorbish", "English"]
        book.save()
        self.assertEqual(book.edition_info, "worm, Glorbish language")

        book.published_date = timezone.make_aware(parse("2020"))
        book.save()
        self.assertEqual(book.edition_info, "worm, Glorbish language, 2020")

    def test_alt_text(self):
        """text slug used for cover images"""
        book = models.Edition.objects.create(title="Test Edition")
        author = models.Author.objects.create(name="Author Name")

        self.assertEqual(book.alt_text, "Test Edition")

        book.authors.set([author])
        book.save()

        self.assertEqual(book.alt_text, "Author Name: Test Edition")

        book.physical_format = "worm"
        book.published_date = timezone.make_aware(parse("2022"))

        self.assertEqual(book.alt_text, "Author Name: Test Edition (worm, 2022)")

    def test_get_rank(self):
        """sets the data quality index for the book"""
        # basic rank
        self.assertEqual(self.first_edition.edition_rank, 0)

        self.first_edition.description = "hi"
        self.first_edition.save()
        self.assertEqual(self.first_edition.edition_rank, 1)

    @pytest.mark.skipif(
        not ENABLE_THUMBNAIL_GENERATION,
        reason="Thumbnail generation disabled in settings",
    )
    def test_thumbnail_fields(self):
        """Just hit them"""
        image_path = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )

        book = models.Edition.objects.create(title="hello")
        with open(image_path, "rb") as image_file:
            book.cover.save("test.jpg", image_file)

        self.assertIsNotNone(book.cover_bw_book_xsmall_webp.url)
        self.assertIsNotNone(book.cover_bw_book_xsmall_jpg.url)
        self.assertIsNotNone(book.cover_bw_book_small_webp.url)
        self.assertIsNotNone(book.cover_bw_book_small_jpg.url)
        self.assertIsNotNone(book.cover_bw_book_medium_webp.url)
        self.assertIsNotNone(book.cover_bw_book_medium_jpg.url)
        self.assertIsNotNone(book.cover_bw_book_large_webp.url)
        self.assertIsNotNone(book.cover_bw_book_large_jpg.url)
        self.assertIsNotNone(book.cover_bw_book_xlarge_webp.url)
        self.assertIsNotNone(book.cover_bw_book_xlarge_jpg.url)
        self.assertIsNotNone(book.cover_bw_book_xxlarge_webp.url)
        self.assertIsNotNone(book.cover_bw_book_xxlarge_jpg.url)

    # pylint: disable=unused-variable
    def test_populate_sort_title(self):
        """The sort title should remove the initial article on save"""
        books = []
        for (k, v) in settings.LANGUAGE_ARTICLES.items():
            lang_books = [
                models.Edition.objects.create(
                    title=f"{article} Test Edition", languages=[string]
                )
                for string in v["variants"]
                for article in v["articles"]
            ]
            books = books + lang_books

        for book in books:
            print(book.title, book.sort_title)
        self.assertTrue(all(book.sort_title == "test edition" for book in books))

    def test_repair_edition(self):
        """Fix editions with no works"""
        edition = models.Edition.objects.create(title="test")
        edition.authors.set([models.Author.objects.create(name="Author Name")])
        self.assertIsNone(edition.parent_work)

        edition.repair()
        edition.refresh_from_db()

        self.assertEqual(edition.parent_work.title, "test")
        self.assertEqual(edition.parent_work.authors.count(), 1)
