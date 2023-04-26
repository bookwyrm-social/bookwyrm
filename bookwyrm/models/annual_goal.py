""" How many books do you want to read this year """
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from bookwyrm.models.status import Review
from .base_model import BookWyrmModel
from . import fields, Review


def get_current_year():
    """sets default year for annual goal to this year"""
    return timezone.now().year


class AnnualGoal(BookWyrmModel):
    """set a goal for how many books you read in a year"""

    user = models.ForeignKey("User", on_delete=models.PROTECT)
    goal = models.IntegerField(validators=[MinValueValidator(1)])
    year = models.IntegerField(default=get_current_year)
    privacy = models.CharField(
        max_length=255, default="public", choices=fields.PrivacyLevels
    )

    class Meta:
        """uniqueness constraint"""

        unique_together = ("user", "year")

    def get_remote_id(self):
        """put the year in the path"""
        return f"{self.user.remote_id}/goal/{self.year}"

    @property
    def books(self):
        """the books you've read this year"""
        return (
            self.user.readthrough_set.filter(
                finish_date__year__gte=self.year,
                finish_date__year__lt=self.year + 1,
            )
            .order_by("-finish_date")
            .all()
        )

    @property
    def ratings(self):
        """ratings for books read this year"""
        book_ids = [r.book.id for r in self.books]
        reviews = Review.objects.filter(
            user=self.user,
            book__in=book_ids,
        )
        return {r.book_id: r.rating for r in reviews}

    @property
    def progress(self):
        """how many books you've read this year"""
        count = self.user.readthrough_set.filter(
            finish_date__year__gte=self.year,
            finish_date__year__lt=self.year + 1,
        ).count()
        return {
            "count": count,
            "percent": int(float(count / self.goal) * 100),
        }
