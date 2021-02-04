''' activitypub model functionality '''
from bookwyrm import activitypub
from . import ActivitypubMixin

class ActivitybMixin(ActivitypubMixin):
    ''' add this mixin for models that are AP serializable '''

    def save(self, *args, **kwargs):
        ''' broadcast activity '''
        super().save(*args, **kwargs)
        self.broadcast(self.to_activity(), self.user)

    def delete(self, *args, **kwargs):
        ''' nevermind, undo that activity '''
        self.broadcast(self.to_undo_activity(), self.user)
        super().delete(*args, **kwargs)


    def to_undo_activity(self):
        ''' undo an action '''
        return activitypub.Undo(
            id='%s#undo' % self.remote_id,
            actor=self.user.remote_id,
            object=self.to_activity()
        ).serialize()
