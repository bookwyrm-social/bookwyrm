''' defines relationships between users '''
from django.db import models

from bookwyrm import activitypub
from .base_model import BookWyrmModel


class UserRelationship(BookWyrmModel):
    ''' many-to-many through table for followers '''
    user_subject = models.ForeignKey(
        'User',
        on_delete=models.PROTECT,
        related_name='%(class)s_user_subject'
    )
    user_object = models.ForeignKey(
        'User',
        on_delete=models.PROTECT,
        related_name='%(class)s_user_object'
    )
    # follow or follow_request for pending TODO: blocking?
    relationship_id = models.CharField(max_length=100)

    class Meta:
        ''' relationships should be unique '''
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=['user_subject', 'user_object'],
                name='%(class)s_unique'
            ),
            models.CheckConstraint(
                check=~models.Q(user_subject=models.F('user_object')),
                name='%(class)s_no_self'
            )
        ]

    def get_remote_id(self):
        ''' use shelf identifier in remote_id '''
        base_path = self.user_subject.remote_id
        return '%s#%s/%d' % (base_path, self.status, self.id)


class UserFollows(UserRelationship):
    ''' Following a user '''
    status = 'follows'

    @classmethod
    def from_request(cls, follow_request):
        ''' converts a follow request into a follow relationship '''
        return cls(
            user_subject=follow_request.user_subject,
            user_object=follow_request.user_object,
            relationship_id=follow_request.relationship_id,
        )


class UserFollowRequest(UserRelationship):
    ''' following a user requires manual or automatic confirmation '''
    status = 'follow_request'

    def to_activity(self):
        ''' request activity '''
        return activitypub.Follow(
            id=self.remote_id,
            actor=self.user_subject.remote_id,
            object=self.user_object.remote_id,
        ).serialize()

    def to_accept_activity(self):
        ''' generate an Accept for this follow request '''
        return activitypub.Accept(
            id='%s#accepts/follows/' % self.remote_id,
            actor=self.user_subject.remote_id,
            object=self.user_object.remote_id,
        ).serialize()

    def to_reject_activity(self):
        ''' generate an Accept for this follow request '''
        return activitypub.Reject(
            id='%s#rejects/follows/' % self.remote_id,
            actor=self.user_subject.remote_id,
            object=self.user_object.remote_id,
        ).serialize()


class UserBlocks(UserRelationship):
    ''' prevent another user from following you and seeing your posts '''
    # TODO: not implemented
    status = 'blocks'
