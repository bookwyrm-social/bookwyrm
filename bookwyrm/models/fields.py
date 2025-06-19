""" activitypub-aware django model fields """
from dataclasses import MISSING
from datetime import datetime
import re
from uuid import uuid4
from urllib.parse import urljoin

import dateutil.parser
from dateutil.parser import ParserError
from django.contrib.postgres.fields import ArrayField as DjangoArrayField
from django.contrib.postgres.fields import CICharField as DjangoCICharField
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import ClearableFileInput, ImageField as DjangoImageField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.encoding import filepath_to_uri
from markdown import markdown

from bookwyrm import activitypub
from bookwyrm.connectors import get_image
from bookwyrm.utils.sanitizer import clean
from bookwyrm.utils.partial_date import (
    PartialDate,
    PartialDateModel,
    from_partial_isoformat,
)
from bookwyrm.settings import MEDIA_FULL_URL, DATA_UPLOAD_MAX_MEMORY_SIZE


def validate_remote_id(value):
    """make sure the remote_id looks like a url"""
    if not value or not re.match(r"^http.?:\/\/[^\s]+$", value):
        raise ValidationError(
            _("%(value)s is not a valid remote_id"),
            params={"value": value},
        )


def validate_localname(value):
    """make sure localnames look okay"""
    if not re.match(r"^[A-Za-z\-_\.0-9]+$", value):
        raise ValidationError(
            _("%(value)s is not a valid username"),
            params={"value": value},
        )


def validate_username(value):
    """make sure usernames look okay"""
    if not re.match(r"^[A-Za-z\-_\.0-9]+@[A-Za-z\-_\.0-9]+\.[a-z]{2,}$", value):
        raise ValidationError(
            _("%(value)s is not a valid username"),
            params={"value": value},
        )


class ActivitypubFieldMixin:
    """make a database field serializable"""

    def __init__(
        self,
        *args,
        activitypub_field=None,
        activitypub_wrapper=None,
        deduplication_field=False,
        **kwargs,
    ):
        self.deduplication_field = deduplication_field
        if activitypub_wrapper:
            self.activitypub_wrapper = activitypub_field
            self.activitypub_field = activitypub_wrapper
        else:
            self.activitypub_field = activitypub_field
        super().__init__(*args, **kwargs)

    def set_field_from_activity(
        self, instance, data, overwrite=True, allow_external_connections=True
    ):
        """helper function for assigning a value to the field. Returns if changed"""
        try:
            value = getattr(data, self.get_activitypub_field())
        except AttributeError:
            # massively hack-y workaround for boosts
            if self.get_activitypub_field() != "attributedTo":
                raise
            value = getattr(data, "actor")
        formatted = self.field_from_activity(
            value,
            allow_external_connections=allow_external_connections,
            trigger=instance,
        )
        if formatted is None or formatted is MISSING or formatted == {}:
            return False

        current_value = (
            getattr(instance, self.name) if hasattr(instance, self.name) else None
        )
        # if we're not in overwrite mode, only continue updating the field if its unset
        if current_value and not overwrite:
            return False

        # the field is unchanged
        if current_value == formatted:
            return False

        setattr(instance, self.name, formatted)
        return True

    def set_activity_from_field(self, activity, instance):
        """update the json object"""
        value = getattr(instance, self.name)
        formatted = self.field_to_activity(value)
        if formatted is None:
            return

        key = self.get_activitypub_field()
        # TODO: surely there's a better way
        if instance.__class__.__name__ == "Boost" and key == "attributedTo":
            key = "actor"
        if isinstance(activity.get(key), list):
            activity[key] += formatted
        else:
            activity[key] = formatted

    def field_to_activity(self, value):
        """formatter to convert a model value into activitypub"""
        if hasattr(self, "activitypub_wrapper"):
            return {self.activitypub_wrapper: value}
        return value

    # pylint: disable=unused-argument
    def field_from_activity(self, value, allow_external_connections=True, trigger=None):
        """formatter to convert activitypub into a model value"""
        if value and hasattr(self, "activitypub_wrapper"):
            value = value.get(self.activitypub_wrapper)
        return value

    def get_activitypub_field(self):
        """model_field_name to activitypubFieldName"""
        if self.activitypub_field:
            return self.activitypub_field
        name = self.name.rsplit(".", maxsplit=1)[-1]
        components = name.split("_")
        return components[0] + "".join(x.title() for x in components[1:])


