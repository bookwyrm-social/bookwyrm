''' activitypub-aware django model fields '''
from dataclasses import MISSING
import re
from uuid import uuid4

import dateutil.parser
from dateutil.parser import ParserError
from django.contrib.postgres.fields import ArrayField as DjangoArrayField
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from bookwyrm import activitypub
from bookwyrm.sanitize_html import InputHtmlParser
from bookwyrm.settings import DOMAIN
from bookwyrm.connectors import get_image


def validate_remote_id(value):
    ''' make sure the remote_id looks like a url '''
    if not value or not re.match(r'^http.?:\/\/[^\s]+$', value):
        raise ValidationError(
            _('%(value)s is not a valid remote_id'),
            params={'value': value},
        )

def validate_username(value):
    ''' make sure usernames look okay '''
    if not re.match(r'^[A-Za-z\-_\.]+$', value):
        raise ValidationError(
            _('%(value)s is not a valid remote_id'),
            params={'value': value},
        )


class ActivitypubFieldMixin:
    ''' make a database field serializable '''
    def __init__(self, *args, \
                 activitypub_field=None, activitypub_wrapper=None,
                 deduplication_field=False, **kwargs):
        self.deduplication_field = deduplication_field
        if activitypub_wrapper:
            self.activitypub_wrapper = activitypub_field
            self.activitypub_field = activitypub_wrapper
        else:
            self.activitypub_field = activitypub_field
        super().__init__(*args, **kwargs)


    def set_field_from_activity(self, instance, data):
        ''' helper function for assinging a value to the field '''
        try:
            value = getattr(data, self.get_activitypub_field())
        except AttributeError:
            # masssively hack-y workaround for boosts
            if self.get_activitypub_field() != 'attributedTo':
                raise
            value = getattr(data, 'actor')
        formatted = self.field_from_activity(value)
        if formatted is None or formatted is MISSING:
            return
        setattr(instance, self.name, formatted)


    def set_activity_from_field(self, activity, instance):
        ''' update the json object '''
        value = getattr(instance, self.name)
        formatted = self.field_to_activity(value)
        if formatted is None:
            return

        key = self.get_activitypub_field()
        # TODO: surely there's a better way
        if instance.__class__.__name__ == 'Boost' and key == 'attributedTo':
            key = 'actor'
        if isinstance(activity.get(key), list):
            activity[key] += formatted
        else:
            activity[key] = formatted


    def field_to_activity(self, value):
        ''' formatter to convert a model value into activitypub '''
        if hasattr(self, 'activitypub_wrapper'):
            return {self.activitypub_wrapper: value}
        return value

    def field_from_activity(self, value):
        ''' formatter to convert activitypub into a model value '''
        if hasattr(self, 'activitypub_wrapper'):
            value = value.get(self.activitypub_wrapper)
        return value

    def get_activitypub_field(self):
        ''' model_field_name to activitypubFieldName '''
        if self.activitypub_field:
            return self.activitypub_field
        name = self.name.split('.')[-1]
        components = name.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])


class ActivitypubRelatedFieldMixin(ActivitypubFieldMixin):
    ''' default (de)serialization for foreign key and one to one '''
    def __init__(self, *args, load_remote=True, **kwargs):
        self.load_remote = load_remote
        super().__init__(*args, **kwargs)

    def field_from_activity(self, value):
        if not value:
            return None

        related_model = self.related_model
        if isinstance(value, dict) and value.get('id'):
            if not self.load_remote:
                # only look in the local database
                return related_model.find_existing(value)
            # this is an activitypub object, which we can deserialize
            activity_serializer = related_model.activity_serializer
            return activity_serializer(**value).to_model(related_model)
        try:
            # make sure the value looks like a remote id
            validate_remote_id(value)
        except ValidationError:
            # we don't know what this is, ignore it
            return None
        # gets or creates the model field from the remote id
        if not self.load_remote:
            # only look in the local database
            return related_model.find_existing_by_remote_id(value)
        return activitypub.resolve_remote_id(related_model, value)


