""" PROCEED WITH CAUTION: uses deduplication fields to permanently
merge book data objects """
from django.core.management.base import BaseCommand
from django.db.models import Count
from bookwyrm import models


def update_related(canonical, obj):
    """update all the models with fk to the object being removed"""
    # move related models to canonical
    related_models = [
        (r.remote_field.name, r.related_model) for r in canonical._meta.related_objects
    ]
    for (related_field, related_model) in related_models:
        related_objs = related_model.objects.filter(**{related_field: obj})
        for related_obj in related_objs:
            print("replacing in", related_model.__name__, related_field, related_obj.id)
            try:
                setattr(related_obj, related_field, canonical)
                related_obj.save()
            except TypeError:
                getattr(related_obj, related_field).add(canonical)
                getattr(related_obj, related_field).remove(obj)


def copy_data(canonical, obj):
    """try to get the most data possible"""
    for data_field in obj._meta.get_fields():
        if not hasattr(data_field, "activitypub_field"):
            continue
        data_value = getattr(obj, data_field.name)
        if not data_value:
            continue
        if not getattr(canonical, data_field.name):
            print("setting data field", data_field.name, data_value)
            setattr(canonical, data_field.name, data_value)
    canonical.save()


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
            .filter(**{"%s__count__gt" % field.name: 1})
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
                copy_data(canonical, obj)
                update_related(canonical, obj)
                # remove the outdated entry
                obj.delete()


class Command(BaseCommand):
    """dedplucate allllll the book data models"""

    help = "merges duplicate book data"
    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """run deudplications"""
        dedupe_model(models.Edition)
        dedupe_model(models.Work)
        dedupe_model(models.Author)
