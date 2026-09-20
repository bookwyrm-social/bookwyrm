"""test repairing series"""

import json
import responses

from django.test import TestCase

from bookwyrm import models
from bookwyrm.management.commands.repair_series import (
    get_series_json,
    refetch_or_fix_individual_series,
    repair_nameless_series,
)
from bookwyrm.settings import INSTANCE_ACTOR_USERNAME


class RepairSeries(TestCase):
    """test repair series"""

    @classmethod
    def setUpTestData(cls):
        """set up shared data"""

        cls.user = models.User.objects.create_user(
            "mouse",
            "mouse@mouse.com",
            "mouseword",
            local=True,
            localname=INSTANCE_ACTOR_USERNAME,
        )

        cls.series_string = str(
            [{"name": "beep", "alternative_names": ["boop"], "inventaire_id": "Q123"}]
        )
        cls.unusable_string = str("[{error")
        cls.nameless_series_string = str(
            [{"alternative_names": ["boop"], "inventaire_id": "Q123"}]
        )
        cls.nameless_no_inventaire = str([{"alternative_names": ["boop"]}])

        cls.connector = models.Connector.objects.get_or_create(
            identifier="inventaire.io",
            defaults={
                "name": "Inventaire",
                "connector_file": "inventaire",
                "base_url": "https://inventaire.io",
                "books_url": "https://inventaire.io/api/entities",
                "covers_url": "https://inventaire.io",
                "search_url": "https://inventaire.io/api/search?types=works&types=works&search=",
                "isbn_search_url": "https://inventaire.io/api/entities?action=by-uris&uris=isbn%3A",
                "priority": 3,
            },
        )

        cls.data = {
            "entities": {
                "wd:Q42490": {
                    "uri": "wd:Q42490",
                    "type": "serie",
                    "labels": {"en": "Asterix", "fr": "Astérix"},
                    "aliases": {
                        "zh": ["亚力历险记", "Asterix and Obelix"],
                        "pl": ["Asterix i Obelix"],
                    },
                    "claims": {"wdt:P6947": ["41270"]},  # GoodReads
                }
            }
        }

        cls.fr_data = {
            "entities": {
                "wd:Q42490": {
                    "uri": "wd:Q42490",
                    "type": "serie",
                    "labels": {"fr": "Astérix"},
                }
            }
        }

    def test_get_series_json(self):
        """test all likely scenarios for borked series entries"""

        with self.assertRaises(json.decoder.JSONDecodeError):
            json.loads(self.series_string)

        edition = models.Edition.objects.create(
            title="test book", series=self.series_string
        )
        return_value = get_series_json({}, edition)
        self.assertTrue(isinstance(return_value, list))
        self.assertEqual(
            return_value,
            [{"name": "beep", "alternative_names": ["boop"], "inventaire_id": "Q123"}],
        )

        edition.series = self.nameless_series_string
        return_value = get_series_json({}, edition)
        self.assertTrue(isinstance(return_value, list))
        self.assertEqual(
            return_value, [{"alternative_names": ["boop"], "inventaire_id": "Q123"}]
        )

        edition.series = self.nameless_no_inventaire
        return_value = get_series_json({}, edition)
        self.assertTrue(isinstance(return_value, list))
        self.assertEqual(return_value, [{"alternative_names": ["boop"]}])

        edition.series = self.unusable_string
        return_value = get_series_json({}, edition)
        self.assertTrue(isinstance(return_value, str))
        self.assertEqual(
            return_value,
            f"ERROR repairing Edition with id: {edition.id} | series: {self.unusable_string} | error: '{{' was never closed (<unknown>, line 1)",
        )

    @responses.activate
    def test_refetch_or_fix_individual_series(self):
        """test the method on a single series"""

        self.assertEqual(models.Series.objects.count(), 0)
        responses.add(
            responses.GET,
            "https://inventaire.io/api/entities",
            json=self.data,
            status=200,
        )

        series = models.Series(name="blah", user=self.user, inventaire_id="wd:99")

        result = refetch_or_fix_individual_series(options={}, series=series)

        self.assertEqual(models.Series.objects.count(), 1)
        self.assertTrue(isinstance(result, models.Series))
        self.assertEqual(result.name, "Asterix")
        self.assertEqual(result.goodreads_key, "41270")
        self.assertTrue("亚力历险记" in result.alternative_names)
        self.assertTrue("Astérix" in result.alternative_names)
        self.assertTrue("Asterix i Obelix" in result.alternative_names)

    @responses.activate
    def test_repair_nameless_series(self):
        """test repairing multiple nameless series"""

        series = models.Series(name="", user=self.user, inventaire_id="wd:99")
        series.save()
        self.assertEqual(models.Series.objects.count(), 1)
        self.assertEqual(series.name, "")

        responses.add(
            responses.GET,
            "https://inventaire.io/api/entities",
            json=self.data,
            status=200,
        )

        repair_nameless_series(options={"dry_run": None, "verbosity": 2, "all": None})
        series.refresh_from_db()
        # Did it fix the name?
        self.assertEqual(series.name, "Asterix")
        # Did it update rather than create a duplicate?
        self.assertEqual(models.Series.objects.count(), 1)

    @responses.activate
    def test_inventaire_has_no_default_or_en_title(self):
        """test the situation that caused the lack of series names"""

        series = models.Series(
            name="",
            alternative_names=["beep"],
            user=self.user,
            inventaire_id="wd:Q42490",
        )
        series.save()
        self.assertEqual(models.Series.objects.count(), 1)
        self.assertEqual(series.name, "")

        responses.add(
            responses.GET,
            "https://inventaire.io/api/entities",
            json=self.fr_data,
            status=200,
        )

        repair_nameless_series(options={"dry_run": None, "verbosity": 2, "all": None})
        series.refresh_from_db()
        # Did it fix the name?
        self.assertEqual(series.name, "Astérix")
        # Did it update rather than create a duplicate?
        self.assertEqual(models.Series.objects.count(), 1)

    @responses.activate
    def test_repair_edition_series_is_nameless_no_inventaire_id(self):
        """this probably will never happen but test anyway"""

        series = models.Series(name="", alternative_names=["beep"], user=self.user)
        series.save()
        self.assertEqual(models.Series.objects.count(), 1)
        self.assertEqual(series.name, "")

        responses.add(
            responses.GET,
            "https://inventaire.io/api/entities",
            json=self.data,
            status=200,
        )

        repair_nameless_series(options={"dry_run": None, "verbosity": 2, "all": True})
        series.refresh_from_db()
        # Did it 'fix' the name?
        self.assertEqual(series.name, "beep")
        # Did it update rather than create a duplicate?
        self.assertEqual(models.Series.objects.count(), 1)
