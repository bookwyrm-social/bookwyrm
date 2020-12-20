''' basics for an activitypub serializer '''
from dataclasses import dataclass, fields, MISSING
from json import JSONEncoder

from django.apps import apps
from django.db import transaction

from bookwyrm.connectors import ConnectorException, get_data
from bookwyrm.tasks import app

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


    @transaction.atomic
    def to_model(self, model, instance=None, save=True):
        ''' convert from an activity to a model instance '''
        if not isinstance(self, model.activity_serializer):
            raise ActivitySerializerError(
                'Wrong activity type "%s" for model "%s" (expects "%s")' % \
                        (self.__class__,
                         model.__name__,
                         model.activity_serializer)
            )

        if hasattr(model, 'ignore_activity') and model.ignore_activity(self):
            return instance

        # check for an existing instance, if we're not updating a known obj
        instance = instance or model.find_existing(self.serialize()) or model()

        for field in instance.simple_fields:
            field.set_field_from_activity(instance, self)

        # image fields have to be set after other fields because they can save
        # too early and jank up users
        for field in instance.image_fields:
            field.set_field_from_activity(instance, self, save=save)

        if not save:
            return instance

        # we can't set many to many and reverse fields on an unsaved object
        instance.save()

        # add many to many fields, which have to be set post-save
        for field in instance.many_to_many_fields:
            # mention books/users, for example
            field.set_field_from_activity(instance, self)

        # reversed relationships in the models
        for (model_field_name, activity_field_name) in \
                instance.deserialize_reverse_fields:
            # attachments on Status, for example
            values = getattr(self, activity_field_name)
            if values is None or values is MISSING:
                continue
            try:
                # this is for one to many
                related_model = getattr(model, model_field_name).field.model
            except AttributeError:
                # it's a one to one or foreign key
                related_model = getattr(model, model_field_name)\
                        .related.related_model
                values = [values]

            for item in values:
                set_related_field.delay(
                    related_model.__name__,
                    instance.__class__.__name__,
                    instance.__class__.__name__.lower(),
                    instance.remote_id,
                    item
                )
        return instance


    def serialize(self):
        ''' convert to dictionary with context attr '''
        data = self.__dict__
        data['@context'] = 'https://www.w3.org/ns/activitystreams'
        return data


@app.task
@transaction.atomic
def set_related_field(
        model_name, origin_model_name,
        related_field_name, related_remote_id, data):
    ''' load reverse related fields (editions, attachments) without blocking '''
    model = apps.get_model('bookwyrm.%s' % model_name, require_ready=True)
    origin_model = apps.get_model(
        'bookwyrm.%s' % origin_model_name,
        require_ready=True
    )

    if isinstance(data, str):
        item = resolve_remote_id(model, data, save=False)
    else:
        # look for a match based on all the available data
        item = model.find_existing(data)
        if not item:
            # create a new model instance
            item = model.activity_serializer(**data)
            item = item.to_model(model, save=False)
    # this must exist because it's the object that triggered this function
    instance = origin_model.find_existing_by_remote_id(related_remote_id)
    if not instance:
        raise ValueError('Invalid related remote id: %s' % related_remote_id)

    # edition.parent_work = instance, for example
    setattr(item, related_field_name, instance)
    item.save()


def resolve_remote_id(model, remote_id, refresh=False, save=True):
    ''' take a remote_id and return an instance, creating if necessary '''
    result = model.find_existing_by_remote_id(remote_id)
    if result and not refresh:
        return result

    # load the data and create the object
    try:
        data = get_data(remote_id)
    except (ConnectorException, ConnectionError):
        raise ActivitySerializerError(
            'Could not connect to host for remote_id in %s model: %s' % \
                (model.__name__, remote_id))

    # check for existing items with shared unique identifiers
    if not result:
        result = model.find_existing(data)
        if result and not refresh:
            return result

    item = model.activity_serializer(**data)
    # if we're refreshing, "result" will be set and we'll update it
    return item.to_model(model, instance=result, save=save)
