""" Test Unicode slug generation and URL routing """
import re
from unittest.mock import patch
from django.test import TestCase
from django.utils.text import slugify

from bookwyrm import models
from bookwyrm.utils.regex import SLUG


class UnicodeSlugTest(TestCase):
    """Test Unicode support in slugs and URL patterns"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "testuser",
                "test@example.com",
                "password",
                local=True,
                localname="testuser",
            )
        models.SiteSettings.objects.create()

    def test_unicode_characters_in_slug_generation(self):
        """Test that Unicode characters are preserved in slugs"""
        test_cases = [
            ("Café", "café"),  # French accented characters
            ("北京", "北京"),  # Chinese characters
            ("العربية", "العربية"),  # Arabic characters
            ("Tëst Bøøk", "tëst-bøøk"),  # Mixed accented characters
            ("Test Book", "test-book"),  # ASCII (should still work)
        ]

        for name, expected_slug in test_cases:
            with self.subTest(name=name):
                # Test Django's slugify with allow_unicode=True
                actual_slug = slugify(name, allow_unicode=True)
                self.assertEqual(
                    actual_slug,
                    expected_slug,
                    (
                        f"Failed for '{name}': expected "
                        f"'{expected_slug}', got '{actual_slug}'"
                    ),
                )

    def test_serbian_cyrillic_characters(self):
        """Test Serbian Cyrillic character support"""
        serbian_test_cases = [
            ("Иво Андрић", "иво-андрић"),  # Ivo Andrić (Nobel Prize winner)
            ("Милош Црњански", "милош-црњански"),  # Miloš Crnjanski
            ("На Дрини ћуприја", "на-дрини-ћуприја"),  # The Bridge on the Drina
            ("Сеобе", "сеобе"),  # Migrations
            ("Ђорђе", "ђорђе"),  # Serbian-specific Đ letter
            ("Љубав", "љубав"),  # Serbian-specific Lj letter
            ("Његош", "његош"),  # Serbian-specific Nj letter
            ("Ћирилица", "ћирилица"),  # Serbian-specific Ć letter
            ("Џемпер", "џемпер"),  # Serbian-specific Dž letter
        ]

        for name, expected_slug in serbian_test_cases:
            with self.subTest(name=name):
                actual_slug = slugify(name, allow_unicode=True)
                self.assertEqual(
                    actual_slug,
                    expected_slug,
                    (
                        f"Serbian Cyrillic failed for '{name}': "
                        f"expected '{expected_slug}', "
                        f"got '{actual_slug}'"
                    ),
                )

    def test_model_local_path_with_unicode(self):
        """Test that model local_path generates Unicode slugs correctly"""
        # Test with Author model which uses slugs
        author = models.Author.objects.create(name="José García")

        # Check that local_path includes Unicode slug
        local_path = author.local_path
        self.assertIn(
            "josé-garcía", local_path
        )  # Unicode preserved, space becomes hyphen
        self.assertIn("/s/", local_path)

    def test_serbian_author_model_integration(self):
        """Test Serbian Cyrillic author name integration with model local_path"""
        # Test Nobel Prize winner Ivo Andrić
        author = models.Author.objects.create(name="Иво Андрић")
        local_path = author.local_path

        self.assertIn("иво-андрић", local_path)
        self.assertIn("/s/", local_path)

    def test_unicode_regex_pattern_matching(self):
        """Test that the SLUG regex pattern matches Unicode characters"""
        test_slugs = [
            "/s/café-literature",
            "/s/北京-book",
            "/s/test-book",  # ASCII
            "/s/иво-андрић",  # Serbian Cyrillic
            "/s/на-дрини-ћуприја",  # Serbian book title
        ]

        pattern = re.compile(SLUG)
        for slug_path in test_slugs:
            with self.subTest(slug_path=slug_path):
                match = pattern.search(slug_path)
                self.assertIsNotNone(match, f"Pattern should match '{slug_path}'")
                extracted_slug = match.group("slug")
                expected = slug_path.replace("/s/", "")
                self.assertEqual(
                    extracted_slug,
                    expected,
                )

    def test_mixed_unicode_ascii_slugs(self):
        """Test edge cases with mixed Unicode and ASCII characters"""
        test_cases = [
            "Book café 2024",
            "Test-北京-Book",
            "Иво Андрић (Ivo Andrić)",  # Serbian bilingual
            "café-book-test",
        ]

        for name in test_cases:
            with self.subTest(name=name):
                slug = slugify(name, allow_unicode=True)
                # Should not be empty and should preserve Unicode
                self.assertTrue(len(slug) > 0)
                # Should not contain spaces (replaced with hyphens)
                self.assertNotIn(" ", slug)

    def test_backward_compatibility_with_ascii(self):
        """Ensure ASCII slugs continue to work as before"""
        ascii_names = [
            "Test Book",
            "Simple Title",
            "Book-With-Hyphens",
            "Book_With_Underscores",
            "CAPS BOOK",
        ]

        for name in ascii_names:
            with self.subTest(name=name):
                author = models.Author.objects.create(name=name)
                local_path = author.local_path
                # Should still generate proper slugs
                self.assertIn("/s/", local_path)
                # Should not contain original spaces/caps
                self.assertNotIn(" ", local_path)

    def test_before_after_unicode_improvement(self):
        """Demonstrate the improvement from the Unicode changes"""
        serbian_name = "Иво Андрић"  # Nobel Prize winning Serbian author

        # What would happen with old slugify (without allow_unicode=True)
        old_slug = slugify(serbian_name, allow_unicode=False)

        # What happens with new slugify (with allow_unicode=True)
        new_slug = slugify(serbian_name, allow_unicode=True)

        # Old approach would strip Serbian Cyrillic characters
        self.assertEqual(
            old_slug, "", "Old slugify should strip all Cyrillic characters"
        )

        # New approach preserves them
        self.assertEqual(
            new_slug, "иво-андрић", "New slugify should preserve Cyrillic characters"
        )
