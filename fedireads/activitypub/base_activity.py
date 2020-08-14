''' basics for an activitypub serializer '''
from dataclasses import dataclass, fields, MISSING
from json import JSONEncoder
from typing import List

from django.db.models.fields.related_descriptors \
        import ForwardManyToOneDescriptor


class ActivityEncoder(JSONEncoder):
    '''  used to convert an Activity object into json '''
    def default(self, o):
        return o.__dict__


@dataclass
class Image:
    ''' image block '''
    mediaType: str
    url: str
    type: str = 'Image'


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
        ''' this lets you pass in an object with fields
        that aren't in the dataclass, which it ignores.
        Any field in the dataclass is required or has a
        default value '''
        for field in fields(self):
            try:
                value = kwargs[field.name]
            except KeyError:
                if field.default == MISSING:
                    raise TypeError('Missing required field: %s' % field.name)
                value = field.default
            setattr(self, field.name, value)


    def to_model(self, model, instance=None):
        ''' convert from an activity to a model '''
        if not isinstance(self, model.activity_serializer):
            raise TypeError('Wrong activity type for model')

        model_fields = [m.name for m in model._meta.get_fields()]
        mapped_fields = {}

        for mapping in model.activity_mappings:
            if mapping.model_key not in model_fields:
                continue
            # value is None if there's a default that isn't supplied
            # in the activity but is supplied in the formatter
            value = None
            if mapping.activity_key:
                value = getattr(self, mapping.activity_key)
            model_field = getattr(model, mapping.model_key)

            # remote_id -> foreign key resolver
            if isinstance(model_field, ForwardManyToOneDescriptor) and value:
                fk_model = model_field.field.related_model
                value = resolve_foreign_key(fk_model, value)

            mapped_fields[mapping.model_key] = mapping.model_formatter(value)


        # updating an existing model isntance
        if instance:
            for k, v in mapped_fields.items():
                setattr(instance, k, v)
            instance.save()
            return instance

        # creating a new model instance
        return model.objects.create(**mapped_fields)


    def serialize(self):
        ''' convert to dictionary with context attr '''
        data = self.__dict__
        data['@context'] = 'https://www.w3.org/ns/activitystreams'
        return data


@dataclass(init=False)
class OrderedCollection(ActivityObject):
    ''' structure of an ordered collection activity '''
    totalItems: int
    first: str
    name: str = ''
    type: str = 'OrderedCollection'


@dataclass(init=False)
class OrderedCollectionPage(ActivityObject):
    ''' structure of an ordered collection activity '''
    partOf: str
    orderedItems: List
    next: str
    prev: str
    type: str = 'OrderedCollectionPage'


def resolve_foreign_key(model, remote_id):
    ''' look up the remote_id on an activity json field '''
    result = model.objects
    if hasattr(model.objects, 'select_subclasses'):
        result = result.select_subclasses()

    result = result.filter(
        remote_id=remote_id
    ).first()

    if not result:
        raise ValueError('Could not resolve remote_id in %s model: %s' % \
                (model.__name__, remote_id))
    return result
