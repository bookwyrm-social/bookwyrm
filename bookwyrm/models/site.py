""" the particulars for this instance of BookWyrm """
import datetime
from urllib.parse import urljoin
import uuid

from django.db import models, IntegrityError
from django.dispatch import receiver
from django.utils import timezone
from model_utils import FieldTracker

from bookwyrm.preview_images import generate_site_preview_image_task
from bookwyrm.settings import DOMAIN, ENABLE_PREVIEW_IMAGES, STATIC_FULL_URL
from .base_model import BookWyrmModel, new_access_code
from .user import User
from .fields import get_absolute_url


class SiteSettings(models.Model):
    """customized settings for this instance"""

    name = models.CharField(default="BookWyrm", max_length=100)
    instance_tagline = models.CharField(
        max_length=150, default="Social Reading and Reviewing"
    )
    instance_description = models.TextField(default="This instance has no description.")
    instance_short_description = models.CharField(max_length=255, blank=True, null=True)
    default_theme = models.ForeignKey(
        "Theme", null=True, blank=True, on_delete=models.SET_NULL
    )
    version = models.CharField(null=True, blank=True, max_length=10)

    # admin setup options
    install_mode = models.BooleanField(default=False)
    admin_code = models.CharField(max_length=50, default=uuid.uuid4)

    # about page
    registration_closed_text = models.TextField(
        default="We aren't taking new users at this time. You can find an open "
        'instance at <a href="https://joinbookwyrm.com/instances">'
        "joinbookwyrm.com/instances</a>."
    )
    invite_request_text = models.TextField(
        default="If your request is approved, you will receive an email with a "
        "registration link."
    )
    code_of_conduct = models.TextField(default="Add a code of conduct here.")
    privacy_policy = models.TextField(default="Add a privacy policy here.")

    # registration
    allow_registration = models.BooleanField(default=False)
    allow_invite_requests = models.BooleanField(default=True)
    invite_request_question = models.BooleanField(default=False)
    require_confirm_email = models.BooleanField(default=True)

    invite_question_text = models.CharField(
        max_length=255, blank=True, default="What is your favourite book?"
    )
    # images
    logo = models.ImageField(upload_to="logos/", null=True, blank=True)
    logo_small = models.ImageField(upload_to="logos/", null=True, blank=True)
    favicon = models.ImageField(upload_to="logos/", null=True, blank=True)
    preview_image = models.ImageField(
        upload_to="previews/logos/", null=True, blank=True
    )

    # footer
    support_link = models.CharField(max_length=255, null=True, blank=True)
    support_title = models.CharField(max_length=100, null=True, blank=True)
    admin_email = models.EmailField(max_length=255, null=True, blank=True)
    footer_item = models.TextField(null=True, blank=True)

    field_tracker = FieldTracker(fields=["name", "instance_tagline", "logo"])

    @classmethod
    def get(cls):
        """gets the site settings db entry or defaults"""
        try:
            return cls.objects.get(id=1)
        except cls.DoesNotExist:
            default_settings = SiteSettings(id=1)
            default_settings.save()
            return default_settings

    @property
    def logo_url(self):
        """helper to build the logo url"""
        return self.get_url("logo", "images/logo.png")

    @property
    def logo_small_url(self):
        """helper to build the logo url"""
        return self.get_url("logo_small", "images/logo-small.png")

    @property
    def favicon_url(self):
        """helper to build the logo url"""
        return self.get_url("favicon", "images/favicon.png")

    def get_url(self, field, default_path):
        """get a media url or a default static path"""
        uploaded = getattr(self, field, None)
        if uploaded:
            return get_absolute_url(uploaded)
        return urljoin(STATIC_FULL_URL, default_path)

    def save(self, *args, **kwargs):
        """if require_confirm_email is disabled, make sure no users are pending,
        if enabled, make sure invite_question_text is not empty"""
        if not self.require_confirm_email:
            User.objects.filter(is_active=False, deactivation_reason="pending").update(
                is_active=True, deactivation_reason=None
            )
        if not self.invite_question_text:
            self.invite_question_text = "What is your favourite book?"
        super().save(*args, **kwargs)


class Theme(models.Model):
    """Theme files"""

    created_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=50, unique=True)
    path = models.CharField(max_length=50, unique=True)

    def __str__(self):
        # pylint: disable=invalid-str-returned
        return self.name


class SiteInvite(models.Model):
    """gives someone access to create an account on the instance"""

    created_date = models.DateTimeField(auto_now_add=True)
    code = models.CharField(max_length=32, default=new_access_code)
    expiry = models.DateTimeField(blank=True, null=True)
    use_limit = models.IntegerField(blank=True, null=True)
    times_used = models.IntegerField(default=0)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    invitees = models.ManyToManyField(User, related_name="invitees")

    def valid(self):
        """make sure it hasn't expired or been used"""
        return (self.expiry is None or self.expiry > timezone.now()) and (
            self.use_limit is None or self.times_used < self.use_limit
        )

    @property
    def link(self):
        """formats the invite link"""
        return f"https://{DOMAIN}/invite/{self.code}"


class InviteRequest(BookWyrmModel):
    """prospective users can request an invite"""

    email = models.EmailField(max_length=255, unique=True)
    invite = models.ForeignKey(
        SiteInvite, on_delete=models.SET_NULL, null=True, blank=True
    )
    answer = models.TextField(max_length=50, unique=False, null=True, blank=True)
    invite_sent = models.BooleanField(default=False)
    ignored = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """don't create a request for a registered email"""
        if not self.id and User.objects.filter(email=self.email).exists():
            raise IntegrityError()
        super().save(*args, **kwargs)


def get_passowrd_reset_expiry():
    """give people a limited time to use the link"""
    now = timezone.now()
    return now + datetime.timedelta(days=1)


class PasswordReset(models.Model):
    """gives someone access to create an account on the instance"""

    code = models.CharField(max_length=32, default=new_access_code)
    expiry = models.DateTimeField(default=get_passowrd_reset_expiry)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def valid(self):
        """make sure it hasn't expired or been used"""
        return self.expiry > timezone.now()

    @property
    def link(self):
        """formats the invite link"""
        return f"https://{DOMAIN}/password-reset/{self.code}"


# pylint: disable=unused-argument
@receiver(models.signals.post_save, sender=SiteSettings)
def preview_image(instance, *args, **kwargs):
    """Update image preview for the default site image"""
    if not ENABLE_PREVIEW_IMAGES:
        return
    changed_fields = instance.field_tracker.changed()

    if len(changed_fields) > 0:
        generate_site_preview_image_task.delay()
