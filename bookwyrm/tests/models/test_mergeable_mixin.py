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

    def test_find_duplication_fields(self):
        """scan for any dupes in the model"""
        models.Edition.objects.create(
            title="Unrelated Edition",
            isbn_13="9780064471831",
            parent_work=models.Work.objects.create(title="Unrelated Work"),
        )
        models.Edition.objects.create(
            title="Example Edition",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Example Work"),
        )
        models.Edition.objects.create(
            title="Duplicate Edition",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Duplicate Work"),
        )
        models.Edition.objects.create(
            title="Duplicate Edition II",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Duplicate Work II"),
        )

        dupes = models.Edition.find_duplicate_fields()
        self.assertEqual(list(dupes["isbn_13"]), ["9780810160118"])
        self.assertEqual(len(dupes.keys()), 2)  # isbn 10 and 13

    def test_mark_merge_candidates(self):
        """scan for any dupes in the model"""
        unrelated = models.Edition.objects.create(
            title="Unrelated Edition",
            isbn_13="9780064471831",
            parent_work=models.Work.objects.create(title="Unrelated Work"),
        )
        book = models.Edition.objects.create(
            title="Example Edition",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Example Work"),
        )
        dupe_1 = models.Edition.objects.create(
            title="Duplicate Edition",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Duplicate Work"),
        )
        dupe_2 = models.Edition.objects.create(
            title="Duplicate Edition II",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Duplicate Work II"),
        )

        models.Edition.mark_merge_candidates()
        unrelated.refresh_from_db()
        self.assertIsNone(unrelated.pending_merge_target)

        book.refresh_from_db()
        self.assertIsNone(book.pending_merge_target)

        dupe_1.refresh_from_db()
        self.assertEqual(dupe_1.pending_merge_target.id, book.id)

        dupe_2.refresh_from_db()
        self.assertEqual(dupe_2.pending_merge_target.id, book.id)

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

        absorbed = book.merge_into(dupe)

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

        absorbed = book.merge_into(dupe, dry_run=True)

        self.assertEqual(absorbed["description"], "don't lose me in the merge")
        self.assertTrue(models.Edition.objects.filter(id=book.id).exists())
        self.assertFalse(models.MergedEdition.objects.exists())
        dupe.refresh_from_db()
        self.assertIsNone(dupe.description)
