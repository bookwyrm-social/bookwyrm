""" testing models """
from io import BytesIO
import pathlib

import pytest

from dateutil.parser import parse
from PIL import Image
from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone

from bookwyrm import models, settings
from bookwyrm.models.book import isbn_10_to_13, isbn_13_to_10
from bookwyrm.settings import ENABLE_THUMBNAIL_GENERATION


class Book(TestCase):
    """not too much going on in the books model but here we are"""

    def setUp(self):
        """we'll need some books"""
        self.work = models.Work.objects.create(
            title="Example Work", remote_id="https://example.com/book/1"
        )
        self.first_edition = models.Edition.objects.create(
            title="Example Edition", parent_work=self.work
        )
        self.second_edition = models.Edition.objects.create(
            title="Another Example Edition",
            parent_work=self.work,
        )

    def test_remote_id(self):
        """fanciness with remote/origin ids"""
        remote_id = f"https://{settings.DOMAIN}/book/{self.work.id}"
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

    def test_isbn_13_to_10(self):
        """checksums and so on"""
        isbn_13 = "9781788161671"
        isbn_10 = isbn_13_to_10(isbn_13)
        self.assertEqual(isbn_10, "178816167X")

        isbn_13 = "978-1788-16167-1"
        isbn_10 = isbn_13_to_10(isbn_13)
        self.assertEqual(isbn_10, "178816167X")

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
        self.assertEqual(book.alt_text, "Test Edition (worm, Glorbish language, 2020)")

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
        image_file = pathlib.Path(__file__).parent.joinpath(
            "../../static/images/default_avi.jpg"
        )
        image = Image.open(image_file)
        output = BytesIO()
        image.save(output, format=image.format)

        book = models.Edition.objects.create(title="hello")
        book.cover.save("test.jpg", ContentFile(output.getvalue()))

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

    def test_populate_sort_title(self):
        """The sort title should remove the initial article on save"""
        books = (
            models.Edition.objects.create(
                title=f"{article} Test Edition", languages=[langauge]
            )
            for langauge, articles in settings.LANGUAGE_ARTICLES.items()
            for article in articles
        )
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
