import base64

from Crypto import Random
from django.db import models
from django.utils import timezone
import datetime

from fedireads.settings import DOMAIN
from .user import User

class SiteSettings(models.Model):
    name = models.CharField(default=DOMAIN, max_length=100)
    instance_description = models.TextField(
        default="This instance has no description.")
    code_of_conduct = models.TextField(
        default="Add a code of conduct here.")
    allow_registration = models.BooleanField(default=True)

    @classmethod
    def get(cls):
        try:
            return cls.objects.get(id=1)
        except cls.DoesNotExist:
            default_settings = SiteSettings(id=1)
            default_settings.save()
            return default_settings

def new_invite_code():
    return base64.b32encode(Random.get_random_bytes(5)).decode('ascii')

class SiteInvite(models.Model):
    code = models.CharField(max_length=32, default=new_invite_code)
    expiry = models.DateTimeField(blank=True, null=True)
    use_limit = models.IntegerField(blank=True, null=True)
    times_used = models.IntegerField(default=0)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def valid(self):
        return (
            (self.expiry is None or self.expiry > timezone.now()) and
            (self.use_limit is None or self.times_used < self.use_limit))

    @property
    def link(self):
        return "https://{}/invite/{}".format(DOMAIN, self.code)

    def valid(self):
        return (
            (self.expiry is None or self.expiry > datetime.datetime.now()) and
            (self.use_limit is None or self.times_used < self.use_limit))
