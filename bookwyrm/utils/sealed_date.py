"""Implementation of the SealedDate class."""

from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any, Optional, Type, TypeVar, cast

from django.core.exceptions import ValidationError
from django.forms import DateField
from django.forms.widgets import SelectDateWidget
from django.utils import timezone


__all__ = [
    "SealedDate",
    "from_partial_isoformat",
]

_partial_re = re.compile(r"(\d{4})(?:-(\d\d?))?(?:-(\d\d?))?$")
_westmost_tz = timezone.get_fixed_timezone(timedelta(hours=-12))

Sealed = TypeVar("Sealed", bound="SealedDate")  # TODO: use Self in Python >= 3.11

# TODO: migrate SealedDate to `date`


class SealedDate(datetime):
    """a date object sealed into a certain precision (day, month, year)"""

    @property
    def has_day(self) -> bool:
        return self.has_month

    @property
    def has_month(self) -> bool:
        return True

    def partial_isoformat(self) -> str:
        return self.strftime("%Y-%m-%d")

    @classmethod
    def from_datetime(cls: Type[Sealed], dt: datetime) -> Sealed:
        # pylint: disable=invalid-name
        return cls.combine(dt.date(), dt.time(), tzinfo=dt.tzinfo)

    @classmethod
    def from_date_parts(cls: Type[Sealed], year: int, month: int, day: int) -> Sealed:
        # because SealedDate is actually a datetime object, we must create it with a
        # timezone such that its date remains stable no matter the values of USE_TZ,
        # current_timezone and default_timezone.
        return cls.from_datetime(datetime(year, month, day, tzinfo=_westmost_tz))


class MonthSeal(SealedDate):
    @property
    def has_day(self) -> bool:
        return False

    def partial_isoformat(self) -> str:
        return self.strftime("%Y-%m")


class YearSeal(SealedDate):
    @property
    def has_month(self) -> bool:
        return False

    def partial_isoformat(self) -> str:
        return self.strftime("%Y")


def from_partial_isoformat(value: str) -> SealedDate:
    match = _partial_re.match(value)

    if not match:
        raise ValueError

    year, month, day = [val and int(val) for val in match.groups()]

    if month is None:
        return YearSeal.from_date_parts(year, 1, 1)
    elif day is None:
        return MonthSeal.from_date_parts(year, month, 1)
    else:
        return SealedDate.from_date_parts(year, month, day)


class SealedDateFormField(DateField):
    """date form field with support for SealedDate"""

    def prepare_value(self, value: Any) -> str:
        # As a convention, Django's `SelectDateWidget` uses "0" for missing
        # parts. We piggy-back into that, to make it work with SealedDate.
        if not isinstance(value, SealedDate):
            return cast(str, super().prepare_value(value))
        elif value.has_day:
            return value.strftime("%Y-%m-%d")
        elif value.has_month:
            return value.strftime("%Y-%m-0")
        else:
            return value.strftime("%Y-0-0")

    def to_python(self, value: Any) -> Optional[SealedDate]:
        try:
            date = super().to_python(value)
        except ValidationError as ex:
            if match := SelectDateWidget.date_re.match(value):
                year, month, day = map(int, match.groups())
            if not match or (day and not month) or not year:
                raise ex from None
            if not month:
                return YearSeal.from_date_parts(year, 1, 1)
            elif not day:
                return MonthSeal.from_date_parts(year, month, 1)
        else:
            if date is None:
                return None
            else:
                year, month, day = date.year, date.month, date.day

        return SealedDate.from_date_parts(year, month, day)
