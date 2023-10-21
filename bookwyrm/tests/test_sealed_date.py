""" test sealed_date module """

import datetime
import unittest

from django.utils import timezone
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
