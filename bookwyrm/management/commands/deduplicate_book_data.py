""" PROCEED WITH CAUTION: uses deduplication fields to permanently
merge book data objects """

from django.core.management.base import BaseCommand
from django.db.models import Count
from bookwyrm import models


def dedupe_model(model):
    """combine duplicate editions and update related models"""
    fields = model._meta.get_fields()
    dedupe_fields = [
        f for f in fields if hasattr(f, "deduplication_field") and f.deduplication_field
    ]
    for field in dedupe_fields:
        dupes = (
            model.objects.values(field.name)
            .annotate(Count(field.name))
            .filter(merged_into__isnull=True, **{"%s__count__gt" % field.name: 1})
            .exclude(**{field.name: "", "%s__isnull" % field.name: True})
        )

        for dupe in dupes:
            value = dupe[field.name]
            if not value or value == "":
                continue
            print("----------")
            print(dupe)
            objs = model.objects.filter(**{field.name: value}).order_by("id")
            canonical = objs.first()
            print("keeping", canonical.remote_id)
            for obj in objs[1:]:
                print(obj.remote_id)
                obj.merge_into(canonical)


class Command(BaseCommand):
    """deduplicate allllll the book data models"""

    help = "merges duplicate book data"

    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """run deduplications"""
        dedupe_model(models.Edition)
        dedupe_model(models.Work)
        dedupe_model(models.Author)
