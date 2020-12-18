''' test incoming activities '''
from datetime import datetime
import json
import pathlib
from unittest.mock import patch

from django.http import HttpResponseBadRequest, HttpResponseNotAllowed, \
        HttpResponseNotFound
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, incoming


#pylint: disable=too-many-public-methods
class Incoming(TestCase):
    ''' a lot here: all handlers for receiving activitypub requests '''
    def setUp(self):
        ''' we need basic things, like users '''
        self.local_user = models.User.objects.create_user(
            'mouse', 'mouse@mouse.com', 'mouseword', local=True)
        self.local_user.remote_id = 'https://example.com/user/mouse'
        self.local_user.save()
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            self.remote_user = models.User.objects.create_user(
                'rat', 'rat@rat.com', 'ratword',
                local=False,
                remote_id='https://example.com/users/rat',
                inbox='https://example.com/users/rat/inbox',
                outbox='https://example.com/users/rat/outbox',
            )
        self.status = models.Status.objects.create(
            user=self.local_user,
            content='Test status',
            remote_id='https://example.com/status/1',
        )
        self.factory = RequestFactory()


    def test_inbox_invalid_get(self):
        ''' shouldn't try to handle if the user is not found '''
        request = self.factory.get('https://www.example.com/')
        self.assertIsInstance(
            incoming.inbox(request, 'anything'), HttpResponseNotAllowed)
        self.assertIsInstance(
            incoming.shared_inbox(request), HttpResponseNotAllowed)

    def test_inbox_invalid_user(self):
        ''' shouldn't try to handle if the user is not found '''
        request = self.factory.post('https://www.example.com/')
        self.assertIsInstance(
            incoming.inbox(request, 'fish@tomato.com'), HttpResponseNotFound)

    def test_inbox_invalid_no_object(self):
        ''' json is missing "object" field '''
        request = self.factory.post(
            self.local_user.shared_inbox, data={})
        self.assertIsInstance(
            incoming.shared_inbox(request), HttpResponseBadRequest)

    def test_inbox_invalid_bad_signature(self):
        ''' bad request for invalid signature '''
        request = self.factory.post(
            self.local_user.shared_inbox,
            '{"type": "Test", "object": "exists"}',
            content_type='application/json')
        with patch('bookwyrm.incoming.has_valid_signature') as mock_has_valid:
            mock_has_valid.return_value = False
            self.assertEqual(
                incoming.shared_inbox(request).status_code, 401)

    def test_inbox_invalid_bad_signature_delete(self):
        ''' invalid signature for Delete is okay though '''
        request = self.factory.post(
            self.local_user.shared_inbox,
            '{"type": "Delete", "object": "exists"}',
            content_type='application/json')
        with patch('bookwyrm.incoming.has_valid_signature') as mock_has_valid:
            mock_has_valid.return_value = False
            self.assertEqual(
                incoming.shared_inbox(request).status_code, 200)

    def test_inbox_unknown_type(self):
        ''' never heard of that activity type, don't have a handler for it '''
        request = self.factory.post(
            self.local_user.shared_inbox,
            '{"type": "Fish", "object": "exists"}',
            content_type='application/json')
        with patch('bookwyrm.incoming.has_valid_signature') as mock_has_valid:
            mock_has_valid.return_value = True
            self.assertIsInstance(
                incoming.shared_inbox(request), HttpResponseNotFound)

    def test_inbox_success(self):
        ''' a known type, for which we start a task '''
        request = self.factory.post(
            self.local_user.shared_inbox,
            '{"type": "Accept", "object": "exists"}',
            content_type='application/json')
        with patch('bookwyrm.incoming.has_valid_signature') as mock_has_valid:
            mock_has_valid.return_value = True

            with patch('bookwyrm.incoming.handle_follow_accept.delay'):
                self.assertEqual(
                    incoming.shared_inbox(request).status_code, 200)


    def test_handle_follow(self):
        ''' remote user wants to follow local user '''
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123",
            "type": "Follow",
            "actor": "https://example.com/users/rat",
            "object": "https://example.com/user/mouse"
        }

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            incoming.handle_follow(activity)

        # notification created
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.notification_type, 'FOLLOW')

        # the request should have been deleted
        requests = models.UserFollowRequest.objects.all()
        self.assertEqual(list(requests), [])

        # the follow relationship should exist
        follow = models.UserFollows.objects.get(user_object=self.local_user)
        self.assertEqual(follow.user_subject, self.remote_user)


    def test_handle_follow_manually_approved(self):
        ''' needs approval before following '''
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123",
            "type": "Follow",
            "actor": "https://example.com/users/rat",
            "object": "https://example.com/user/mouse"
        }

        self.local_user.manually_approves_followers = True
        self.local_user.save()

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            incoming.handle_follow(activity)

        # notification created
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.notification_type, 'FOLLOW_REQUEST')

        # the request should exist
        request = models.UserFollowRequest.objects.get()
        self.assertEqual(request.user_subject, self.remote_user)
        self.assertEqual(request.user_object, self.local_user)

        # the follow relationship should not exist
        follow = models.UserFollows.objects.all()
        self.assertEqual(list(follow), [])


    def test_handle_unfollow(self):
        ''' remove a relationship '''
        activity = {
            "type": "Undo",
            "@context": "https://www.w3.org/ns/activitystreams",
            "object": {
                "id": "https://example.com/users/rat/follows/123",
                "type": "Follow",
                "actor": "https://example.com/users/rat",
                "object": "https://example.com/user/mouse"
            }
        }
        models.UserFollows.objects.create(
            user_subject=self.remote_user, user_object=self.local_user)
        self.assertEqual(self.remote_user, self.local_user.followers.first())

        incoming.handle_unfollow(activity)
        self.assertIsNone(self.local_user.followers.first())


    def test_handle_follow_accept(self):
        ''' a remote user approved a follow request from local '''
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123#accepts",
            "type": "Accept",
            "actor": "https://example.com/users/rat",
            "object": {
                "id": "https://example.com/users/rat/follows/123",
                "type": "Follow",
                "actor": "https://example.com/user/mouse",
                "object": "https://example.com/users/rat"
            }
        }

        models.UserFollowRequest.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user
        )
        self.assertEqual(models.UserFollowRequest.objects.count(), 1)

        incoming.handle_follow_accept(activity)

        # request should be deleted
        self.assertEqual(models.UserFollowRequest.objects.count(), 0)

        # relationship should be created
        follows = self.remote_user.followers
        self.assertEqual(follows.count(), 1)
        self.assertEqual(follows.first(), self.local_user)


    def test_handle_follow_reject(self):
        ''' turn down a follow request '''
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": "https://example.com/users/rat/follows/123#accepts",
            "type": "Reject",
            "actor": "https://example.com/users/rat",
            "object": {
                "id": "https://example.com/users/rat/follows/123",
                "type": "Follow",
                "actor": "https://example.com/user/mouse",
                "object": "https://example.com/users/rat"
            }
        }

        models.UserFollowRequest.objects.create(
            user_subject=self.local_user,
            user_object=self.remote_user
        )
        self.assertEqual(models.UserFollowRequest.objects.count(), 1)

        incoming.handle_follow_reject(activity)

        # request should be deleted
        self.assertEqual(models.UserFollowRequest.objects.count(), 0)

        # relationship should be created
        follows = self.remote_user.followers
        self.assertEqual(follows.count(), 0)


    def test_handle_create(self):
        ''' the "it justs works" mode '''
        self.assertEqual(models.Status.objects.count(), 1)

        datafile = pathlib.Path(__file__).parent.joinpath(
            'data/ap_quotation.json')
        status_data = json.loads(datafile.read_bytes())
        models.Edition.objects.create(
            title='Test Book', remote_id='https://example.com/book/1')
        activity = {'object': status_data, 'type': 'Create'}

        incoming.handle_create(activity)

        status = models.Quotation.objects.get()
        self.assertEqual(
            status.remote_id, 'https://example.com/user/mouse/quotation/13')
        self.assertEqual(status.quote, 'quote body')
        self.assertEqual(status.content, 'commentary')
        self.assertEqual(status.user, self.local_user)
        self.assertEqual(models.Status.objects.count(), 2)

        # while we're here, lets ensure we avoid dupes
        incoming.handle_create(activity)
        self.assertEqual(models.Status.objects.count(), 2)

    def test_handle_create_remote_note_with_mention(self):
        ''' should only create it under the right circumstances '''
        self.assertEqual(models.Status.objects.count(), 1)
        self.assertFalse(
            models.Notification.objects.filter(user=self.local_user).exists())

        datafile = pathlib.Path(__file__).parent.joinpath(
            'data/ap_note.json')
        status_data = json.loads(datafile.read_bytes())
        activity = {'object': status_data, 'type': 'Create'}

        incoming.handle_create(activity)
        status = models.Status.objects.last()
        self.assertEqual(status.content, 'test content in note')
        self.assertEqual(status.mention_users.first(), self.local_user)
        self.assertTrue(
            models.Notification.objects.filter(user=self.local_user).exists())
        self.assertEqual(
            models.Notification.objects.get().notification_type, 'MENTION')

    def test_handle_create_remote_note_with_reply(self):
        ''' should only create it under the right circumstances '''
        self.assertEqual(models.Status.objects.count(), 1)
        self.assertFalse(
            models.Notification.objects.filter(user=self.local_user))

        datafile = pathlib.Path(__file__).parent.joinpath(
            'data/ap_note.json')
        status_data = json.loads(datafile.read_bytes())
        del status_data['tag']
        status_data['inReplyTo'] = self.status.remote_id
        activity = {'object': status_data, 'type': 'Create'}

        incoming.handle_create(activity)
        status = models.Status.objects.last()
        self.assertEqual(status.content, 'test content in note')
        self.assertEqual(status.reply_parent, self.status)
        self.assertTrue(
            models.Notification.objects.filter(user=self.local_user))
        self.assertEqual(
            models.Notification.objects.get().notification_type, 'REPLY')


    def test_handle_delete_status(self):
        ''' remove a status '''
        self.assertFalse(self.status.deleted)
        activity = {
            'type': 'Delete',
            'id': '%s/activity' % self.status.remote_id,
            'actor': self.local_user.remote_id,
            'object': {'id': self.status.remote_id},
        }
        incoming.handle_delete_status(activity)
        # deletion doens't remove the status, it turns it into a tombstone
        status = models.Status.objects.get()
        self.assertTrue(status.deleted)
        self.assertIsInstance(status.deleted_date, datetime)


    def test_handle_delete_status_notifications(self):
        ''' remove a status with related notifications '''
        models.Notification.objects.create(
            related_status=self.status,
            user=self.local_user,
            notification_type='MENTION'
        )
        # this one is innocent, don't delete it
        notif = models.Notification.objects.create(
            user=self.local_user,
            notification_type='MENTION'
        )
        self.assertFalse(self.status.deleted)
        self.assertEqual(models.Notification.objects.count(), 2)
        activity = {
            'type': 'Delete',
            'id': '%s/activity' % self.status.remote_id,
            'actor': self.local_user.remote_id,
            'object': {'id': self.status.remote_id},
        }
        incoming.handle_delete_status(activity)
        # deletion doens't remove the status, it turns it into a tombstone
        status = models.Status.objects.get()
        self.assertTrue(status.deleted)
        self.assertIsInstance(status.deleted_date, datetime)

        # notifications should be truly deleted
        self.assertEqual(models.Notification.objects.count(), 1)
        self.assertEqual(models.Notification.objects.get(), notif)


    def test_handle_favorite(self):
        ''' fav a status '''
        activity = {
            '@context': 'https://www.w3.org/ns/activitystreams',
            'id': 'https://example.com/fav/1',
            'actor': 'https://example.com/users/rat',
            'published': 'Mon, 25 May 2020 19:31:20 GMT',
            'object': 'https://example.com/status/1',
        }

        incoming.handle_favorite(activity)

        fav = models.Favorite.objects.get(remote_id='https://example.com/fav/1')
        self.assertEqual(fav.status, self.status)
        self.assertEqual(fav.remote_id, 'https://example.com/fav/1')
        self.assertEqual(fav.user, self.remote_user)

    def test_handle_unfavorite(self):
        ''' fav a status '''
        activity = {
            'id': 'https://example.com/fav/1#undo',
            'type': 'Undo',
            'object': {
                '@context': 'https://www.w3.org/ns/activitystreams',
                'id': 'https://example.com/fav/1',
                'actor': 'https://example.com/users/rat',
                'published': 'Mon, 25 May 2020 19:31:20 GMT',
                'object': 'https://example.com/fav/1',
            }
        }
        models.Favorite.objects.create(
            status=self.status,
            user=self.remote_user,
            remote_id='https://example.com/fav/1')
        self.assertEqual(models.Favorite.objects.count(), 1)

        incoming.handle_unfavorite(activity)
        self.assertEqual(models.Favorite.objects.count(), 0)


    def test_handle_boost(self):
        ''' boost a status '''
        self.assertEqual(models.Notification.objects.count(), 0)
        activity = {
            'type': 'Announce',
            'id': '%s/boost' % self.status.remote_id,
            'actor': self.remote_user.remote_id,
            'object': self.status.to_activity(),
        }
        with patch('bookwyrm.models.status.Status.ignore_activity') \
                as discarder:
            discarder.return_value = False
            incoming.handle_boost(activity)
        boost = models.Boost.objects.get()
        self.assertEqual(boost.boosted_status, self.status)
        notification = models.Notification.objects.get()
        self.assertEqual(notification.user, self.local_user)
        self.assertEqual(notification.related_status, self.status)


    def test_handle_unboost(self):
        ''' undo a boost '''
        activity = {
            'type': 'Undo',
            'object': {
                'type': 'Announce',
                'id': '%s/boost' % self.status.remote_id,
                'actor': self.local_user.remote_id,
                'object': self.status.to_activity(),
            }
        }
        models.Boost.objects.create(
            boosted_status=self.status, user=self.remote_user)
        incoming.handle_unboost(activity)


    def test_handle_add_book(self):
        ''' shelving a book '''
        book = models.Edition.objects.create(
            title='Test', remote_id='https://bookwyrm.social/book/37292')
        shelf = models.Shelf.objects.create(
            user=self.remote_user, name='Test Shelf')
        shelf.remote_id = 'https://bookwyrm.social/user/mouse/shelf/to-read'
        shelf.save()

        activity = {
            "id": "https://bookwyrm.social/shelfbook/6189#add",
            "type": "Add",
            "actor": "hhttps://example.com/users/rat",
            "object": "https://bookwyrm.social/book/37292",
            "target": "https://bookwyrm.social/user/mouse/shelf/to-read",
            "@context": "https://www.w3.org/ns/activitystreams"
        }
        incoming.handle_add(activity)
        self.assertEqual(shelf.books.first(), book)


    def test_handle_update_user(self):
        ''' update an existing user '''
        datafile = pathlib.Path(__file__).parent.joinpath(
            'data/ap_user.json')
        userdata = json.loads(datafile.read_bytes())
        del userdata['icon']
        self.assertEqual(self.local_user.name, '')
        incoming.handle_update_user({'object': userdata})
        user = models.User.objects.get(id=self.local_user.id)
        self.assertEqual(user.name, 'MOUSE?? MOUSE!!')


    def test_handle_update_edition(self):
        ''' update an existing edition '''
        datafile = pathlib.Path(__file__).parent.joinpath(
            'data/fr_edition.json')
        bookdata = json.loads(datafile.read_bytes())

        models.Work.objects.create(
            title='Test Work', remote_id='https://bookwyrm.social/book/5988')
        book = models.Edition.objects.create(
            title='Test Book', remote_id='https://bookwyrm.social/book/5989')

        del bookdata['authors']
        self.assertEqual(book.title, 'Test Book')

        with patch(
                'bookwyrm.activitypub.base_activity.set_related_field.delay'):
            incoming.handle_update_edition({'object': bookdata})
        book = models.Edition.objects.get(id=book.id)
        self.assertEqual(book.title, 'Piranesi')


    def test_handle_update_work(self):
        ''' update an existing edition '''
        datafile = pathlib.Path(__file__).parent.joinpath(
            'data/fr_work.json')
        bookdata = json.loads(datafile.read_bytes())

        book = models.Work.objects.create(
            title='Test Book', remote_id='https://bookwyrm.social/book/5988')

        del bookdata['authors']
        self.assertEqual(book.title, 'Test Book')
        with patch(
                'bookwyrm.activitypub.base_activity.set_related_field.delay'):
            incoming.handle_update_work({'object': bookdata})
        book = models.Work.objects.get(id=book.id)
        self.assertEqual(book.title, 'Piranesi')
