''' basics for an activitypub serializer '''
from dataclasses import dataclass, fields, MISSING
from json import JSONEncoder

from bookwyrm import books_manager, models

from django.db.models.fields.related_descriptors \
        import ForwardManyToOneDescriptor


class ActivityEncoder(JSONEncoder):
    '''  used to convert an Activity object into json '''
    def default(self, o):
        return o.__dict__


@dataclass
class Image:
    ''' image block '''
    url: str
    type: str = 'Image'


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
                if field.default == MISSING:
                    raise TypeError('Missing required field: %s' % field.name)
                value = field.default
            setattr(self, field.name, value)


    def to_model(self, model, instance=None):
        ''' convert from an activity to a model instance '''
        if not isinstance(self, model.activity_serializer):
            raise TypeError('Wrong activity type for model')

        # check for an existing instance, if we're not updating a known obj
        if not instance:
            try:
                return model.objects.get(remote_id=self.id)
            except model.DoesNotExist:
                pass

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


def resolve_foreign_key(model, remote_id):
    ''' look up the remote_id on an activity json field '''
    if model in [models.Edition, models.Work]:
        return books_manager.get_or_create_book(remote_id)

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
