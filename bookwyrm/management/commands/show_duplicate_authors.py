from django.core.management.base import BaseCommand
from django.db.models import Count
from bookwyrm import models


def find_duplicate_author_names():
    """Show authors that have same name"""
    dupes = (
        models.Author.objects.values("name")
        .annotate(Count("name"))
        .filter(name__count__gt=1)
        .exclude(name="")
        .exclude(name__isnull=True)
        .order_by("name__count")
    )

    for dupe in dupes:
        value = dupe["name"]
        print("----------")
        objs = (
            models.Author.objects.filter(name=value)
            .annotate(num_books=Count("book", distinct=True))
            .order_by("-num_books", "id")
        )
        print(
            "You could check if the following authors are actually the same and can be merged, (only checked based on name)"
        )
        for obj in objs:
            born = obj.born.year if obj.born else ""
            died = obj.died.year if obj.died else ""
            years = ""
            if born or died:
                years = f" ({born}-{died})"
            print(
                f"- {obj.remote_id}, {obj.name}{years} book editions found:{obj.num_books}"
            )


class Command(BaseCommand):
    """Show all the authors that appear with same name, but different id"""

    help = "show authors with same name but different id"

    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """run deduplications"""
        find_duplicate_author_names()
        print("----------")
        print(
            "You should manually check each author id to determine if they are same author before thinking of merging"
        )