class ActivitypubRelatedFieldMixin(ActivitypubFieldMixin):
    """default (de)serialization for foreign key and one to one"""

    def __init__(self, *args, load_remote=True, **kwargs):
        self.load_remote = load_remote
        super().__init__(*args, **kwargs)

    def field_from_activity(self, value, allow_external_connections=True, trigger=None):
        """trigger: the object that triggered this deserialization.
        For example the Edition for which self is the parent Work"""
        if not value:
            return None

        related_model = self.related_model
        if hasattr(value, "id") and value.id:
            if not self.load_remote:
                # only look in the local database
                return related_model.find_existing(value.serialize())
            # this is an activitypub object, which we can deserialize
            return value.to_model(model=related_model, trigger=trigger)
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
        return activitypub.resolve_remote_id(
            value,
            model=related_model,
            allow_external_connections=allow_external_connections,
        )


class RemoteIdField(ActivitypubFieldMixin, models.CharField):
    """a url that serves as a unique identifier"""

    def __init__(self, *args, max_length=255, validators=None, **kwargs):
        validators = validators or [validate_remote_id]
        super().__init__(*args, max_length=max_length, validators=validators, **kwargs)
        # for this field, the default is true. false everywhere else.
        self.deduplication_field = kwargs.get("deduplication_field", True)


class UsernameField(ActivitypubFieldMixin, models.CharField):
    """activitypub-aware username field"""

    def __init__(self, activitypub_field="preferredUsername", **kwargs):
        self.activitypub_field = activitypub_field
        super(ActivitypubFieldMixin, self).__init__(
            _("username"),
            max_length=150,
            unique=True,
            validators=[validate_username],
            error_messages={
                "unique": _("A user with that username already exists."),
            },
        )

    def deconstruct(self):
        """implementation of models.Field deconstruct"""
        name, path, args, kwargs = super().deconstruct()
        del kwargs["verbose_name"]
        del kwargs["max_length"]
        del kwargs["unique"]
        del kwargs["validators"]
        del kwargs["error_messages"]
        return name, path, args, kwargs

    def field_to_activity(self, value):
        return value.split("@")[0]


PrivacyLevels = [
    ("public", _("Public")),
    ("unlisted", _("Unlisted")),
    ("followers", _("Followers")),
    ("direct", _("Private")),
]


class PrivacyField(ActivitypubFieldMixin, models.CharField):
    """this maps to two different activitypub fields"""

    public = "https://www.w3.org/ns/activitystreams#Public"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, max_length=255, choices=PrivacyLevels, default="public")

    def set_field_from_activity(
        self, instance, data, overwrite=True, allow_external_connections=True
    ):
        if not overwrite:
            return False

        original = getattr(instance, self.name)
        to = data.to
        cc = data.cc

        # we need to figure out who this is to get their followers link
        for field in ["attributedTo", "owner", "actor"]:
            if hasattr(data, field):
                user_field = field
                break
        if not user_field:
            raise ValidationError("No user field found for privacy", data)
        user = activitypub.resolve_remote_id(
            getattr(data, user_field),
            model="User",
            allow_external_connections=allow_external_connections,
        )

        if to == [self.public]:
            setattr(instance, self.name, "public")
        elif self.public in cc:
            setattr(instance, self.name, "unlisted")
        elif to == [user.followers_url]:
            setattr(instance, self.name, "followers")
        elif cc == []:
            setattr(instance, self.name, "direct")
        else:
            setattr(instance, self.name, "followers")
        return original == getattr(instance, self.name)

    def set_activity_from_field(self, activity, instance):
        # explicitly to anyone mentioned (statuses only)
        mentions = []
        if hasattr(instance, "mention_users"):
            mentions = [u.remote_id for u in instance.mention_users.all()]
        # this is a link to the followers list
        followers = instance.user.followers_url
        if instance.privacy == "public":
            activity["to"] = [self.public]
            activity["cc"] = [followers] + mentions
        elif instance.privacy == "unlisted":
            activity["to"] = [followers]
            activity["cc"] = [self.public] + mentions
        elif instance.privacy == "followers":
            activity["to"] = [followers]
            activity["cc"] = mentions
        if instance.privacy == "direct":
            activity["to"] = mentions
            activity["cc"] = []


class ForeignKey(  # pylint: disable=abstract-method
    ActivitypubRelatedFieldMixin,
    models.ForeignKey,
):
    """activitypub-aware foreign key field"""

    def field_to_activity(self, value):
        if not value:
            return None
        return value.remote_id


class OneToOneField(  # pylint: disable=abstract-method
    ActivitypubRelatedFieldMixin, models.OneToOneField
):
    """activitypub-aware foreign key field"""

    def field_to_activity(self, value):
        if not value:
            return None
        return value.to_activity()


