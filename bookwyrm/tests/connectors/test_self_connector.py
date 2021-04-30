""" testing book data connectors """
import datetime
from django.test import TestCase
from django.utils import timezone

from bookwyrm import models
from bookwyrm.connectors.self_connector import Connector
from bookwyrm.settings import DOMAIN


class SelfConnector(TestCase):
    """just uses local data"""

    def setUp(self):
        """creating the connector"""
        models.Connector.objects.create(
            identifier=DOMAIN,
            name="Local",
            local=True,
            connector_file="self_connector",
            base_url="https://%s" % DOMAIN,
            books_url="https://%s/book" % DOMAIN,
            covers_url="https://%s/images/covers" % DOMAIN,
            search_url="https://%s/search?q=" % DOMAIN,
            priority=1,
        )
        self.connector = Connector(DOMAIN)

    def test_format_search_result(self):
        """create a SearchResult"""
        author = models.Author.objects.create(name="Anonymous")
        edition = models.Edition.objects.create(
            title="Edition of Example Work",
            published_date=datetime.datetime(1980, 5, 10, tzinfo=timezone.utc),
        )
        edition.authors.add(author)
        result = self.connector.search("Edition of Example")[0]
        self.assertEqual(result.title, "Edition of Example Work")
        self.assertEqual(result.key, edition.remote_id)
        self.assertEqual(result.author, "Anonymous")
        self.assertEqual(result.year, 1980)
        self.assertEqual(result.connector, self.connector)

    def test_search_rank(self):
        """prioritize certain results"""
        author = models.Author.objects.create(name="Anonymous")
        edition = models.Edition.objects.create(
            title="Edition of Example Work",
            published_date=datetime.datetime(1980, 5, 10, tzinfo=timezone.utc),
            parent_work=models.Work.objects.create(title=""),
        )
        # author text is rank C
        edition.authors.add(author)

        # series is rank D
        models.Edition.objects.create(
            title="Another Edition",
            series="Anonymous",
            parent_work=models.Work.objects.create(title=""),
        )
        # subtitle is rank B
        models.Edition.objects.create(
            title="More Editions",
            subtitle="The Anonymous Edition",
            parent_work=models.Work.objects.create(title=""),
        )
        # title is rank A
        models.Edition.objects.create(title="Anonymous")
        # doesn't rank in this search
        edition = models.Edition.objects.create(
            title="An Edition", parent_work=models.Work.objects.create(title="")
        )

        results = self.connector.search("Anonymous")
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].title, "Anonymous")
        self.assertEqual(results[1].title, "More Editions")
        self.assertEqual(results[2].title, "Edition of Example Work")

    def test_search_multiple_editions(self):
        """it should get rid of duplicate editions for the same work"""
        work = models.Work.objects.create(title="Work Title")
        edition_1 = models.Edition.objects.create(
            title="Edition 1 Title", parent_work=work
        )
        edition_2 = models.Edition.objects.create(
            title="Edition 2 Title",
            parent_work=work,
            edition_rank=20,  # that's default babey
        )
        edition_3 = models.Edition.objects.create(title="Fish", parent_work=work)

        # pick the best edition
        results = self.connector.search("Edition 1 Title")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].key, edition_1.remote_id)

        # pick the default edition when no match is best
        results = self.connector.search("Edition Title")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].key, edition_2.remote_id)

        # only matches one edition, so no deduplication takes place
        results = self.connector.search("Fish")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].key, edition_3.remote_id)
