"""Implementation of the SealedDate class."""

from datetime import datetime


class SealedDate(datetime):  # TODO: migrate from DateTimeField to DateField
    @property
    def has_day(self) -> bool:
        return self.has_month

    @property
    def has_month(self) -> bool:
        return True

    def __str__(self):
        return self.strftime("%Y-%m-%d")

    @classmethod
    def from_datetime(cls, dt):
        # pylint: disable=invalid-name
        return cls.combine(dt.date(), dt.time(), tzinfo=dt.tzinfo)


class MonthSeal(SealedDate):
    @property
    def has_day(self) -> bool:
        return False

    def __str__(self):
        return self.strftime("%Y-%m")


class YearSeal(SealedDate):
    @property
    def has_month(self) -> bool:
        return False

    def __str__(self):
        return self.strftime("%Y")
