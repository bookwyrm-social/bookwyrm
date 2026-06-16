"""testing models"""

from django.test import TestCase

from bookwyrm import models


class MergeableMixin(TestCase):
    """not too much going on in the books model but here we are"""

    @classmethod
    def setUpTestData(cls):
        """Any test data here"""

    def test_dedupe_fields(self):
        """get a list of all the deduplication fields"""
        edition_fields = [f.name for f in models.Edition.deduplication_fields()]
        # just a spot check
        self.assertTrue("isbn_10" in edition_fields)
        self.assertFalse("title" in edition_fields)

    def test_find_merge_candidate(self):
        """look for duplicates"""
        models.Edition.objects.create(
            title="Unrelated Edition",
            isbn_13="9780064471831",
            parent_work=models.Work.objects.create(title="Unrelated Work"),
        )
        book = models.Edition.objects.create(
            title="Example Edition",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Example Work"),
        )
        dupe = models.Edition.objects.create(
            title="Duplicate Edition",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Duplicate Work"),
        )

        candidate = book.find_merge_candidate()
        self.assertEqual(candidate, dupe)

    def test_find_merge_candidate_no_match(self):
        """look for duplicates"""
        book = models.Edition.objects.create(
            title="Example Edition",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Example Work"),
        )

        candidate = book.find_merge_candidate()
        self.assertIsNone(candidate)

    def test_merge_into(self):
        """merge duplicates"""
        models.Edition.objects.create(
            title="Unrelated Edition",
            isbn_13="9780064471831",
            parent_work=models.Work.objects.create(title="Unrelated Work"),
        )

        book = models.Edition.objects.create(
            title="Example Edition",
            isbn_13="9780810160118",
            description="don't lose me in the merge",
            parent_work=models.Work.objects.create(title="Example Work"),
        )
        dupe = models.Edition.objects.create(
            title="Duplicate Edition",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Duplicate Work"),
        )
        self.assertFalse(models.MergedEdition.objects.exists())

        candidate = book.find_merge_candidate()
        absorbed = book.merge_into(candidate)

        self.assertEqual(absorbed["description"], "don't lose me in the merge")
        self.assertFalse(models.Edition.objects.filter(id=book.id).exists())
        merged = models.MergedEdition.objects.get()
        dupe.refresh_from_db()
        self.assertEqual(merged.deleted_id, book.id)
        self.assertEqual(merged.merged_into, dupe)
        self.assertEqual(dupe.description, "don't lose me in the merge")

    def test_merge_into_dry_run(self):
        """merge duplicates"""
        models.Edition.objects.create(
            title="Unrelated Edition",
            isbn_13="9780064471831",
            parent_work=models.Work.objects.create(title="Unrelated Work"),
        )

        book = models.Edition.objects.create(
            title="Example Edition",
            isbn_13="9780810160118",
            description="don't lose me in the merge",
            parent_work=models.Work.objects.create(title="Example Work"),
        )
        dupe = models.Edition.objects.create(
            title="Duplicate Edition",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Duplicate Work"),
        )
        self.assertFalse(models.MergedEdition.objects.exists())

        candidate = book.find_merge_candidate()
        absorbed = book.merge_into(candidate, dry_run=True)

        self.assertEqual(absorbed["description"], "don't lose me in the merge")
        self.assertTrue(models.Edition.objects.filter(id=book.id).exists())
        self.assertFalse(models.MergedEdition.objects.exists())
        dupe.refresh_from_db()
        self.assertIsNone(dupe.description)
