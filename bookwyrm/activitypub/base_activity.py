''' basics for an activitypub serializer '''
from dataclasses import dataclass, fields, MISSING
from json import JSONEncoder
from uuid import uuid4

from django.core.files.base import ContentFile
from django.db.models.fields.related_descriptors \
        import ForwardManyToOneDescriptor, ManyToManyDescriptor, \
        ReverseManyToOneDescriptor
from django.db.models.fields.files import ImageFileDescriptor
import requests

from bookwyrm import books_manager, models


class ActivitySerializerError(ValueError):
    ''' routine problems serializing activitypub json '''


class ActivityEncoder(JSONEncoder):
    '''  used to convert an Activity object into json '''
    def default(self, o):
        return o.__dict__


@dataclass
class Link():
    ''' for tagging a book in a status '''
    href: str
    name: str
    type: str = 'Link'

@dataclass
class Mention(Link):
    ''' a subtype of Link for mentioning an actor '''
    type: str = 'Mention'


@dataclass
class PublicKey:
    ''' public key block '''
    id: str
    owner: str
    publicKeyPem: str


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
            raise ActivitySerializerError('Wrong activity type for model')

        # check for an existing instance, if we're not updating a known obj
        if not instance:
            try:
                return model.objects.get(remote_id=self.id)
            except model.DoesNotExist:
                pass

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
            if isinstance(model_field, ForwardManyToOneDescriptor) and \
                    formatted_value:
                # foreign key remote id reolver
                fk_model = model_field.field.related_model
                reference = resolve_foreign_key(fk_model, formatted_value)
                mapped_fields[mapping.model_key] = reference
            elif isinstance(model_field, ManyToManyDescriptor):
                many_to_many_fields[mapping.model_key] = formatted_value
            elif isinstance(model_field, ReverseManyToOneDescriptor):
                # attachments on statuses, for example
                one_to_many_fields[mapping.model_key] = formatted_value
            elif isinstance(model_field, ImageFileDescriptor):
                # image fields need custom handling
                image_fields[mapping.model_key] = formatted_value
            else:
                mapped_fields[mapping.model_key] = formatted_value

        if instance:
            # updating an existing model isntance
            for k, v in mapped_fields.items():
                setattr(instance, k, v)
            instance.save()
        else:
            # creating a new model instance
            instance = model.objects.create(**mapped_fields)

        # add many-to-many fields
        for (model_key, values) in many_to_many_fields.items():
            getattr(instance, model_key).set(values)
        instance.save()

        # add images
        for (model_key, value) in image_fields.items():
            if not value:
                continue
            #formatted_value = image_formatter(value)
            getattr(instance, model_key).save(*value, save=True)

        # add one to many fields
        for (model_key, values) in one_to_many_fields.items():
            items = []
            for item in values:
                # the reference id wasn't available at creation time
                setattr(item, instance.__class__.__name__.lower(), instance)
                item.save()
                items.append(item)
            if items:
                getattr(instance, model_key).set(items)
                instance.save()
        return instance


    def serialize(self):
        ''' convert to dictionary with context attr '''
        data = self.__dict__
        data['@context'] = 'https://www.w3.org/ns/activitystreams'
        return data


def resolve_foreign_key(model, remote_id):
    ''' look up the remote_id on an activity json field '''
    if model in [models.Edition, models.Work, models.Book]:
        return books_manager.get_or_create_book(remote_id)

    result = model.objects
    if hasattr(model.objects, 'select_subclasses'):
        result = result.select_subclasses()

    result = result.filter(
        remote_id=remote_id
    ).first()

    if not result:
        raise ActivitySerializerError(
            'Could not resolve remote_id in %s model: %s' % \
                (model.__name__, remote_id))
    return result


def tag_formatter(tags, tag_type):
    ''' helper function to extract foreign keys from tag activity json '''
    if not isinstance(tags, list):
        return []
    items = []
    types = {
        'Book': models.Book,
        'Mention': models.User,
    }
    for tag in [t for t in tags if t.get('type') == tag_type]:
        if not tag_type in types:
            continue
        remote_id = tag.get('href')
        try:
            item = resolve_foreign_key(types[tag_type], remote_id)
        except ActivitySerializerError:
            continue
        items.append(item)
    return items


def image_formatter(image_json):
    ''' helper function to load images and format them for a model '''
    url = image.get('url')
    if not url:
        return None
    try:
        response = requests.get(url)
    except ConnectionError:
        return None
    if not response.ok:
        return None

    image_name = str(uuid4()) + '.' + url.split('.')[-1]
    image_content = ContentFile(response.content)
    return [image_name, image_content]


def image_attachments_formatter(images_json):
    ''' deserialize a list of images '''
    attachments = []
    for image in images_json:
        caption = image.get('name')
        attachment = models.Attachment(caption=caption)
        image_field = image_formatter(image)
        if not image_field:
            continue
        attachment.image.save(*image_field, save=False)
        attachments.append(attachment)
    return attachments
