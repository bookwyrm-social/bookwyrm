""" template filters """
from django import template
from django.db.models import Avg, StdDev, Count, F, Q

from bookwyrm import models

register = template.Library()


@register.simple_tag(takes_context=False)
def get_book_superlatives():
    """get book stats for the about page"""
    total_ratings = models.Review.objects.filter(local=True, deleted=False).count()
    data = {}
    data["top_rated"] = (
        models.Work.objects.annotate(
            rating=Avg(
                "editions__review__rating",
                filter=Q(
                    editions__review__user__local=True, editions__review__deleted=False
                ),
            ),
            rating_count=Count(
                "editions__review",
                filter=Q(
                    editions__review__user__local=True, editions__review__deleted=False
                ),
            ),
        )
        .annotate(weighted=F("rating") * F("rating_count") / total_ratings)
        .filter(rating__gt=4, weighted__gt=0)
        .order_by("-weighted")
        .first()
    )

    data["controversial"] = (
        models.Work.objects.annotate(
            deviation=StdDev(
                "editions__review__rating",
                filter=Q(
                    editions__review__user__local=True, editions__review__deleted=False
                ),
            ),
            rating_count=Count(
                "editions__review",
                filter=Q(
                    editions__review__user__local=True, editions__review__deleted=False
                ),
            ),
        )
        .annotate(weighted=F("deviation") * F("rating_count") / total_ratings)
        .filter(weighted__gt=0)
        .order_by("-weighted")
        .first()
    )

    data["wanted"] = (
        models.Work.objects.annotate(
            shelf_count=Count(
                "editions__shelves", filter=Q(editions__shelves__identifier="to-read")
            )
        )
        .order_by("-shelf_count")
        .first()
    )
    return data


@register.simple_tag(takes_context=False)
def get_landing_books():
    """list of books for the landing page"""
    return list(
        set(
            models.Edition.objects.filter(
                review__published_date__isnull=False,
                review__deleted=False,
                review__user__local=True,
                review__privacy__in=["public", "unlisted"],
            )
            .exclude(cover__exact="")
            .distinct()
            .order_by("-review__published_date")[:6]
        )
    )
