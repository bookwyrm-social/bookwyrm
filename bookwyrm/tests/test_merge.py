"""test merging Authors, Works and Editions"""

from django.test import TestCase
from django.test.client import Client

from bookwyrm import models


class MergeBookDataModel(TestCase):
    """test merging of subclasses of BookDataModel"""

    @classmethod
    def setUpTestData(cls):
        """shared data"""
        models.SiteSettings.objects.create()

        cls.jrr_tolkien = models.Author.objects.create(
            name="J.R.R. Tolkien",
            aliases=["JRR Tolkien", "Tolkien"],
            bio="This guy wrote about hobbits and stuff.",
            openlibrary_key="OL26320A",
            isni="0000000121441970",
        )
        cls.jrr_tolkien_2 = models.Author.objects.create(
            name="J.R.R. Tolkien",
            aliases=["JRR Tolkien", "John Ronald Reuel Tolkien"],
            openlibrary_key="OL26320A",
            isni="wrong",
            wikidata="Q892",
        )
        cls.jrr_tolkien_2_id = cls.jrr_tolkien_2.id

        # perform merges
        cls.jrr_tolkien_absorbed_fields = cls.jrr_tolkien_2.merge_into(cls.jrr_tolkien)

    def test_merged_author(self):
        """verify merged author after merge"""
        self.assertEqual(self.jrr_tolkien_2.id, None, msg="duplicate should be deleted")

    def test_canonical_author(self):
        """verify canonical author data after merge"""

        self.assertFalse(
            self.jrr_tolkien.id is None, msg="canonical should not be deleted"
        )

        # identical in canonical and duplicate; should be unchanged
        self.assertEqual(self.jrr_tolkien.name, "J.R.R. Tolkien")
        self.assertEqual(self.jrr_tolkien.openlibrary_key, "OL26320A")

        # present in canonical and absent in duplicate; should be unchanged
        self.assertEqual(
            self.jrr_tolkien.bio, "This guy wrote about hobbits and stuff."
        )

        # absent in canonical and present in duplicate; should be absorbed
        self.assertEqual(self.jrr_tolkien.wikidata, "Q892")

        # scalar value that is different in canonical and duplicate; should be unchanged
        self.assertEqual(self.jrr_tolkien.isni, "0000000121441970")

        # set value with both matching and non-matching elements; should be the
        # union of canonical and duplicate
        self.assertEqual(
            self.jrr_tolkien.aliases,
            [
                "JRR Tolkien",
                "Tolkien",
                "John Ronald Reuel Tolkien",
            ],
        )

    def test_merged_author_redirect(self):
        """a web request for a merged author should redirect to the canonical author"""
        client = Client()
        response = client.get(
            f"/author/{self.jrr_tolkien_2_id}/s/jrr-tolkien", follow=True
        )
        self.assertEqual(response.redirect_chain, [(self.jrr_tolkien.local_path, 301)])

    def test_merged_author_activitypub(self):
        """an activitypub request for a merged author should return the data for
        the canonical author (including the canonical id)"""
        client = Client(HTTP_ACCEPT="application/json")
        response = client.get(f"/author/{self.jrr_tolkien_2_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.jrr_tolkien.to_activity())

    def test_absorbed_fields(self):
        """reported absorbed_fields should be accurate for --dry_run"""
        self.assertEqual(
            self.jrr_tolkien_absorbed_fields,
            {
                "aliases": ["John Ronald Reuel Tolkien"],
                "wikidata": "Q892",
            },
        )
