""" basics for an activitypub serializer """
from dataclasses import dataclass, fields, MISSING
from json import JSONEncoder

from django.apps import apps
from django.db import IntegrityError, transaction

from bookwyrm.connectors import ConnectorException, get_data
from bookwyrm.tasks import app


class ActivitySerializerError(ValueError):
    """routine problems serializing activitypub json"""


class ActivityEncoder(JSONEncoder):
    """used to convert an Activity object into json"""

    def default(self, o):
        return o.__dict__


@dataclass
# pylint: disable=invalid-name
class Signature:
    """public key block"""

    creator: str
    created: str
    signatureValue: str
    type: str = "RsaSignature2017"


def naive_parse(activity_objects, activity_json, serializer=None):
    """this navigates circular import issues by looking up models' serializers"""
    if not serializer:
        if activity_json.get("publicKeyPem"):
            # ugh
            activity_json["type"] = "PublicKey"

        activity_type = activity_json.get("type")
        try:
            serializer = activity_objects[activity_type]
        except KeyError as err:
            # we know this exists and that we can't handle it
            if activity_type in ["Question"]:
                return None
            raise ActivitySerializerError(err)

    return serializer(activity_objects=activity_objects, **activity_json)


@dataclass(init=False)
class ActivityObject:
    """actor activitypub json"""

    id: str
    type: str

    def __init__(self, activity_objects=None, **kwargs):
        """this lets you pass in an object with fields that aren't in the
        dataclass, which it ignores. Any field in the dataclass is required or
        has a default value"""
        for field in fields(self):
            try:
                value = kwargs[field.name]
                if value in (None, MISSING, {}):
                    raise KeyError()
                try:
                    is_subclass = issubclass(field.type, ActivityObject)
                except TypeError:
                    is_subclass = False
                # serialize a model obj
                if hasattr(value, "to_activity"):
                    value = value.to_activity()
                # parse a dict into the appropriate activity
                elif is_subclass and isinstance(value, dict):
                    if activity_objects:
                        value = naive_parse(activity_objects, value)
                    else:
                        value = naive_parse(
                            activity_objects, value, serializer=field.type
                        )

            except KeyError:
                if field.default == MISSING and field.default_factory == MISSING:
                    raise ActivitySerializerError(
                        f"Missing required field: {field.name}"
                    )
                value = field.default
            setattr(self, field.name, value)

    # pylint: disable=too-many-locals,too-many-branches,too-many-arguments
    def to_model(
        self, model=None, instance=None, allow_create=True, save=True, overwrite=True
    ):
        """convert from an activity to a model instance"""
        model = model or get_model_from_type(self.type)

        # only reject statuses if we're potentially creating them
        if (
            allow_create
            and hasattr(model, "ignore_activity")
            and model.ignore_activity(self)
        ):
            return None

        # check for an existing instance
        instance = instance or model.find_existing(self.serialize())

        if not instance and not allow_create:
            # so that we don't create when we want to delete or update
            return None
        instance = instance or model()

        # keep track of what we've changed
        update_fields = []
        # sets field on the model using the activity value
        for field in instance.simple_fields:
            try:
                changed = field.set_field_from_activity(
                    instance, self, overwrite=overwrite
                )
                if changed:
                    update_fields.append(field.name)
            except AttributeError as e:
                raise ActivitySerializerError(e)

        # image fields have to be set after other fields because they can save
        # too early and jank up users
        for field in instance.image_fields:
            changed = field.set_field_from_activity(
                instance, self, save=save, overwrite=overwrite
            )
            if changed:
                update_fields.append(field.name)

        if not save:
            return instance

        with transaction.atomic():
            # can't force an update on fields unless the object already exists in the db
            if not instance.id:
                update_fields = None
            # we can't set many to many and reverse fields on an unsaved object
            try:
                try:
                    instance.save(broadcast=False, update_fields=update_fields)
                except TypeError:
                    instance.save(update_fields=update_fields)
            except IntegrityError as e:
                raise ActivitySerializerError(e)

            # add many to many fields, which have to be set post-save
            for field in instance.many_to_many_fields:
                # mention books/users, for example
                field.set_field_from_activity(instance, self)

        # reversed relationships in the models
        for (
            model_field_name,
            activity_field_name,
        ) in instance.deserialize_reverse_fields:
            # attachments on Status, for example
            values = getattr(self, activity_field_name)
            if values is None or values is MISSING:
                continue

            model_field = getattr(model, model_field_name)
            # creating a Work, model_field is 'editions'
            # creating a User, model field is 'key_pair'
            related_model = model_field.field.model
            related_field_name = model_field.field.name

            for item in values:
                set_related_field.delay(
                    related_model.__name__,
                    instance.__class__.__name__,
                    related_field_name,
                    instance.remote_id,
                    item,
                )
        return instance

    def serialize(self, **kwargs):
        """convert to dictionary with context attr"""
        omit = kwargs.get("omit", ())
        data = self.__dict__.copy()
        # recursively serialize
        for (k, v) in data.items():
            try:
                if issubclass(type(v), ActivityObject):
                    data[k] = v.serialize()
            except TypeError:
                pass
        data = {k: v for (k, v) in data.items() if v is not None and k not in omit}
        if "@context" not in omit:
            data["@context"] = "https://www.w3.org/ns/activitystreams"
        return data


