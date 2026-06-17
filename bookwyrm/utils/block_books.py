"""
Function for filtering out blocked books on any relevant queryset
For statuses instead use self.blocked_book_filter(viewer)
"""

from django.core.exceptions import FieldError
from django.db.models.query import QuerySet
from bookwyrm import models


def blocked_book_filter(
    queryset: QuerySet[models.Edition] | QuerySet[models.Work],
    model: str,
    viewer: models.User,
) -> QuerySet[models.Edition] | QuerySet[models.Work]:
    """filter out blocked books from querysets"""

    if not viewer or not viewer.is_authenticated:
        return queryset

    blocked = viewer.blocked_books.all().values_list("id", flat=True)

    if model == "Work":
        try:
            return queryset.exclude(work__in=blocked)
        except FieldError:
            return queryset.exclude(book__in=blocked)

    if model == "Edition":
        try:
            return queryset.exclude(edition__parent_work__in=blocked)
        except FieldError:
            return queryset.exclude(book__parent_work__in=blocked)

    return queryset
