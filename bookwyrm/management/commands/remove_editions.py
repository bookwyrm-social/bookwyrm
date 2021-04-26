""" PROCEED WITH CAUTION: this permanently deletes book data """
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from bookwyrm import models


def remove_editions():
    """combine duplicate editions and update related models"""
    # not in use
    filters = {
        "%s__isnull" % r.name: True for r in models.Edition._meta.related_objects
    }
    # no cover, no identifying fields
    filters["cover"] = ""
    null_fields = {
        "%s__isnull" % f: True for f in ["isbn_10", "isbn_13", "oclc_number"]
    }

    editions = (
        models.Edition.objects.filter(
            Q(languages=[]) | Q(languages__contains=["English"]),
            **filters,
            **null_fields
        )
        .annotate(Count("parent_work__editions"))
        .filter(
            # mustn't be the only edition for the work
            parent_work__editions__count__gt=1
        )
    )
    print(editions.count())
    editions.delete()


class Command(BaseCommand):
    """dedplucate allllll the book data models"""

    help = "merges duplicate book data"
    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """run deudplications"""
        remove_editions()
