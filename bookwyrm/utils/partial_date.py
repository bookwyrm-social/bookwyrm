"""Implementation of the PartialDate class."""

from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any, Optional, Type, cast
from typing_extensions import Self

from django.core.exceptions import ValidationError
from django.db import models
from django.forms import DateField
from django.forms.widgets import SelectDateWidget
from django.utils import timezone

# pylint: disable=no-else-return

__all__ = [
    "PartialDate",
    "PartialDateModel",
    "from_partial_isoformat",
]

_partial_re = re.compile(r"(\d{4})(?:-(\d\d?))?(?:-(\d\d?))?$")
_westmost_tz = timezone.get_fixed_timezone(timedelta(hours=-12))

# TODO: migrate PartialDate: `datetime` => `date`
# TODO: migrate PartialDateModel: `DateTimeField` => `DateField`


class PartialDate(datetime):
    """a date object bound into a certain precision (day, month or year)"""

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
    def from_datetime(cls, dt: datetime) -> Self:
        """construct a PartialDate object from a timezone-aware datetime

        Use subclasses to specify precision. If `dt` is naive, `ValueError`
        is raised.
        """
        if timezone.is_naive(dt):
            raise ValueError("naive datetime not accepted")
        return cls.combine(dt.date(), dt.time(), tzinfo=dt.tzinfo)

    @classmethod
    def from_date_parts(cls, year: int, month: int, day: int) -> Self:
        """construct a PartialDate from year, month, day.

        Use sublcasses to specify precision."""
        # because PartialDate is actually a datetime object, we must create it with a
        # timezone such that its date remains stable no matter the values of USE_TZ,
        # current_timezone and default_timezone.
        return cls.from_datetime(datetime(year, month, day, tzinfo=_westmost_tz))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PartialDate):
            return NotImplemented
        return self.partial_isoformat() == other.partial_isoformat()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} object: {self.partial_isoformat()}>"


class MonthParts(PartialDate):
    """a date bound into month precision"""

    @property
    def has_day(self) -> bool:
        return False

    def partial_isoformat(self) -> str:
        return self.strftime("%Y-%m")


class YearParts(PartialDate):
    """a date bound into year precision"""

    @property
    def has_month(self) -> bool:
        return False

    def partial_isoformat(self) -> str:
        return self.strftime("%Y")


def from_partial_isoformat(value: str) -> PartialDate:
    """construct PartialDate from a partial string.

    Accepted formats: YYYY, YYYY-MM, YYYY-MM-DD; otherwise `ValueError`
    is raised.
    """
    match = _partial_re.match(value)

    if not match:
        raise ValueError

    year, month, day = [int(val) if val else -1 for val in match.groups()]

    if month < 0:
        return YearParts.from_date_parts(year, 1, 1)
    elif day < 0:
        return MonthParts.from_date_parts(year, month, 1)
    else:
        return PartialDate.from_date_parts(year, month, day)


class PartialDateFormField(DateField):
    """date form field with support for PartialDate"""

    def prepare_value(self, value: Any) -> str:
        # As a convention, Django's `SelectDateWidget` uses "0" for missing
        # parts. We piggy-back into that, to make it work with PartialDate.
        if not isinstance(value, PartialDate):
            return cast(str, super().prepare_value(value))
        elif value.has_day:
            return value.strftime("%Y-%m-%d")
        elif value.has_month:
            return value.strftime("%Y-%m-0")
        else:
            return value.strftime("%Y-0-0")

    def to_python(self, value: Any) -> Optional[PartialDate]:
        try:
            date = super().to_python(value)
        except ValidationError as ex:
            if match := SelectDateWidget.date_re.match(value):
                year, month, day = map(int, match.groups())
            if not match or (day and not month) or not year:
                raise ex from None
            if not month:
                return YearParts.from_date_parts(year, 1, 1)
            elif not day:
                return MonthParts.from_date_parts(year, month, 1)
        else:
            if date is None:
                return None
            else:
                year, month, day = date.year, date.month, date.day

        return PartialDate.from_date_parts(year, month, day)


# For typing field and descriptor, below.
_SetType = datetime
_GetType = Optional[PartialDate]


class PartialDateDescriptor:
    """descriptor for PartialDateModel.

    Encapsulates the "two columns, one field" for PartialDateModel.
    """

    _PRECISION_NAMES: dict[Type[_SetType], str] = {
        YearParts: "YEAR",
        MonthParts: "MONTH",
        PartialDate: "DAY",
    }

    _PARTIAL_CLASSES: dict[Any, Type[PartialDate]] = {
        "YEAR": YearParts,
        "MONTH": MonthParts,
    }

    def __init__(self, field: models.Field[_SetType, _GetType]):
        self.field = field

    def __get__(self, instance: models.Model, cls: Any = None) -> _GetType:
        if instance is None:
            return self

        value = instance.__dict__.get(self.field.attname)

        if not value or isinstance(value, PartialDate):
            return value

        # use precision field to construct PartialDate.
        precision = getattr(instance, self.precision_field, None)
        date_class = self._PARTIAL_CLASSES.get(precision, PartialDate)

        return date_class.from_datetime(value)  # FIXME: drop datetimes.

    def __set__(self, instance: models.Model, value: _SetType) -> None:
        """assign value, with precision where available"""
        try:
            precision = self._PRECISION_NAMES[value.__class__]
        except KeyError:
            value = self.field.to_python(value)
        else:
            setattr(instance, self.precision_field, precision)

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
        return [("DAY", "Day prec."), ("MONTH", "Month prec."), ("YEAR", "Year prec.")]


class PartialDateModel(models.DateTimeField):  # type: ignore[type-arg]
    """a date field for Django models, using PartialDate as values"""

    descriptor_class = PartialDateDescriptor

    def formfield(self, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.setdefault("form_class", PartialDateFormField)
        return super().formfield(**kwargs)

    # pylint: disable-next=arguments-renamed,line-too-long
    def contribute_to_class(self, model, our_name_in_model, **kwargs):  # type: ignore[no-untyped-def]
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
