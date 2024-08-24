""" test searching for authors """
from django.test import TestCase

from django.contrib.postgres.search import SearchRank, SearchQuery
from django.db.models import F

from bookwyrm import models


class AuthorSearch(TestCase):
    """look for some authors"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        cls.bob = models.Author.objects.create(
            name="Bob", aliases=["Robertus", "Alice"]
        )
        cls.alice = models.Author.objects.create(name="Alice")

    def test_search(self):
        """search for an author in the db"""
        results = self._search("Bob")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.bob)

    def test_alias_priority(self):
        """aliases should be included, with lower priority than name"""
        results = self._search("Alice")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], self.alice)

    def _search_first(self, query):
        """wrapper around search_title_author"""
        return self._search(query, return_first=True)

    @staticmethod
    def _search(query, *, return_first=False):
        """author search"""
        search_query = SearchQuery(query, config="simple")
        min_confidence = 0

        results = (
            models.Author.objects.filter(search_vector=search_query)
            .annotate(rank=SearchRank(F("search_vector"), search_query))
            .filter(rank__gt=min_confidence)
            .order_by("-rank")
        )
        if return_first:
            return results.first()
        return results


class SearchVectorTest(TestCase):
    """check search_vector is computed correctly"""

    def test_search_vector_simple(self):
        """simplest search vector"""
        author = self._create_author("Mary")
        self.assertEqual(author.search_vector, "'mary':1A")

    def test_search_vector_aliases(self):
        """author aliases should be included with lower priority"""
        author = self._create_author("Mary", aliases=["Maria", "Example"])
        self.assertEqual(author.search_vector, "'example':3B 'maria':2B 'mary':1A")

    def test_search_vector_parse_author(self):
        """author name and alias is not stem'd or affected by stop words"""
        author = self._create_author("Writes", aliases=["Reads"])
        self.assertEqual(author.search_vector, "'reads':2B 'writes':1A")

    def test_search_vector_on_update(self):
        """make sure that search_vector is being set correctly on edit"""
        author = self._create_author("Mary")
        self.assertEqual(author.search_vector, "'mary':1A")

        author.name = "Example"
        author.save(broadcast=False)
        author.refresh_from_db()
        self.assertEqual(author.search_vector, "'example':1A")

    @staticmethod
    def _create_author(name, /, *, aliases=None):
        """quickly create an author"""
        author = models.Author.objects.create(name=name, aliases=aliases or [])
        author.refresh_from_db()
        return author