class RemoteIdField(ActivitypubFieldMixin, models.CharField):
    ''' a url that serves as a unique identifier '''
    def __init__(self, *args, max_length=255, validators=None, **kwargs):
        validators = validators or [validate_remote_id]
        super().__init__(
            *args, max_length=max_length, validators=validators,
            **kwargs
        )
        # for this field, the default is true. false everywhere else.
        self.deduplication_field = kwargs.get('deduplication_field', True)


class UsernameField(ActivitypubFieldMixin, models.CharField):
    ''' activitypub-aware username field '''
    def __init__(self, activitypub_field='preferredUsername'):
        self.activitypub_field = activitypub_field
        # I don't totally know why pylint is mad at this, but it makes it work
        super( #pylint: disable=bad-super-call
            ActivitypubFieldMixin, self
        ).__init__(
            _('username'),
            max_length=150,
            unique=True,
            validators=[validate_username],
            error_messages={
                'unique': _('A user with that username already exists.'),
            },
        )

    def deconstruct(self):
        ''' implementation of models.Field deconstruct '''
        name, path, args, kwargs = super().deconstruct()
        del kwargs['verbose_name']
        del kwargs['max_length']
        del kwargs['unique']
        del kwargs['validators']
        del kwargs['error_messages']
        return name, path, args, kwargs

    def field_to_activity(self, value):
        return value.split('@')[0]


PrivacyLevels = models.TextChoices('Privacy', [
    'public',
    'unlisted',
    'followers',
    'direct'
])

class PrivacyField(ActivitypubFieldMixin, models.CharField):
    ''' this maps to two differente activitypub fields '''
    public = 'https://www.w3.org/ns/activitystreams#Public'
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, max_length=255,
            choices=PrivacyLevels.choices, default='public')

    def set_field_from_activity(self, instance, data):
        to = data.to
        cc = data.cc
        if to == [self.public]:
            setattr(instance, self.name, 'public')
        elif cc == []:
            setattr(instance, self.name, 'direct')
        elif self.public in cc:
            setattr(instance, self.name, 'unlisted')
        else:
            setattr(instance, self.name, 'followers')

    def set_activity_from_field(self, activity, instance):
        mentions = [u.remote_id for u in instance.mention_users.all()]
        # this is a link to the followers list
        followers = instance.user.__class__._meta.get_field('followers')\
                .field_to_activity(instance.user.followers)
        if instance.privacy == 'public':
            activity['to'] = [self.public]
            activity['cc'] = [followers] + mentions
        elif instance.privacy == 'unlisted':
            activity['to'] = [followers]
            activity['cc'] = [self.public] + mentions
        elif instance.privacy == 'followers':
            activity['to'] = [followers]
            activity['cc'] = mentions
        if instance.privacy == 'direct':
            activity['to'] = mentions
            activity['cc'] = []


class ForeignKey(ActivitypubRelatedFieldMixin, models.ForeignKey):
    ''' activitypub-aware foreign key field '''
    def field_to_activity(self, value):
        if not value:
            return None
        return value.remote_id


class OneToOneField(ActivitypubRelatedFieldMixin, models.OneToOneField):
    ''' activitypub-aware foreign key field '''
    def field_to_activity(self, value):
        if not value:
            return None
        return value.to_activity()


class ManyToManyField(ActivitypubFieldMixin, models.ManyToManyField):
    ''' activitypub-aware many to many field '''
    def __init__(self, *args, link_only=False, **kwargs):
        self.link_only = link_only
        super().__init__(*args, **kwargs)

    def set_field_from_activity(self, instance, data):
        ''' helper function for assinging a value to the field '''
        value = getattr(data, self.get_activitypub_field())
        formatted = self.field_from_activity(value)
        if formatted is None or formatted is MISSING:
            return
        getattr(instance, self.name).set(formatted)

    def field_to_activity(self, value):
        if self.link_only:
            return '%s/%s' % (value.instance.remote_id, self.name)
        return [i.remote_id for i in value.all()]

    def field_from_activity(self, value):
        items = []
        if value is None or value is MISSING:
            return []
        for remote_id in value:
            try:
                validate_remote_id(remote_id)
            except ValidationError:
                continue
            items.append(
                activitypub.resolve_remote_id(self.related_model, remote_id)
            )
        return items