@app.task(queue="medium_priority")
@transaction.atomic
def set_related_field(
    model_name, origin_model_name, related_field_name, related_remote_id, data
):
    """load reverse related fields (editions, attachments) without blocking"""
    model = apps.get_model(f"bookwyrm.{model_name}", require_ready=True)
    origin_model = apps.get_model(f"bookwyrm.{origin_model_name}", require_ready=True)

    if isinstance(data, str):
        existing = model.find_existing_by_remote_id(data)
        if existing:
            data = existing.to_activity()
        else:
            data = get_data(data)
    activity = model.activity_serializer(**data)

    # this must exist because it's the object that triggered this function
    instance = origin_model.find_existing_by_remote_id(related_remote_id)
    if not instance:
        raise ValueError(f"Invalid related remote id: {related_remote_id}")

    # set the origin's remote id on the activity so it will be there when
    # the model instance is created
    # edition.parentWork = instance, for example
    model_field = getattr(model, related_field_name)
    if hasattr(model_field, "activitypub_field"):
        setattr(activity, getattr(model_field, "activitypub_field"), instance.remote_id)
    item = activity.to_model()

    # if the related field isn't serialized (attachments on Status), then
    # we have to set it post-creation
    if not hasattr(model_field, "activitypub_field"):
        setattr(item, related_field_name, instance)
        item.save()


def get_model_from_type(activity_type):
    """given the activity, what type of model"""
    models = apps.get_models()
    model = [
        m
        for m in models
        if hasattr(m, "activity_serializer")
        and hasattr(m.activity_serializer, "type")
        and m.activity_serializer.type == activity_type
    ]
    if not model:
        raise ActivitySerializerError(
            f'No model found for activity type "{activity_type}"'
        )
    return model[0]


def resolve_remote_id(
    remote_id, model=None, refresh=False, save=True, get_activity=False
):
    """take a remote_id and return an instance, creating if necessary"""
    if model:  # a bonus check we can do if we already know the model
        if isinstance(model, str):
            model = apps.get_model(f"bookwyrm.{model}", require_ready=True)
        result = model.find_existing_by_remote_id(remote_id)
        if result and not refresh:
            return result if not get_activity else result.to_activity_dataclass()

    # load the data and create the object
    try:
        data = get_data(remote_id)
    except ConnectorException:
        raise ActivitySerializerError(
            f"Could not connect to host for remote_id: {remote_id}"
        )
    # determine the model implicitly, if not provided
    # or if it's a model with subclasses like Status, check again
    if not model or hasattr(model.objects, "select_subclasses"):
        model = get_model_from_type(data.get("type"))

    # check for existing items with shared unique identifiers
    result = model.find_existing(data)
    if result and not refresh:
        return result if not get_activity else result.to_activity_dataclass()

    item = model.activity_serializer(**data)
    if get_activity:
        return item

    # if we're refreshing, "result" will be set and we'll update it
    return item.to_model(model=model, instance=result, save=save)


@dataclass(init=False)
class Link(ActivityObject):
    """for tagging a book in a status"""

    href: str
    name: str = None
    mediaType: str = None
    id: str = None
    attributedTo: str = None
    type: str = "Link"

    def serialize(self, **kwargs):
        """remove fields"""
        omit = ("id", "type", "@context")
        return super().serialize(omit=omit)


@dataclass(init=False)
class Mention(Link):
    """a subtype of Link for mentioning an actor"""

    type: str = "Mention"
