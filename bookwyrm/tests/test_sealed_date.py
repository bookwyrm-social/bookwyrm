""" test sealed_date module """

import datetime
import unittest

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils import translation

from bookwyrm.utils import sealed_date


class SealedDateTest(unittest.TestCase):
    def setUp(self):
        self.dt = datetime.datetime(2023, 10, 20, 17, 33, 10, tzinfo=timezone.utc)

    def test_day_seal(self):
        sealed = sealed_date.SealedDate.from_datetime(self.dt)
        self.assertEqual(self.dt, sealed)
        self.assertEqual("2023-10-20", sealed.partial_isoformat())

    def test_month_seal(self):
        sealed = sealed_date.MonthSeal.from_datetime(self.dt)
        self.assertEqual(self.dt, sealed)
        self.assertEqual("2023-10", sealed.partial_isoformat())

    def test_year_seal(self):
        sealed = sealed_date.YearSeal.from_datetime(self.dt)
        self.assertEqual(self.dt, sealed)
        self.assertEqual("2023", sealed.partial_isoformat())


class SealedDateFormFieldTest(unittest.TestCase):
    def setUp(self):
        self.dt = datetime.datetime(2022, 11, 21, 17, 1, 0, tzinfo=timezone.utc)
        self.field = sealed_date.SealedDateFormField()

    def test_prepare_value(self):
        sealed = sealed_date.SealedDate.from_datetime(self.dt)
        self.assertEqual("2022-11-21", self.field.prepare_value(sealed))

    def test_prepare_value_month(self):
        sealed = sealed_date.MonthSeal.from_datetime(self.dt)
        self.assertEqual("2022-11-0", self.field.prepare_value(sealed))

    def test_prepare_value_year(self):
        sealed = sealed_date.YearSeal.from_datetime(self.dt)
        self.assertEqual("2022-0-0", self.field.prepare_value(sealed))

    def test_to_python(self):
        date = self.field.to_python("2022-11-21")
        self.assertIsInstance(date, sealed_date.SealedDate)
        self.assertEqual("2022-11-21", date.partial_isoformat())

    def test_to_python_month(self):
        date = self.field.to_python("2022-11-0")
        self.assertIsInstance(date, sealed_date.SealedDate)
        self.assertEqual("2022-11", date.partial_isoformat())
        with self.assertRaises(ValidationError):
            self.field.to_python("2022-0-25")

    def test_to_python_year(self):
        date = self.field.to_python("2022-0-0")
        self.assertIsInstance(date, sealed_date.SealedDate)
        self.assertEqual("2022", date.partial_isoformat())
        with self.assertRaises(ValidationError):
            self.field.to_python("0-05-25")

    def test_to_python_other(self):
        with translation.override("es"):
            # check super() is called
            date = self.field.to_python("5/6/97")
            self.assertIsInstance(date, sealed_date.SealedDate)
            self.assertEqual("1997-06-05", date.partial_isoformat())
