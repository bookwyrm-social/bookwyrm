""" base model with default fields """
import base64
from Crypto import Random

from django.core.exceptions import PermissionDenied
from django.db import models
from django.dispatch import receiver
from django.http import Http404
from django.utils.translation import gettext_lazy as _

from bookwyrm.settings import DOMAIN
from .fields import RemoteIdField


DeactivationReason = [
    ("pending", _("Pending")),
    ("self_deletion", _("Self deletion")),
    ("moderator_suspension", _("Moderator suspension")),
    ("moderator_deletion", _("Moderator deletion")),
    ("domain_block", _("Domain block")),
]


def new_access_code():
    """the identifier for a user invite"""
    return base64.b32encode(Random.get_random_bytes(5)).decode("ascii")


class BookWyrmModel(models.Model):
    """shared fields"""

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    remote_id = RemoteIdField(null=True, activitypub_field="id")

    def get_remote_id(self):
        """generate a url that resolves to the local object"""
        base_path = f"https://{DOMAIN}"
        if hasattr(self, "user"):
            base_path = f"{base_path}{self.user.local_path}"
        model_name = type(self).__name__.lower()
        return f"{base_path}/{model_name}/{self.id}"

    class Meta:
        """this is just here to provide default fields for other models"""

        abstract = True

    @property
    def local_path(self):
        """how to link to this object in the local app"""
        return self.get_remote_id().replace(f"https://{DOMAIN}", "")

    def raise_visible_to_user(self, viewer):
        """is a user authorized to view an object?"""
        # make sure this is an object with privacy owned by a user
        if not hasattr(self, "user") or not hasattr(self, "privacy"):
            return

        # viewer can't see it if the object's owner blocked them
        if viewer in self.user.blocks.all():
            raise Http404()

        # you can see your own posts and any public or unlisted posts
        if viewer == self.user or self.privacy in ["public", "unlisted"]:
            return

        # you can see the followers only posts of people you follow
        if (
            self.privacy == "followers"
            and self.user.followers.filter(id=viewer.id).first()
        ):
            return

        # you can see dms you are tagged in
        if hasattr(self, "mention_users"):
            if (
                self.privacy == "direct"
                and self.mention_users.filter(id=viewer.id).first()
            ):
                return
        raise Http404()

    def raise_not_editable(self, viewer):
        """does this user have permission to edit this object? liable to be overwritten
        by models that inherit this base model class"""
        if not hasattr(self, "user"):
            return

        # generally moderators shouldn't be able to edit other people's stuff
        if self.user == viewer:
            return

        raise PermissionDenied()

    def raise_not_deletable(self, viewer):
        """does this user have permission to delete this object? liable to be
        overwritten by models that inherit this base model class"""
        if not hasattr(self, "user"):
            return

        # but generally moderators can delete other people's stuff
        if self.user == viewer or viewer.has_perm("moderate_post"):
            return

        raise PermissionDenied()


@receiver(models.signals.post_save)
# pylint: disable=unused-argument
def set_remote_id(sender, instance, created, *args, **kwargs):
    """set the remote_id after save (when the id is available)"""
    if not created or not hasattr(instance, "get_remote_id"):
        return
    if not instance.remote_id:
        instance.remote_id = instance.get_remote_id()
        try:
            instance.save(broadcast=False)
        except TypeError:
            instance.save()
