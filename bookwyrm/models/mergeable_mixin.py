"""models that can be deduplicated and merged"""

from datetime import timedelta
from functools import reduce
import operator

from typing import Any, Dict
from typing_extensions import Self

from django.db import transaction
from django.db.models import Count, ManyToManyField, Q
from django.utils import timezone

from . import fields


class MergeableMixin:
    """A bookwyrm data object that can be deduplicated"""

    @classmethod
    def deduplication_fields(cls):
        """list all the deduplication fields for a model"""
        model_fields = cls._meta.get_fields()
        return [
            f
            for f in model_fields
            if hasattr(f, "deduplication_field") and f.deduplication_field
        ]

    @classmethod
    def find_duplicate_fields(cls):
        """scan the model for all dedupe fields with multiple objs with the same value"""
        dedupe_fields = cls.deduplication_fields()
        duplicates = {}
        for field in dedupe_fields:
            results = (
                cls.objects.filter(pending_merge_target__isnull=True)
                .values(field.name)
                .annotate(Count(field.name))
                .filter(**{f"{field.name}__count__gt": 1})
                .exclude(**{field.name: ""})
                .exclude(**{f"{field.name}__isnull": True})
                .values_list(field.name, flat=True)
            )
            if results.exists():
                duplicates[field.name] = results
        return duplicates

    @classmethod
    def mark_merge_candidates(cls):
        """update duplicate entries with pending merge reference"""
        dedupe_fields = cls.find_duplicate_fields()
        week_from_today = timezone.now() + timedelta(days=7)
        for field_name, values in dedupe_fields.items():
            for value in values:
                objs = cls.objects.filter(**{field_name: value}).order_by("id")
                if not objs.exists() or objs.count() <= 1:
                    continue
                canonical = objs.first()
                candidates = objs.exclude(id=canonical.id)
                candidates.update(
                    pending_merge_target=canonical, pending_merge_date=week_from_today
                )

    def find_merge_candidate(self):
        """look for the first possible duplicate of the current object"""
        model = self.__class__
        # filter based on the dedupe fields on this obj that are set
        dedupe_fields = model.deduplication_fields()
        filters = [
            {f.name: getattr(self, f.name)}
            for f in dedupe_fields
            if getattr(self, f.name) and getattr(self, f.name) != ""
        ]
        # look up objects that aren't the current object but match any dedupe field
        dupe = model.objects.exclude(id=self.id).filter(
            reduce(operator.or_, (Q(**f) for f in filters))
        )
        return dupe.first()

    @transaction.atomic
    def merge_into(self, canonical: Self, dry_run=False) -> Dict[str, Any]:
        """merge this entity into another entity"""
        if canonical.id == self.id:
            raise ValueError(f"Cannot merge {self} into itself")

        absorbed_fields = canonical.absorb_data_from(self, dry_run=dry_run)

        if dry_run:
            return absorbed_fields

        canonical.save()

        self.merged_model.objects.create(deleted_id=self.id, merged_into=canonical)

        # move related models to canonical
        related_models = [
            (r.remote_field.name, r.related_model) for r in self._meta.related_objects
        ]
        for related_field, related_model in related_models:
            # Skip the ManyToMany fields that aren’t auto-created. These
            # should have a corresponding OneToMany field in the model for
            # the linking table anyway. If we update it through that model
            # instead then we won’t lose the extra fields in the linking
            # table.

            related_field_obj = related_model._meta.get_field(related_field)
            if isinstance(related_field_obj, ManyToManyField):
                through = related_field_obj.remote_field.through
                if not through._meta.auto_created:
                    continue
            related_objs = related_model.objects.filter(**{related_field: self})
            for related_obj in related_objs:
                try:
                    setattr(related_obj, related_field, canonical)
                    related_obj.save()
                except TypeError:
                    getattr(related_obj, related_field).add(canonical)
                    getattr(related_obj, related_field).remove(self)

        self.delete()
        return absorbed_fields

    def absorb_data_from(self, other: Self, dry_run=False) -> Dict[str, Any]:
        """fill empty fields with values from another entity"""
        absorbed_fields = {}
        for data_field in self._meta.get_fields():
            if not hasattr(data_field, "activitypub_field"):
                continue
            canonical_value = getattr(self, data_field.name)
            other_value = getattr(other, data_field.name)
            if not other_value:
                continue
            if isinstance(data_field, fields.ArrayField):
                if new_values := list(set(other_value) - set(canonical_value)):
                    # append at the end (in no particular order)
                    if not dry_run:
                        setattr(self, data_field.name, canonical_value + new_values)
                    absorbed_fields[data_field.name] = new_values
            elif isinstance(data_field, fields.PartialDateField):
                if (
                    (not canonical_value)
                    or (other_value.has_day and not canonical_value.has_day)
                    or (other_value.has_month and not canonical_value.has_month)
                ):
                    if not dry_run:
                        setattr(self, data_field.name, other_value)
                    absorbed_fields[data_field.name] = other_value
            else:
                if not canonical_value:
                    if not dry_run:
                        setattr(self, data_field.name, other_value)
                    absorbed_fields[data_field.name] = other_value
        return absorbed_fields
