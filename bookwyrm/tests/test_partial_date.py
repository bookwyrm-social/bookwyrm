""" test partial_date module """

import datetime
import unittest

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils import translation

from bookwyrm.utils import partial_date


class PartialDateTest(unittest.TestCase):
    """test PartialDate class in isolation"""

    # pylint: disable=missing-function-docstring

    def setUp(self):
        self._dt = datetime.datetime(2023, 10, 20, 17, 33, 10, tzinfo=timezone.utc)

    def test_day_seal(self):
        sealed = partial_date.PartialDate.from_datetime(self._dt)
        self.assertEqual(self._dt, sealed)
        self.assertEqual("2023-10-20", sealed.partial_isoformat())
        self.assertTrue(sealed.has_day)
        self.assertTrue(sealed.has_month)

    def test_month_seal(self):
        sealed = partial_date.MonthParts.from_datetime(self._dt)
        self.assertEqual(self._dt, sealed)
        self.assertEqual("2023-10", sealed.partial_isoformat())
        self.assertFalse(sealed.has_day)
        self.assertTrue(sealed.has_month)

    def test_year_seal(self):
        sealed = partial_date.YearParts.from_datetime(self._dt)
        self.assertEqual(self._dt, sealed)
        self.assertEqual("2023", sealed.partial_isoformat())
        self.assertFalse(sealed.has_day)
        self.assertFalse(sealed.has_month)

    def test_no_naive_datetime(self):
        with self.assertRaises(ValueError):
            partial_date.PartialDate.from_datetime(datetime.datetime(2000, 1, 1))

    def test_parse_year_seal(self):
        parsed = partial_date.from_partial_isoformat("1995")
        expected = datetime.date(1995, 1, 1)
        self.assertEqual(expected, parsed.date())
        self.assertFalse(parsed.has_day)
        self.assertFalse(parsed.has_month)

    def test_parse_year_errors(self):
        self.assertRaises(ValueError, partial_date.from_partial_isoformat, "995")
        self.assertRaises(ValueError, partial_date.from_partial_isoformat, "1995x")
        self.assertRaises(ValueError, partial_date.from_partial_isoformat, "1995-")

    def test_parse_month_seal(self):
        expected = datetime.date(1995, 5, 1)
        test_cases = [
            ("parse_month", "1995-05"),
            ("parse_month_lenient", "1995-5"),
        ]
        for desc, value in test_cases:
            with self.subTest(desc):
                parsed = partial_date.from_partial_isoformat(value)
                self.assertEqual(expected, parsed.date())
                self.assertFalse(parsed.has_day)
                self.assertTrue(parsed.has_month)

    def test_parse_month_dash_required(self):
        self.assertRaises(ValueError, partial_date.from_partial_isoformat, "20056")
        self.assertRaises(ValueError, partial_date.from_partial_isoformat, "200506")
        self.assertRaises(ValueError, partial_date.from_partial_isoformat, "1995-7-")

    def test_parse_day_seal(self):
        expected = datetime.date(1995, 5, 6)
        test_cases = [
            ("parse_day", "1995-05-06"),
            ("parse_day_lenient1", "1995-5-6"),
            ("parse_day_lenient2", "1995-05-6"),
        ]
        for desc, value in test_cases:
            with self.subTest(desc):
                parsed = partial_date.from_partial_isoformat(value)
                self.assertEqual(expected, parsed.date())
                self.assertTrue(parsed.has_day)
                self.assertTrue(parsed.has_month)

    def test_partial_isoformat_no_time_allowed(self):
        self.assertRaises(
            ValueError, partial_date.from_partial_isoformat, "2005-06-07 "
        )
        self.assertRaises(
            ValueError, partial_date.from_partial_isoformat, "2005-06-07T"
        )
        self.assertRaises(
            ValueError, partial_date.from_partial_isoformat, "2005-06-07T00:00:00"
        )
        self.assertRaises(
            ValueError, partial_date.from_partial_isoformat, "2005-06-07T00:00:00-03"
        )


class PartialDateFormFieldTest(unittest.TestCase):
    """test form support for PartialDate objects"""

    # pylint: disable=missing-function-docstring

    def setUp(self):
        self._dt = datetime.datetime(2022, 11, 21, 17, 1, 0, tzinfo=timezone.utc)
        self.field = partial_date.PartialDateFormField()

    def test_prepare_value(self):
        sealed = partial_date.PartialDate.from_datetime(self._dt)
        self.assertEqual("2022-11-21", self.field.prepare_value(sealed))

    def test_prepare_value_month(self):
        sealed = partial_date.MonthParts.from_datetime(self._dt)
        self.assertEqual("2022-11-0", self.field.prepare_value(sealed))

    def test_prepare_value_year(self):
        sealed = partial_date.YearParts.from_datetime(self._dt)
        self.assertEqual("2022-0-0", self.field.prepare_value(sealed))

    def test_to_python(self):
        date = self.field.to_python("2022-11-21")
        self.assertIsInstance(date, partial_date.PartialDate)
        self.assertEqual("2022-11-21", date.partial_isoformat())

    def test_to_python_month(self):
        date = self.field.to_python("2022-11-0")
        self.assertIsInstance(date, partial_date.PartialDate)
        self.assertEqual("2022-11", date.partial_isoformat())
        with self.assertRaises(ValidationError):
            self.field.to_python("2022-0-25")

    def test_to_python_year(self):
        date = self.field.to_python("2022-0-0")
        self.assertIsInstance(date, partial_date.PartialDate)
        self.assertEqual("2022", date.partial_isoformat())
        with self.assertRaises(ValidationError):
            self.field.to_python("0-05-25")

    def test_to_python_other(self):
        with translation.override("es"):
            # check super() is called
            date = self.field.to_python("5/6/97")
            self.assertIsInstance(date, partial_date.PartialDate)
            self.assertEqual("1997-06-05", date.partial_isoformat())
