""" we have the goodreads ratings......... """
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from bookwyrm import models


def get_ratings():
    """find and set ratings based on goodreads import lines"""
    import_items = models.ImportItem.objects.filter(book__isnull=False).all()
    user = models.User.objects.get(localname="goodreads-average-ratings")
    for item in import_items:
        rating = item.data.get("Average Rating")
        if (
            not rating
            or models.ReviewRating.objects.filter(user=user, book=item.book).exists()
        ):
            continue
        models.ReviewRating.objects.create(
            user=user,
            rating=float(rating),
            book=item.book.edition,
            published_date=timezone.make_aware(datetime(2000, 1, 1)),  # long ago
            privacy="followers",
        )


class Command(BaseCommand):
    """dedplucate allllll the book data models"""

    help = "merges duplicate book data"
    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """run deudplications"""
        get_ratings()
