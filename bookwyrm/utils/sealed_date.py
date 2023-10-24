"""Implementation of the SealedDate class."""

from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any, Optional, Type, TypeVar, cast

from django.core.exceptions import ValidationError
from django.db import models
from django.forms import DateField
from django.forms.widgets import SelectDateWidget
from django.utils import timezone

# pylint: disable=no-else-return

__all__ = [
    "SealedDate",
    "from_partial_isoformat",
]

_partial_re = re.compile(r"(\d{4})(?:-(\d\d?))?(?:-(\d\d?))?$")
_westmost_tz = timezone.get_fixed_timezone(timedelta(hours=-12))

Sealed = TypeVar("Sealed", bound="SealedDate")  # TODO: use Self in Python >= 3.11

# TODO: migrate SealedDate: `datetime` => `date`
# TODO: migrate SealedDateField: `DateTimeField` => `DateField`


class SealedDate(datetime):
    """a date object sealed into a certain precision (day, month or year)"""

    @property
    def has_day(self) -> bool:
        """whether this is a full date"""
        return self.has_month

    @property
    def has_month(self) -> bool:
        """whether this date includes month"""
        return True

    def partial_isoformat(self) -> str:
        """partial ISO-8601 format"""
        return self.strftime("%Y-%m-%d")

    @classmethod
    def from_datetime(cls: Type[Sealed], dt: datetime) -> Sealed:
        """construct a SealedDate object from a timezone-aware datetime

        Use subclasses to specify precision. If `dt` is naive, `ValueError`
        is raised.
        """
        # pylint: disable=invalid-name
        if timezone.is_naive(dt):
            raise ValueError("naive datetime not accepted")
        return cls.combine(dt.date(), dt.time(), tzinfo=dt.tzinfo)

    @classmethod
    def from_date_parts(cls: Type[Sealed], year: int, month: int, day: int) -> Sealed:
        """construct a SealedDate from year, month, day.

        Use sublcasses to specify precision."""
        # because SealedDate is actually a datetime object, we must create it with a
        # timezone such that its date remains stable no matter the values of USE_TZ,
        # current_timezone and default_timezone.
        return cls.from_datetime(datetime(year, month, day, tzinfo=_westmost_tz))


class MonthSeal(SealedDate):
    """a date sealed into month precision"""

    @property
    def has_day(self) -> bool:
        return False

    def partial_isoformat(self) -> str:
        return self.strftime("%Y-%m")


class YearSeal(SealedDate):
    """a date sealed into year precision"""

    @property
    def has_month(self) -> bool:
        return False

    def partial_isoformat(self) -> str:
        return self.strftime("%Y")


def from_partial_isoformat(value: str) -> SealedDate:
    """construct SealedDate from a partial string.

    Accepted formats: YYYY, YYYY-MM, YYYY-MM-DD; otherwise `ValueError`
    is raised.
    """
    match = _partial_re.match(value)

    if not match:
        raise ValueError

    year, month, day = [int(val) if val else -1 for val in match.groups()]

    if month < 0:
        return YearSeal.from_date_parts(year, 1, 1)
    elif day < 0:
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


# For typing field and descriptor, below.
_SetType = datetime
_GetType = Optional[SealedDate]


class SealedDateDescriptor:
    """descriptor for SealedDateField.

    Encapsulates the "two columns, one field" for SealedDateField.
    """

    _SEAL_TYPES: dict[Type[_SetType], str] = {
        YearSeal: "YEAR",
        MonthSeal: "MONTH",
        SealedDate: "DAY",
    }

    _DATE_CLASSES: dict[Any, Type[SealedDate]] = {
        "YEAR": YearSeal,
        "MONTH": MonthSeal,
    }

    def __init__(self, field: models.Field[_SetType, _GetType]):
        self.field = field

    def __get__(self, instance: models.Model, cls: Any = None) -> _GetType:
        if instance is None:
            return self

        value = instance.__dict__.get(self.field.attname)

        if not value or isinstance(value, SealedDate):
            return value

        # use precision field to construct SealedDate.
        seal_type = getattr(instance, self.precision_field, None)
        date_class = self._DATE_CLASSES.get(seal_type, SealedDate)

        return date_class.from_datetime(value)  # FIXME: drop datetimes.

    def __set__(self, instance: models.Model, value: _SetType) -> None:
        """assign value, with precision where available"""
        try:
            seal_type = self._SEAL_TYPES[value.__class__]
        except KeyError:
            value = self.field.to_python(value)
        else:
            setattr(instance, self.precision_field, seal_type)

        instance.__dict__[self.field.attname] = value

    @classmethod
    def make_precision_name(cls, date_attr_name: str) -> str:
        """derive the precision field name from main attr name"""
        return f"{date_attr_name}_precision"

    @property
    def precision_field(self) -> str:
        """the name of the accompanying precision field"""
        return self.make_precision_name(self.field.attname)

    @property
    def precision_choices(self) -> list[tuple[str, str]]:
        """valid options for precision database field"""
        return [("DAY", "Day seal"), ("MONTH", "Month seal"), ("YEAR", "Year seal")]


class SealedDateField(models.DateTimeField):  # type: ignore
    """a date field for Django models, using SealedDate as values"""

    descriptor_class = SealedDateDescriptor

    def formfield(self, **kwargs):  # type: ignore
        kwargs.setdefault("form_class", SealedDateFormField)
        return super().formfield(**kwargs)

    # pylint: disable-next=arguments-renamed
    def contribute_to_class(self, model, our_name_in_model, **kwargs):  # type: ignore
        # Define precision field.
        descriptor = self.descriptor_class(self)
        precision: models.Field[Optional[str], Optional[str]] = models.CharField(
            null=True,
            blank=True,
            editable=False,
            max_length=10,
            choices=descriptor.precision_choices,
        )
        precision_name = descriptor.make_precision_name(our_name_in_model)

        model.add_to_class(precision_name, precision)
        return super().contribute_to_class(model, our_name_in_model, **kwargs)