class ManyToManyField(  # pylint: disable=abstract-method
    ActivitypubFieldMixin, models.ManyToManyField
):
    """activitypub-aware many to many field"""

    def __init__(self, *args, link_only=False, **kwargs):
        self.link_only = link_only
        super().__init__(*args, **kwargs)

    def set_field_from_activity(
        self, instance, data, overwrite=True, allow_external_connections=True
    ):
        """helper function for assigning a value to the field"""
        if not overwrite and getattr(instance, self.name).exists():
            return False

        value = getattr(data, self.get_activitypub_field())
        formatted = self.field_from_activity(
            value, allow_external_connections=allow_external_connections
        )
        if formatted is None or formatted is MISSING:
            return False
        getattr(instance, self.name).set(formatted)
        instance.save(broadcast=False)
        return True

    def field_to_activity(self, value):
        if self.link_only:
            return f"{value.instance.remote_id}/{self.name}"
        return [i.remote_id for i in value.all()]

    def field_from_activity(self, value, allow_external_connections=True, trigger=None):
        if value is None or value is MISSING:
            return None
        if not isinstance(value, list):
            # If this is a link, we currently aren't doing anything with it
            return None
        items = []
        for remote_id in value:
            try:
                validate_remote_id(remote_id)
            except ValidationError:
                continue
            items.append(
                activitypub.resolve_remote_id(
                    remote_id,
                    model=self.related_model,
                    allow_external_connections=allow_external_connections,
                )
            )
        return items


