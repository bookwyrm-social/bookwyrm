''' basics for an activitypub serializer '''
from dataclasses import dataclass, fields, MISSING
from json import JSONEncoder
from uuid import uuid4

import dateutil.parser
from dateutil.parser import ParserError
from django.core.files.base import ContentFile
from django.db.models.fields.related_descriptors \
    import ForwardManyToOneDescriptor, ManyToManyDescriptor, \
        ReverseManyToOneDescriptor
from django.db.models.fields import DateTimeField
from django.db.models.fields.files import ImageFileDescriptor
from django.db.models.query_utils import DeferredAttribute
from django.utils import timezone

from bookwyrm.connectors import ConnectorException, get_data, get_image

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

        model_fields = [m.name for m in model._meta.get_fields()]
        mapped_fields = {}
        many_to_many_fields = {}
        one_to_many_fields = {}
        image_fields = {}

        for mapping in model.activity_mappings:
            if mapping.model_key not in model_fields:
                continue
            # value is None if there's a default that isn't supplied
            # in the activity but is supplied in the formatter
            value = None
            if mapping.activity_key:
                value = getattr(self, mapping.activity_key)
            model_field = getattr(model, mapping.model_key)

            formatted_value = mapping.model_formatter(value)
            if isinstance(model_field, DeferredAttribute) and \
                    isinstance(model_field.field, DateTimeField):
                try:
                    date_value = dateutil.parser.parse(formatted_value)
                    try:
                        formatted_value = timezone.make_aware(date_value)
                    except ValueError:
                        formatted_value = date_value
                except (ParserError, TypeError):
                    formatted_value = None
            elif isinstance(model_field, ForwardManyToOneDescriptor):
                if not formatted_value:
                    continue
                # foreign key remote id reolver (work on Edition, for example)
                fk_model = model_field.field.related_model
                if isinstance(formatted_value, dict) and \
                        formatted_value.get('id'):
                    # if the AP field is a serialized object (as in Add)
                    remote_id = formatted_value['id']
                else:
                    # if the field is just a remote_id (as in every other case)
                    remote_id = formatted_value
                reference = resolve_remote_id(fk_model, remote_id)
                mapped_fields[mapping.model_key] = reference
            elif isinstance(model_field, ManyToManyDescriptor):
                # status mentions book/users
                many_to_many_fields[mapping.model_key] = formatted_value
            elif isinstance(model_field, ReverseManyToOneDescriptor):
                # attachments on Status, for example
                one_to_many_fields[mapping.model_key] = formatted_value
            elif isinstance(model_field, ImageFileDescriptor):
                # image fields need custom handling
                image_fields[mapping.model_key] = formatted_value
            else:
                if formatted_value == MISSING:
                    formatted_value = None
                mapped_fields[mapping.model_key] = formatted_value

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
            formatted_value = image_formatter(value)
            if not formatted_value:
                continue
            getattr(instance, model_key).save(*formatted_value, save=True)

        # add many to many fields
        for (model_key, values) in many_to_many_fields.items():
            # mention books, mention users
            if values == MISSING:
                continue
            model_field = getattr(instance, model_key)
            model = model_field.model
            items = []
            for link in values:
                if isinstance(link, dict):
                    # check that the Type matches the model (Status
                    # tags contain both user mentions and book tags)
                    if not model.activity_serializer.type == \
                            link.get('type'):
                        continue
                    remote_id = link.get('href')
                else:
                    remote_id = link
                items.append(
                    resolve_remote_id(model, remote_id)
                )
            getattr(instance, model_key).set(items)

        # add one to many fields
        for (model_key, values) in one_to_many_fields.items():
            if values == MISSING:
                continue
            model_field = getattr(instance, model_key)
            model = model_field.model
            for item in values:
                if isinstance(item, str):
                    item = resolve_remote_id(model, item)
                else:
                    item = model.activity_serializer(**item)
                    item = item.to_model(model)
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


def image_formatter(image_slug):
    ''' helper function to load images and format them for a model '''
    # when it's an inline image (User avatar/icon, Book cover), it's a json
    # blob, but when it's an attached image, it's just a url
    if isinstance(image_slug, dict):
        url = image_slug.get('url')
    elif isinstance(image_slug, str):
        url = image_slug
    else:
        return None
    if not url:
        return None

    response = get_image(url)
    if not response:
        return None

    image_name = str(uuid4()) + '.' + url.split('.')[-1]
    image_content = ContentFile(response.content)
    return [image_name, image_content]
