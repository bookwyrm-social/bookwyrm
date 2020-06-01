from django.db import models
from fedireads.settings import DOMAIN

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
