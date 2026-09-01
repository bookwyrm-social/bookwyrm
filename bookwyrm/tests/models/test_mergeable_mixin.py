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

        work_fields = [f.name for f in models.Work.deduplication_fields()]
        self.assertTrue("lccn" in work_fields)
        self.assertFalse("Isbn_10" in work_fields)

        author_fields = [f.name for f in models.Author.deduplication_fields()]
        self.assertTrue("isni" in author_fields)
        self.assertFalse("name" in author_fields)

        series_fields = [f.name for f in models.Series.deduplication_fields()]
        self.assertTrue("wikidata_id" in series_fields)
        self.assertFalse("name" in series_fields)

    def test_get_shared_fields(self):
        """Two editions with the same isbn"""
        ed_1 = models.Edition.objects.create(
            title="Unrelated Edition",
            isbn_13="9780810160118",
            isbn_10="X098765432",
            parent_work=models.Work.objects.create(title="Unrelated Work"),
        )
        ed_2 = models.Edition.objects.create(
            title="Example Edition",
            isbn_13="9780810160118",
            isbn_10="123456789X",
            parent_work=models.Work.objects.create(title="Example Work"),
            pending_merge_target=ed_1,
        )
        result = ed_1.get_shared_fields(ed_2)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], models.fields.CharField)
        self.assertEqual(result[0].name, "isbn_13")

    def test_get_shared_fields_without_target(self):
        """Two editions with the same isbn"""
        ed_1 = models.Edition.objects.create(
            title="Unrelated Edition",
            isbn_13="9780810160118",
            isbn_10="X098765432",
            parent_work=models.Work.objects.create(title="Unrelated Work"),
        )
        ed_2 = models.Edition.objects.create(
            title="Example Edition",
            isbn_13="9780810160118",
            isbn_10="123456789X",
            parent_work=models.Work.objects.create(title="Example Work"),
        )
        with self.assertRaises(ValueError):
            ed_1.get_shared_fields(ed_2)

    def test_get_shared_fields_wrong_types(self):
        """Can't compare different types of model"""
        with self.assertRaises(ValueError):
            edition = models.Edition.objects.create(
                title="Unrelated Edition",
                isbn_13="9780810160118",
                isbn_10="X098765432",
                parent_work=models.Work.objects.create(title="Unrelated Work"),
            )
            work = models.Author.objects.create(name="Hello")
            work.get_shared_fields(edition)

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

    def test_related_authors_merged(self):
        """are related authors merged?"""

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

        book.authors.add(models.Author.objects.create(name="Amy Author"))
        dupe.authors.add(models.Author.objects.create(name="Bob Bookwriter"))

        self.assertEqual(book.authors.count(), 1)
        self.assertFalse(models.MergedEdition.objects.exists())

        dupe.merge_into(book)
        book.refresh_from_db()
        self.assertEqual(book.authors.count(), 2)
        self.assertTrue(book.authors.last().name, "Bob Bookwriter")

    def test_related_parent_work_deleted(self):
        """are parent works deleted once orphaned?"""

        work = models.Work.objects.create(title="Duplicate Work")

        book = models.Edition.objects.create(
            title="Example Edition",
            isbn_13="9780810160118",
            parent_work=models.Work.objects.create(title="Example Work"),
        )
        dupe = models.Edition.objects.create(
            title="Duplicate Edition",
            isbn_13="9780810160118",
            parent_work=work,
        )

        self.assertEqual(models.Edition.objects.count(), 2)
        self.assertEqual(models.Work.objects.count(), 2)

        dupe.merge_into(book)

        self.assertEqual(models.Edition.objects.count(), 1)
        self.assertEqual(models.Work.objects.count(), 1)

    def test_related_suggestions_merged(self):
        """are related suggestion items merged?"""

        user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
        )

        work = models.Work.objects.create(title="Example Work")
        dupe_work = models.Work.objects.create(title="Example Work 2")

        models.SuggestionListItem.objects.create(
            work=dupe_work,
            book_list=models.SuggestionList.objects.create(suggests_for=work),
            user=user,
            notes="what a great book",
        )

        self.assertEqual(models.Work.objects.count(), 2)
        self.assertEqual(models.SuggestionList.objects.count(), 1)
        self.assertEqual(models.SuggestionListItem.objects.count(), 1)

        dupe_work.merge_into(work)

        self.assertEqual(models.Work.objects.count(), 1)
        self.assertEqual(models.SuggestionList.objects.count(), 1)
        self.assertEqual(models.SuggestionListItem.objects.count(), 1)
        self.assertEqual(models.SuggestionListItem.objects.first().work, work)

    def test_multiple_related_merged(self):
        """are related suggestion items merged?"""

        user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "mouseword", local=True, localname="mouse"
        )

        work = models.Work.objects.create(title="Example Work")
        dupe_work = models.Work.objects.create(title="Example Work 2")

        book = models.Edition.objects.create(
            title="Example Edition",
            isbn_13="9780810160118",
            parent_work=work,
        )
        dupe = models.Edition.objects.create(
            title="Duplicate Edition", isbn_13="9780810160118", parent_work=dupe_work
        )

        models.SuggestionListItem.objects.create(
            work=dupe_work,
            book_list=models.SuggestionList.objects.create(suggests_for=work),
            user=user,
            notes="what a great book",
        )

        models.SuggestionListItem.objects.create(
            work=work,
            book_list=models.SuggestionList.objects.create(suggests_for=dupe_work),
            user=user,
            notes="what a lovely work",
        )

        self.assertEqual(models.Edition.objects.count(), 2)
        self.assertEqual(models.Work.objects.count(), 2)
        self.assertEqual(models.SuggestionList.objects.count(), 2)
        self.assertEqual(models.SuggestionListItem.objects.count(), 2)
        self.assertEqual(
            models.SuggestionList.objects.filter(suggests_for=work).count(), 1
        )
        self.assertEqual(models.SuggestionListItem.objects.filter(work=work).count(), 1)

        dupe.merge_into(book)

        self.assertEqual(models.Edition.objects.count(), 1)
        self.assertEqual(models.Work.objects.count(), 1)
        self.assertEqual(models.SuggestionList.objects.count(), 2)
        self.assertEqual(models.SuggestionListItem.objects.count(), 2)
        self.assertEqual(
            models.SuggestionList.objects.filter(suggests_for=work).count(), 2
        )
        self.assertEqual(models.SuggestionListItem.objects.filter(work=work).count(), 2)
