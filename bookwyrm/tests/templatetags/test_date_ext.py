"""Test date extensions in templates"""
from dateutil.parser import isoparse

from django.test import TestCase, override_settings

from bookwyrm.templatetags import date_ext
from bookwyrm.utils.partial_date import MonthParts, YearParts, from_partial_isoformat


@override_settings(LANGUAGE_CODE="en-AU")
class PartialDateTags(TestCase):
    """PartialDate tags"""

    def setUp(self):
        """create dates and set language"""
        self._dt = isoparse("2023-12-31T23:59:59Z")
        self._date = self._dt.date()
        self._partial_day = from_partial_isoformat("2023-06-30")
        self._partial_month = MonthParts.from_date_parts(2023, 6, 30)
        self._partial_year = YearParts.from_datetime(self._dt)

    def test_standard_date_objects(self):
        """should work with standard date/datetime objects"""
        self.assertEqual("31 Dec 2023", date_ext.naturalday_partial(self._dt))
        self.assertEqual("31 Dec 2023", date_ext.naturalday_partial(self._date))

    def test_partial_date_objects(self):
        """should work with PartialDate and subclasses"""
        self.assertEqual("2023", date_ext.naturalday_partial(self._partial_year))
        self.assertEqual("June 2023", date_ext.naturalday_partial(self._partial_month))
        self.assertEqual("30 Jun 2023", date_ext.naturalday_partial(self._partial_day))
