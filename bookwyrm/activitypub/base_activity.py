''' basics for an activitypub serializer '''
from dataclasses import dataclass, fields, MISSING
from json import JSONEncoder

from django.db.models.fields.related_descriptors \
    import ForwardManyToOneDescriptor, ManyToManyDescriptor, \
        ReverseManyToOneDescriptor
from django.db.models.fields.files import ImageFileDescriptor

from bookwyrm.connectors import ConnectorException, get_data

class ActivitySerializerError(ValueError):
    ''' routine problems serializing activitypub json '''


class ActivityEncoder(JSONEncoder):
    '''  used to convert an Activity object into json '''
    def default(self, o):
        return o.__dict__


@dataclass
class Link:
    ''' for tagging a book in a status '''
    href: str
    name: str
    type: str = 'Link'


@dataclass
class Mention(Link):
    ''' a subtype of Link for mentioning an actor '''
    type: str = 'Mention'


@dataclass
class Signature:
    ''' public key block '''
    creator: str
    created: str
    signatureValue: str
    type: str = 'RsaSignature2017'


@dataclass(init=False)
class ActivityObject:
    ''' actor activitypub json '''
    id: str
    type: str

    def __init__(self, **kwargs):
        ''' this lets you pass in an object with fields that aren't in the
        dataclass, which it ignores. Any field in the dataclass is required or
        has a default value '''
        for field in fields(self):
            try:
                value = kwargs[field.name]
            except KeyError:
                if field.default == MISSING and \
                        field.default_factory == MISSING:
                    raise ActivitySerializerError(\
                            'Missing required field: %s' % field.name)
                value = field.default
            setattr(self, field.name, value)


    def to_model(self, model, instance=None):
        ''' convert from an activity to a model instance '''
        if not isinstance(self, model.activity_serializer):
            raise ActivitySerializerError(
                'Wrong activity type "%s" for model "%s" (expects "%s")' % \
                        (self.__class__,
                         model.__name__,
                         model.activity_serializer)
            )

        # check for an existing instance, if we're not updating a known obj
        if not instance:
            instance = find_existing_by_remote_id(model, self.id)
	# TODO: deduplicate books by identifiers

        mapped_fields = {}
        many_to_many_fields = {}
        one_to_many_fields = {}
        image_fields = {}

        for field in model._meta.get_fields():
            if not hasattr(field, 'field_to_activity'):
                continue
            activitypub_field = field.get_activitypub_field()
            value = field.field_from_activity(getattr(self, activitypub_field))
            if value is None:
                continue

            model_field = getattr(model, field.name)

            if isinstance(model_field, ForwardManyToOneDescriptor):
                mapped_fields[field.name] = value
            if isinstance(model_field, ManyToManyDescriptor):
                # status mentions book/users
                many_to_many_fields[field.name] = value
            elif isinstance(model_field, ReverseManyToOneDescriptor):
                # attachments on Status, for example
                one_to_many_fields[field.name] = value
            elif isinstance(model_field, ImageFileDescriptor):
                # image fields need custom handling
                print(model_field, field.name, value)
                image_fields[field.name] = value
            else:
                if value == MISSING:
                    value = None
                mapped_fields[field.name] = value


        if instance:
            # updating an existing model instance
            for k, v in mapped_fields.items():
                setattr(instance, k, v)
            instance.save()
        else:
            # creating a new model instance
            instance = model.objects.create(**mapped_fields)

        # --- these are all fields that can't be saved until after the
        # instance has an id (after it's been saved). ---------------#

        # add images
        for (model_key, value) in image_fields.items():
            if not value:
                continue
            getattr(instance, model_key).save(*value, save=True)

        # add many to many fields
        for (model_key, values) in many_to_many_fields.items():
            # mention books, mention users, followers
            getattr(instance, model_key).set(values)

        # add one to many fields
        for (model_key, values) in one_to_many_fields.items():
            if values == MISSING:
                continue
            model_field = getattr(instance, model_key)
            related_model = model_field.model
            for item in values:
                if isinstance(item, str):
                    item = resolve_remote_id(related_model, item)
                else:
                    item = related_model.activity_serializer(**item)
                    item = item.to_model(related_model)
                field_name = instance.__class__.__name__.lower()
                setattr(item, field_name, instance)
                item.save()

        return instance


    def serialize(self):
        ''' convert to dictionary with context attr '''
        data = self.__dict__
        data['@context'] = 'https://www.w3.org/ns/activitystreams'
        return data


def find_existing_by_remote_id(model, remote_id):
    ''' check for an existing instance of this id in the db '''
    objects = model.objects
    if hasattr(model.objects, 'select_subclasses'):
        objects = objects.select_subclasses()

    # first, check for an existing copy in the database
    result = objects.filter(
        remote_id=remote_id
    ).first()

    if not result and hasattr(model, 'origin_id'):
        result = objects.filter(
            origin_id=remote_id
        ).first()
    return result


def resolve_remote_id(model, remote_id, refresh=False):
    ''' look up the remote_id in the database or load it remotely '''
    result = find_existing_by_remote_id(model, remote_id)
    if result and not refresh:
        return result

    # load the data and create the object
    try:
        data = get_data(remote_id)
    except (ConnectorException, ConnectionError):
        raise ActivitySerializerError(
            'Could not connect to host for remote_id in %s model: %s' % \
                (model.__name__, remote_id))

    item = model.activity_serializer(**data)
    # if we're refreshing, "result" will be set and we'll update it
    return item.to_model(model, instance=result)
