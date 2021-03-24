""" base model with default fields """
from django.db import models
from django.dispatch import receiver

from bookwyrm.settings import DOMAIN
from .fields import RemoteIdField


class BookWyrmModel(models.Model):
    """ shared fields """

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    remote_id = RemoteIdField(null=True, activitypub_field="id")

    def get_remote_id(self):
        """ generate a url that resolves to the local object """
        base_path = "https://%s" % DOMAIN
        if hasattr(self, "user"):
            base_path = "%s%s" % (base_path, self.user.local_path)
        model_name = type(self).__name__.lower()
        return "%s/%s/%d" % (base_path, model_name, self.id)

    class Meta:
        """ this is just here to provide default fields for other models """

        abstract = True

    @property
    def local_path(self):
        """ how to link to this object in the local app """
        return self.get_remote_id().replace("https://%s" % DOMAIN, "")


@receiver(models.signals.post_save)
# pylint: disable=unused-argument
def set_remote_id(sender, instance, created, *args, **kwargs):
    """ set the remote_id after save (when the id is available) """
    if not created or not hasattr(instance, "get_remote_id"):
        return
    if not instance.remote_id:
        instance.remote_id = instance.get_remote_id()
        try:
            instance.save(broadcast=False)
        except TypeError:
            instance.save()
