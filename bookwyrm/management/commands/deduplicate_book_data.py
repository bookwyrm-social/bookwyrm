"""PROCEED WITH CAUTION: uses deduplication fields to permanently
merge book data objects"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from bookwyrm import models


def dedupe_model(model, dry_run=False):
    """combine duplicate editions and update related models"""
    print(f"deduplicating {model.__name__}:")
    fields = model._meta.get_fields()
    dedupe_fields = [
        f for f in fields if hasattr(f, "deduplication_field") and f.deduplication_field
    ]
    for field in dedupe_fields:
        dupes = (
            model.objects.values(field.name)
            .annotate(Count(field.name))
            .filter(**{f"{field.name}__count__gt": 1})
            .exclude(**{field.name: ""})
            .exclude(**{f"{field.name}__isnull": True})
        )

        for dupe in dupes:
            value = dupe[field.name]
            print("----------")
            objs = model.objects.filter(**{field.name: value}).order_by("id")
            canonical = objs.first()
            action = "would merge" if dry_run else "merging"
            print(
                f"{action} into {model.__name__} {canonical.remote_id} based on {field.name} {value}:"
            )
            for obj in objs[1:]:
                print(f"- {obj.remote_id}")
                absorbed_fields = obj.merge_into(canonical, dry_run=dry_run)
                print(f"  absorbed fields: {absorbed_fields}")


class Command(BaseCommand):
    """deduplicate allllll the book data models"""

    help = "merges duplicate book data"

    def add_arguments(self, parser):
        """add the arguments for this command"""
        parser.add_argument(
            "--dry_run",
            action="store_true",
            help="don't actually merge, only print what would happen",
        )

    def handle(self, *args, **options):
        """run deduplications"""
        dedupe_model(models.Edition, dry_run=options["dry_run"])
        dedupe_model(models.Work, dry_run=options["dry_run"])
        dedupe_model(models.Author, dry_run=options["dry_run"])
