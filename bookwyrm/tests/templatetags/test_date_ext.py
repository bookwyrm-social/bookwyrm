"""Test date extensions in templates"""
from dateutil.parser import isoparse

from django.test import TestCase, override_settings
from django.utils import timezone

from bookwyrm.templatetags import date_ext
from bookwyrm.utils.partial_date import (
    MonthParts,
    PartialDate,
    YearParts,
    from_partial_isoformat,
)


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

    def test_format_arg_is_used(self):
        """the provided format should be used by default"""
        self.assertEqual("Dec.31", date_ext.naturalday_partial(self._dt, "M.j"))
        self.assertEqual("Dec.31", date_ext.naturalday_partial(self._date, "M.j"))
        self.assertEqual("June", date_ext.naturalday_partial(self._partial_day, "F"))

    def test_month_precision_downcast(self):
        """precision is adjusted for well-known date formats"""
        self.assertEqual(
            "June 2023", date_ext.naturalday_partial(self._partial_month, "DATE_FORMAT")
        )

    def test_year_precision_downcast(self):
        """precision is adjusted for well-known date formats"""
        for fmt in "DATE_FORMAT", "SHORT_DATE_FORMAT", "YEAR_MONTH_FORMAT":
            with self.subTest(desc=fmt):
                self.assertEqual(
                    "2023", date_ext.naturalday_partial(self._partial_year, fmt)
                )

    def test_nonstandard_formats_passthru(self):
        """garbage-in, garbage-out: we don't mess with unknown date formats"""
        # Expected because there is no SHORT_YEAR_MONTH_FORMAT in Django that we can use
        self.assertEqual(
            "30/06/2023",
            date_ext.naturalday_partial(self._partial_month, "SHORT_DATE_FORMAT"),
        )
        self.assertEqual(
            "December.31", date_ext.naturalday_partial(self._partial_year, "F.j")
        )

    def test_natural_format(self):
        """today and yesterday are handled correctly"""
        today = timezone.now()
        today_date = today.date()
        today_exact = PartialDate.from_datetime(today)

        # exact dates can be naturalized
        self.assertEqual("today", date_ext.naturalday_partial(today))
        self.assertEqual("today", date_ext.naturalday_partial(today_date))
        self.assertEqual("today", date_ext.naturalday_partial(today_exact))

        # dates with missing parts can't
        today_year = YearParts.from_datetime(today)
        today_month = MonthParts.from_datetime(today)
        self.assertEqual(str(today.year), date_ext.naturalday_partial(today_year))
        self.assertEqual(str(today.year), date_ext.naturalday_partial(today_month, "Y"))
