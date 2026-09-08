"""test some key url strings work correctly"""

from django.contrib import auth
from django.http.response import HttpResponseNotFound
from django.template.response import TemplateResponse
from django.test import TestCase
from django.urls import resolve, reverse, Resolver404

from bookwyrm import models
from bookwyrm.activitypub.response import ActivitypubResponse


class Urls(TestCase):
    """test urls"""

    def setUp(self):
        """set up data"""

        self.local_user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
        )
        self.series = models.Series.objects.create(
            name="test series", user=self.local_user
        )
        self.book = models.Work.objects.create(title="test book")
        self.seriesbook = models.SeriesBook.objects.create(
            book=self.book, series=self.series, user=self.local_user
        )

        self.author = models.Author.objects.create(name="Amy Author")

    def test_series_urls(self):
        """test series urls"""

        url = reverse("series", args=[self.series.id])
        self.assertEqual(url, f"/series/{self.series.id}")

        resolver = resolve(f"/series/{self.series.id}")  # id only
        full_resolver = resolve(f"/series/{self.series.id}/s/test-series")  # full
        trailing_slash = resolve(f"/series/{self.series.id}/s/test-series/")
        self.assertEqual(resolver.view_name, "series")
        self.assertEqual(resolver.view_name, full_resolver.view_name)
        self.assertEqual(resolver.view_name, trailing_slash.view_name)

        # id only redirects
        redirect = self.client.get(f"/series/{self.series.id}")
        self.assertRedirects(
            redirect,
            f"/series/{self.series.id}/s/test-series",
            status_code=301,
            target_status_code=200,
        )

        # response is html template
        response = self.client.get(f"/series/{self.series.id}/s/test-series")
        self.assertEqual(type(response), TemplateResponse)

        # path doesn't take endless amendments
        with self.assertRaises(Resolver404):
            resolve(f"/series/{self.series.id}/xxx")

    def test_series_api(self):
        """test series api urls"""

        # json path resolves
        json_resolver = resolve(f"/series/{self.series.id}.json")
        self.assertEqual(json_resolver.view_name, "series")

        # json headers return Activity JSON
        response = self.client.get(
            f"/series/{self.series.id}", headers={"Accept": "application/ld+json"}
        )
        self.assertEqual(type(response), ActivitypubResponse)

    def test_series_request_users(self):
        """can anonymous users load series?"""

        # anon
        user = auth.get_user(self.client)
        self.assertTrue(user.is_anonymous)
        with self.assertTemplateUsed("book/series.html"):
            response = self.client.get(f"/series/{self.series.id}/s/test-series")
        self.assertEqual(response.status_code, 200)

        # logged in
        self.client.force_login(self.local_user)
        with self.assertTemplateUsed("book/series.html"):
            auth_response = self.client.get(f"/series/{self.series.id}/s/test-series")
        self.assertEqual(auth_response.status_code, 200)

    def test_seriesbook_urls(self):
        """test series urls"""

        url = reverse("seriesbook", args=[self.series.id])
        self.assertEqual(url, f"/seriesbook/{self.series.id}")

        resolver = resolve(f"/seriesbook/{self.series.id}")
        trailing_resolver = resolve(f"/seriesbook/{self.series.id}/")
        self.assertEqual(resolver.view_name, "seriesbook")
        self.assertEqual(resolver.view_name, trailing_resolver.view_name)

        # text/plain doesn't resolve
        html_response = self.client.get(f"/seriesbook/{self.seriesbook.id}")
        self.assertEqual(type(html_response), HttpResponseNotFound)

        # json path is escaped
        with self.assertRaises(Resolver404):
            resolve(f"/seriesbook/{self.seriesbook.id}/xjson")

        # path doesn't take endless amendments
        with self.assertRaises(Resolver404):
            resolve(f"/seriesbook/{self.seriesbook.id}/xxx")

    def test_seriesbook_api(self):
        """test seriesbook api urls"""

        # json path resolves
        json_resolver = resolve(f"/seriesbook/{self.seriesbook.id}.json")
        self.assertEqual(json_resolver.view_name, "seriesbook")

        # json headers return Activity JSON
        response = self.client.get(
            f"/seriesbook/{self.seriesbook.id}",
            headers={"Accept": "application/ld+json"},
        )
        self.assertEqual(type(response), ActivitypubResponse)

    def test_author_urls(self):
        """test author urls"""

        url = reverse("author", args=[self.author.id])
        self.assertEqual(url, f"/author/{self.author.id}")

        resolver = resolve(f"/author/{self.author.id}")
        trailing_resolver = resolve(f"/author/{self.author.id}/")
        self.assertEqual(resolver.view_name, "author")
        self.assertEqual(resolver.view_name, trailing_resolver.view_name)

        # id only redirects
        redirect = self.client.get(f"/author/{self.author.id}")
        self.assertRedirects(
            redirect,
            f"/author/{self.author.id}/s/amy-author",
            status_code=301,
            target_status_code=200,
        )

        # json path is escaped
        with self.assertRaises(Resolver404):
            resolve(f"/author/{self.author.id}/xjson")

        # path doesn't take endless amendments
        with self.assertRaises(Resolver404):
            resolve(f"/author/{self.author.id}/blah")

        # json headers return Activity JSON
        response = self.client.get(
            f"/series/{self.author.id}", headers={"Accept": "application/ld+json"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response), ActivitypubResponse)
