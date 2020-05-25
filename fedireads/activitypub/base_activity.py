''' basics for an activitypub serializer '''
from dataclasses import dataclass, fields, MISSING
from json import JSONEncoder

from django.db.models.fields.related_descriptors \
        import ForwardManyToOneDescriptor


class ActivityEncoder(JSONEncoder):
    ''' allows conversion to JSON '''
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


@dataclass(init=False)
class ActivityObject:
    ''' actor activitypub json '''
    id: str
    type: str

    def __init__(self, **kwargs):
        ''' treat fields as required but not exhaustive '''
        for field in fields(self):
            try:
                value = kwargs[field.name]
            except KeyError:
                if field.default == MISSING:
                    raise TypeError('Missing required field: %s' % field.name)
                value = field.default
            setattr(self, field.name, value)


    def to_model(self, model):
        ''' convert from an activity to a model '''
        if not isinstance(self, model.activity_serializer):
            raise TypeError('Wrong activity type for model')

        model_fields = {}
        for mapping in model.activity_mappings:
            value = getattr(self, mapping.activity_key)
            model_field = getattr(model, mapping.model_key)

            # remote_id -> foreign key resolver
            if isinstance(model_field, ForwardManyToOneDescriptor):
                fk_model = model_field.field.related_model
                value = resolve_foreign_key(fk_model, value)

            model_fields[mapping.model_key] = value
        return model.objects.create(**model_fields)


    def serialize(self):
        ''' convert to dictionary with context attr '''
        data = self.__dict__
        data['@context'] = 'https://www.w3.org/ns/activitystreams'
        return data


def resolve_foreign_key(model, remote_id):
    ''' look up the remote_id on an activity json field '''
    if hasattr(model.objects, 'select_subclasses'):
        return model.objects.select_subclasses().filter(
            remote_id=remote_id
        ).first()
    return model.objects.filter(
        remote_id=remote_id
    ).first()