class TagField(ManyToManyField):
    ''' special case of many to many that uses Tags '''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.activitypub_field = 'tag'

    def field_to_activity(self, value):
        tags = []
        for item in value.all():
            activity_type = item.__class__.__name__
            if activity_type == 'User':
                activity_type = 'Mention'
            tags.append(activitypub.Link(
                href=item.remote_id,
                name=getattr(item, item.name_field),
                type=activity_type
            ))
        return tags

    def field_from_activity(self, value):
        if not isinstance(value, list):
            return None
        items = []
        for link_json in value:
            link = activitypub.Link(**link_json)
            tag_type = link.type if link.type != 'Mention' else 'Person'
            if tag_type == 'Book':
                tag_type = 'Edition'
            if tag_type != self.related_model.activity_serializer.type:
                # tags can contain multiple types
                continue
            items.append(
                activitypub.resolve_remote_id(self.related_model, link.href)
            )
        return items


def image_serializer(value, alt):
    ''' helper for serializing images '''
    if value and hasattr(value, 'url'):
        url = value.url
    else:
        return None
    url = 'https://%s%s' % (DOMAIN, url)
    return activitypub.Image(url=url, name=alt)


class ImageField(ActivitypubFieldMixin, models.ImageField):
    ''' activitypub-aware image field '''
    def __init__(self, *args, alt_field=None, **kwargs):
        self.alt_field = alt_field
        super().__init__(*args, **kwargs)

    # pylint: disable=arguments-differ
    def set_field_from_activity(self, instance, data, save=True):
        ''' helper function for assinging a value to the field '''
        value = getattr(data, self.get_activitypub_field())
        formatted = self.field_from_activity(value)
        if formatted is None or formatted is MISSING:
            return
        getattr(instance, self.name).save(*formatted, save=save)

    def set_activity_from_field(self, activity, instance):
        value = getattr(instance, self.name)
        if value is None:
            return
        alt_text = getattr(instance, self.alt_field)
        formatted = self.field_to_activity(value, alt_text)

        key = self.get_activitypub_field()
        activity[key] = formatted


    def field_to_activity(self, value, alt=None):
        return image_serializer(value, alt)


    def field_from_activity(self, value):
        image_slug = value
        # when it's an inline image (User avatar/icon, Book cover), it's a json
        # blob, but when it's an attached image, it's just a url
        if isinstance(image_slug, dict):
            url = image_slug.get('url')
        elif isinstance(image_slug, str):
            url = image_slug
        else:
            return None

        try:
            validate_remote_id(url)
        except ValidationError:
            return None

        response = get_image(url)
        if not response:
            return None

        image_name = str(uuid4()) + '.' + url.split('.')[-1]
        image_content = ContentFile(response.content)
        return [image_name, image_content]


class DateTimeField(ActivitypubFieldMixin, models.DateTimeField):
    ''' activitypub-aware datetime field '''
    def field_to_activity(self, value):
        if not value:
            return None
        return value.isoformat()

    def field_from_activity(self, value):
        try:
            date_value = dateutil.parser.parse(value)
            try:
                return timezone.make_aware(date_value)
            except ValueError:
                return date_value
        except (ParserError, TypeError):
            return None

class HtmlField(ActivitypubFieldMixin, models.TextField):
    ''' a text field for storing html '''
    def field_from_activity(self, value):
        if not value or value == MISSING:
            return None
        sanitizer = InputHtmlParser()
        sanitizer.feed(value)
        return sanitizer.get_output()

class ArrayField(ActivitypubFieldMixin, DjangoArrayField):
    ''' activitypub-aware array field '''
    def field_to_activity(self, value):
        return [str(i) for i in value]

class CharField(ActivitypubFieldMixin, models.CharField):
    ''' activitypub-aware char field '''

class TextField(ActivitypubFieldMixin, models.TextField):
    ''' activitypub-aware text field '''

class BooleanField(ActivitypubFieldMixin, models.BooleanField):
    ''' activitypub-aware boolean field '''

class IntegerField(ActivitypubFieldMixin, models.IntegerField):
    ''' activitypub-aware boolean field '''
