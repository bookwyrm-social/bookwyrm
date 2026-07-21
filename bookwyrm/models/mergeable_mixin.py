"""models that can be deduplicated and merged"""

from datetime import timedelta

from typing import Any, Dict, Optional, Iterable
from typing_extensions import Self

from django.apps import apps
from django.db import transaction
from django.db.models import BooleanField, Count, DateTimeField, ManyToManyField, Model
from django.utils import timezone

from bookwyrm.utils.db import add_update_fields
from . import fields


class MergeableMixin(Model):
    """A bookwyrm data object that can be deduplicated"""

    pending_merge_date = DateTimeField(null=True)
    prevent_automatic_merge = BooleanField(default=False)

    class Meta:
        """can't initialize this model, that wouldn't make sense"""

        abstract = True

    def save(
        self, *args: Any, update_fields: Optional[Iterable[str]] = None, **kwargs: Any
    ) -> None:
        """Check for duplicates that may be invalidated"""
        # do this check for objects that are being edited, not created
        if self.id:
            # check if the current target still matches the dedupe fields
            if self.pending_merge_target and not self.get_shared_fields(
                self.pending_merge_target
            ):
                self.pending_merge_target = None
                self.pending_merge_date = None
                self.prevent_automatic_merge = False
                update_fields = add_update_fields(
                    update_fields,
                    "pending_merge_target",
                    "prevent_automatic_merge",
                    "pending_merge_date",
                )

            # also check if this is the canonical for other editions
            for target in self.merge_target.all():
                if not self.get_shared_fields(target):
                    target.pending_merge_target = None
                    target.pending_merge_date = None
                    target.prevent_automatic_merge = False
                    target.save(
                        broadcast=False,
                        update_fields=[
                            "pending_merge_target",
                            "prevent_automatic_merge",
                            "pending_merge_date",
                        ],
                    )

        super().save(*args, update_fields=update_fields, **kwargs)

    def get_shared_fields(self, candidate):
        """list the fields that two items have in common"""
        if type(self) is not type(candidate) or (
            self.pending_merge_target != candidate
            and candidate.pending_merge_target != self
        ):
            raise ValueError("Invalid deduplication comparison for:", self, candidate)

        shared_fields = []
        for field in self.deduplication_fields():
            origin_value = getattr(self, field.name)
            candidate_value = getattr(candidate, field.name)
            if origin_value and origin_value == candidate_value:
                shared_fields.append(field)
        return shared_fields

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
                .exclude(
                    **{field.name: None if isinstance(field, fields.ForeignKey) else ""}
                )
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

    @property
    def merge_candidates(self):
        """aggregate duplicates of this item"""
        model = self.__class__
        return model.objects.filter(pending_merge_target=self.id)

    @transaction.atomic
    def merge_into(
        self, canonical: Self, dry_run=False, manual=False
    ) -> Dict[str, Any]:
        """merge this entity into another entity"""
        if canonical.id == self.id:
            raise ValueError(f"Cannot merge {self} into itself")

        absorbed_fields = (
            canonical.absorb_data_from(self, dry_run=dry_run) if not manual else []
        )

        if dry_run:
            return absorbed_fields

        canonical.save()

        # generally we create a merged model, but not for suggestion lists
        if hasattr(self, "merged_model"):
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

        # TODO: decide what to do about authors and series

        edition_model = apps.get_model("bookwyrm.Edition")
        work_model = apps.get_model("bookwyrm.Work")
        suggests_model = apps.get_model("bookwyrm.SuggestionList")

        if self.__class__ == edition_model:
            parent = work_model.objects.get(editions__contains=self.id)
            self.delete()
            # if self.parent is now without any child editions, merge it too
            # unless it is already marked as a merge candidate
            if not parent.editions and not parent.pending_merge_target:
                parent.merge_into(canonical.parent_work)

        elif self.__class__ == work_model:
            self.delete()
            # if self has a suggestion list it needs to either be meged with the canonical
            # suggestion list, or simply transferred if canonical has no suggestion list
            if lists := suggests_model.objects.filter(
                suggests_for__in=[self.id, canonical.id]
            ):
                if lists.count() > 1:
                    work_model.objects.get(id=self.id).merge_into(
                        work_model.objects.get(id=canonical.id)
                    )
                if lists.count() == 1 and lists.first().suggests_for == self:
                    lists.first().suggests_for = canonical
                    lists.first().save()

        else:
            self.delete()

        # TODO
        # suggestionlists have suggestions, suggestions have (endorsement, notes, raw_notes)
        # I suggest (sorry) we leave SuggestionList model as-is but in the _view_ allow for multiple
        # SuggestionListItems and display together in one card

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
