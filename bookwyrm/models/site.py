''' the particulars for this instance of BookWyrm '''
import base64
import datetime

from Crypto import Random
from django.db import models
from django.utils import timezone

from bookwyrm.settings import DOMAIN
from .user import User

class SiteSettings(models.Model):
    ''' customized settings for this instance '''
    name = models.CharField(default='BookWyrm', max_length=100)
    instance_description = models.TextField(
        default="This instance has no description.")
    code_of_conduct = models.TextField(
        default="Add a code of conduct here.")
    allow_registration = models.BooleanField(default=True)
    support_link = models.CharField(max_length=255, null=True, blank=True)
    support_title = models.CharField(max_length=100, null=True, blank=True)
    admin_email = models.EmailField(max_length=255, null=True, blank=True)

    @classmethod
    def get(cls):
        ''' gets the site settings db entry or defaults '''
        try:
            return cls.objects.get(id=1)
        except cls.DoesNotExist:
            default_settings = SiteSettings(id=1)
            default_settings.save()
            return default_settings

def new_access_code():
    ''' the identifier for a user invite '''
    return base64.b32encode(Random.get_random_bytes(5)).decode('ascii')

class SiteInvite(models.Model):
    ''' gives someone access to create an account on the instance '''
    code = models.CharField(max_length=32, default=new_access_code)
    expiry = models.DateTimeField(blank=True, null=True)
    use_limit = models.IntegerField(blank=True, null=True)
    times_used = models.IntegerField(default=0)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def valid(self):
        ''' make sure it hasn't expired or been used '''
        return (
            (self.expiry is None or self.expiry > timezone.now()) and
            (self.use_limit is None or self.times_used < self.use_limit))

    @property
    def link(self):
        ''' formats the invite link '''
        return "https://{}/invite/{}".format(DOMAIN, self.code)


def get_passowrd_reset_expiry():
    ''' give people a limited time to use the link '''
    now = timezone.now()
    return now + datetime.timedelta(days=1)


class PasswordReset(models.Model):
    ''' gives someone access to create an account on the instance '''
    code = models.CharField(max_length=32, default=new_access_code)
    expiry = models.DateTimeField(default=get_passowrd_reset_expiry)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def valid(self):
        ''' make sure it hasn't expired or been used '''
        return self.expiry > timezone.now()

    @property
    def link(self):
        ''' formats the invite link '''
        return "https://{}/password-reset/{}".format(DOMAIN, self.code)
