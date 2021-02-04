''' activitypub objects like Person and Book'''
from base64 import b64encode
from uuid import uuid4

from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from django.apps import apps

from bookwyrm import activitypub
from . import ActivitypubMixin


class ObjectMixin(ActivitypubMixin):
    ''' add this mixin for object models that are AP serializable '''

    def save(self, *args, **kwargs):
        ''' broadcast updated '''
        # first off, we want to save normally no matter what
        super().save(*args, **kwargs)

        # we only want to handle updates, not newly created objects
        if not self.id:
            return

        # this will work for lists, shelves
        user = self.user if hasattr(self, 'user') else None
        if not user:
            # users don't have associated users, they ARE users
            user_model = apps.get_model('bookwyrm.User', require_ready=True)
            if isinstance(self, user_model):
                user = self
            # book data tracks last editor
            elif hasattr(self, 'last_edited_by'):
                user = self.last_edited_by
        # again, if we don't know the user or they're remote, don't bother
        if not user or not user.local:
            return

        # is this a deletion?
        if self.deleted:
            activity = self.to_delete_activity(user)
        else:
            activity = self.to_update_activity(user)
        self.broadcast(activity, user)


    def to_create_activity(self, user, **kwargs):
        ''' returns the object wrapped in a Create activity '''
        activity_object = self.to_activity(**kwargs)

        signature = None
        create_id = self.remote_id + '/activity'
        if 'content' in activity_object:
            signer = pkcs1_15.new(RSA.import_key(user.key_pair.private_key))
            content = activity_object['content']
            signed_message = signer.sign(SHA256.new(content.encode('utf8')))

            signature = activitypub.Signature(
                creator='%s#main-key' % user.remote_id,
                created=activity_object['published'],
                signatureValue=b64encode(signed_message).decode('utf8')
            )

        return activitypub.Create(
            id=create_id,
            actor=user.remote_id,
            to=activity_object['to'],
            cc=activity_object['cc'],
            object=activity_object,
            signature=signature,
        ).serialize()


    def to_delete_activity(self, user):
        ''' notice of deletion '''
        return activitypub.Delete(
            id=self.remote_id + '/activity',
            actor=user.remote_id,
            to=['%s/followers' % user.remote_id],
            cc=['https://www.w3.org/ns/activitystreams#Public'],
            object=self.to_activity(),
        ).serialize()


    def to_update_activity(self, user):
        ''' wrapper for Updates to an activity '''
        activity_id = '%s#update/%s' % (self.remote_id, uuid4())
        return activitypub.Update(
            id=activity_id,
            actor=user.remote_id,
            to=['https://www.w3.org/ns/activitystreams#Public'],
            object=self.to_activity()
        ).serialize()