class TagField(ManyToManyField):  # pylint: disable=abstract-method
    """special case of many to many that uses Tags"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.activitypub_field = "tag"

    def field_to_activity(self, value):
        tags = []
        for item in value.all():
            activity_type = item.__class__.__name__
            if activity_type == "User":
                activity_type = "Mention"

            if activity_type == "Hashtag":
                name = item.name
            else:
                name = f"@{getattr(item, item.name_field)}"

            tags.append(
                activitypub.Link(
                    href=item.remote_id,
                    name=name,
                    type=activity_type,
                )
            )
        return tags

    def field_from_activity(self, value, allow_external_connections=True, trigger=None):
        if not isinstance(value, list):
            # GoToSocial DMs and single-user mentions are
            # sent as objects, not as an array of objects
            if isinstance(value, dict):
                value = [value]
            else:
                return None
        items = []
        for link_json in value:
            link = activitypub.Link(**link_json)
            tag_type = link.type if link.type != "Mention" else "Person"
            if tag_type == "Book":
                tag_type = "Edition"
            if tag_type != self.related_model.activity_serializer.type:
                # tags can contain multiple types
                continue

            if tag_type == "Hashtag":
                # we already have all data to create hashtags,
                # no need to fetch from remote
                item = self.related_model.activity_serializer(**link_json)
                hashtag = item.to_model(model=self.related_model, save=True)
                items.append(hashtag)
            else:
                # for other tag types we fetch them remotely
                items.append(
                    activitypub.resolve_remote_id(
                        link.href,
                        model=self.related_model,
                        allow_external_connections=allow_external_connections,
                    )
                )
        return items


class ClearableFileInputWithWarning(ClearableFileInput):
    """max file size warning"""

    template_name = "widgets/clearable_file_input_with_warning.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["attrs"].update(
            {
                "data-max-upload": DATA_UPLOAD_MAX_MEMORY_SIZE,
                "max_mb": DATA_UPLOAD_MAX_MEMORY_SIZE >> 20,
            }
        )
        return context


class CustomImageField(DjangoImageField):
    """overwrites image field for form"""

    widget = ClearableFileInputWithWarning


class ImageField(ActivitypubFieldMixin, models.ImageField):
    """activitypub-aware image field"""

    def __init__(self, *args, alt_field=None, **kwargs):
        self.alt_field = alt_field
        super().__init__(*args, **kwargs)

    # pylint: disable=arguments-renamed,too-many-arguments
    def set_field_from_activity(
        self, instance, data, save=True, overwrite=True, allow_external_connections=True
    ):
        """helper function for assigning a value to the field"""
        value = getattr(data, self.get_activitypub_field())
        formatted = self.field_from_activity(
            value, allow_external_connections=allow_external_connections
        )
        if formatted is None or formatted is MISSING:
            return False

        if (
            not overwrite
            and hasattr(instance, self.name)
            and getattr(instance, self.name)
        ):
            return False

        getattr(instance, self.name).save(*formatted, save=save)
        return True

    def set_activity_from_field(self, activity, instance):
        value = getattr(instance, self.name)
        if value is None:
            return
        alt_text = getattr(instance, self.alt_field)
        formatted = self.field_to_activity(value, alt_text)

        key = self.get_activitypub_field()
        activity[key] = formatted

    def field_to_activity(self, value, alt=None):
        url = get_absolute_url(value)

        if not url:
            return None

        return activitypub.Image(url=url, name=alt)

    def field_from_activity(self, value, allow_external_connections=True, trigger=None):
        image_slug = value
        # when it's an inline image (User avatar/icon, Book cover), it's a json
        # blob, but when it's an attached image, it's just a url
        if isinstance(image_slug, str):
            url = image_slug
        elif isinstance(image_slug, dict):
            url = image_slug.get("url")
        elif hasattr(image_slug, "url"):  # Serialized to Image/Document object?
            url = image_slug.url
        else:
            return None

        try:
            validate_remote_id(url)
        except ValidationError:
            return None

        image_content, extension = get_image(url)
        if not image_content:
            return None

        image_name = f"{uuid4()}.{extension}"
        return [image_name, image_content]

    def formfield(self, **kwargs):
        """special case for forms"""
        return super().formfield(
            **{
                "form_class": CustomImageField,
                **kwargs,
            }
        )


def get_absolute_url(value):
    """returns an absolute URL for the image"""
    name = getattr(value, "name")
    if not name:
        return None

    url = filepath_to_uri(name)
    if url is not None:
        url = url.lstrip("/")
    url = urljoin(MEDIA_FULL_URL, url)

    return url


class DateTimeField(ActivitypubFieldMixin, models.DateTimeField):
    """activitypub-aware datetime field"""

    def field_to_activity(self, value):
        if not value:
            return None
        return value.isoformat()

    def field_from_activity(self, value, allow_external_connections=True, trigger=None):
        missing_fields = datetime(1970, 1, 1)  # "2022-10" => "2022-10-01"
        try:
            date_value = dateutil.parser.parse(value, default=missing_fields)
            try:
                return timezone.make_aware(date_value)
            except ValueError:
                return date_value
        except (ParserError, TypeError):
            return None


class PartialDateField(ActivitypubFieldMixin, PartialDateModel):
    """activitypub-aware partial date field"""

    def field_to_activity(self, value) -> str:
        return value.partial_isoformat() if value else None

    def field_from_activity(self, value, allow_external_connections=True, trigger=None):
        # pylint: disable=no-else-return
        try:
            return from_partial_isoformat(value)
        except ValueError:
            pass

        # fallback to full ISO-8601 parsing
        try:
            parsed = dateutil.parser.isoparse(value)
        except (ValueError, ParserError):
            return None

        if timezone.is_aware(parsed):
            return PartialDate.from_datetime(parsed)
        else:
            # Should not happen on the wire, but truncate down to date parts.
            return PartialDate.from_date_parts(parsed.year, parsed.month, parsed.day)

        # FIXME: decide whether to fix timestamps like "2023-09-30T21:00:00-03":
        # clearly Oct 1st, not Sep 30th (an unwanted side-effect of USE_TZ). It's
        # basically the remnants of #3028; there is a data migration pending (see …)
        # but over the wire we might get these for an indeterminate amount of time.


class HtmlField(ActivitypubFieldMixin, models.TextField):
    """a text field for storing html"""

    def field_from_activity(self, value, allow_external_connections=True, trigger=None):
        if not value or value == MISSING:
            return None
        return clean(value)

    def field_to_activity(self, value):
        return markdown(value) if value else value


class ArrayField(ActivitypubFieldMixin, DjangoArrayField):
    """activitypub-aware array field"""

    def field_to_activity(self, value):
        return [str(i) for i in value]


class CharField(ActivitypubFieldMixin, models.CharField):
    """activitypub-aware char field"""


class CICharField(ActivitypubFieldMixin, DjangoCICharField):
    """activitypub-aware cichar field"""


class URLField(ActivitypubFieldMixin, models.URLField):
    """activitypub-aware url field"""


class TextField(ActivitypubFieldMixin, models.TextField):
    """activitypub-aware text field"""


class BooleanField(ActivitypubFieldMixin, models.BooleanField):
    """activitypub-aware boolean field"""


class IntegerField(ActivitypubFieldMixin, models.IntegerField):
    """activitypub-aware boolean field"""


class DecimalField(ActivitypubFieldMixin, models.DecimalField):
    """activitypub-aware boolean field"""

    def field_to_activity(self, value):
        if not value:
            return None
        return float(value)
