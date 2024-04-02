from django.db.models import ManyToManyField


def update_related(canonical, obj):
    """update all the models with fk to the object being removed"""
    # move related models to canonical
    related_models = [
        (r.remote_field.name, r.related_model) for r in canonical._meta.related_objects
    ]
    for (related_field, related_model) in related_models:
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


def merge_objects(canonical, obj):
    copy_data(canonical, obj)
    update_related(canonical, obj)
    # remove the outdated entry
    obj.delete()
