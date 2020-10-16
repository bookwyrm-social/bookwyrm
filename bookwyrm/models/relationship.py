''' defines relationships between users '''
from django.db import models

from bookwyrm import activitypub
from .base_model import ActivitypubMixin, ActivityMapping, BookWyrmModel


class UserRelationship(ActivitypubMixin, BookWyrmModel):
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

    activity_mappings = [
        ActivityMapping('id', 'remote_id'),
        ActivityMapping('actor', 'user_subject'),
        ActivityMapping('object', 'user_object'),
    ]
    activity_serializer = activitypub.Follow

    def get_remote_id(self, status=None):
        ''' use shelf identifier in remote_id '''
        status = status or 'follows'
        base_path = self.user_subject.remote_id
        return '%s#%s/%d' % (base_path, status, self.id)


    def to_accept_activity(self):
        ''' generate an Accept for this follow request '''
        return activitypub.Accept(
            id=self.get_remote_id(status='accepts'),
            actor=self.user_object.remote_id,
            object=self.to_activity()
        ).serialize()


    def to_reject_activity(self):
        ''' generate an Accept for this follow request '''
        return activitypub.Reject(
            id=self.get_remote_id(status='rejects'),
            actor=self.user_object.remote_id,
            object=self.to_activity()
        ).serialize()


class UserFollows(UserRelationship):
    ''' Following a user '''
    status = 'follows'

    @classmethod
    def from_request(cls, follow_request):
        ''' converts a follow request into a follow relationship '''
        return cls(
            user_subject=follow_request.user_subject,
            user_object=follow_request.user_object,
            remote_id=follow_request.remote_id,
        )


class UserFollowRequest(UserRelationship):
    ''' following a user requires manual or automatic confirmation '''
    status = 'follow_request'


class UserBlocks(UserRelationship):
    ''' prevent another user from following you and seeing your posts '''
    # TODO: not implemented
    status = 'blocks'
