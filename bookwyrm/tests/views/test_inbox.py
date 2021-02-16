''' tests incoming activities'''
import json
from unittest.mock import patch

from django.http import HttpResponseNotAllowed, HttpResponseNotFound
from django.test import TestCase, Client

from bookwyrm import models

class Inbox(TestCase):
    ''' readthrough tests '''
    def setUp(self):
        ''' basic user and book data '''
        self.client = Client()
        self.local_user = models.User.objects.create_user(
            'mouse@example.com', 'mouse@mouse.com', 'mouseword',
            local=True, localname='mouse')
        self.local_user.remote_id = 'https://example.com/user/mouse'
        self.local_user.save(broadcast=False)
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            self.remote_user = models.User.objects.create_user(
                'rat', 'rat@rat.com', 'ratword',
                local=False,
                remote_id='https://example.com/users/rat',
                inbox='https://example.com/users/rat/inbox',
                outbox='https://example.com/users/rat/outbox',
            )
        with patch('bookwyrm.models.activitypub_mixin.broadcast_task.delay'):
            self.status = models.Status.objects.create(
                user=self.local_user,
                content='Test status',
                remote_id='https://example.com/status/1',
            )
        models.SiteSettings.objects.create()


    def test_inbox_invalid_get(self):
        ''' shouldn't try to handle if the user is not found '''
        result = self.client.get(
            '/inbox', content_type="application/json"
        )
        self.assertIsInstance(result, HttpResponseNotAllowed)

    def test_inbox_invalid_user(self):
        ''' shouldn't try to handle if the user is not found '''
        result = self.client.post(
            '/user/bleh/inbox',
            '{"type": "Test", "object": "exists"}',
            content_type="application/json"
        )
        self.assertIsInstance(result, HttpResponseNotFound)

    def test_inbox_invalid_bad_signature(self):
        ''' bad request for invalid signature '''
        with patch('bookwyrm.views.inbox.has_valid_signature') as mock_valid:
            mock_valid.return_value = False
            result = self.client.post(
                '/user/mouse/inbox',
                '{"type": "Test", "object": "exists"}',
                content_type="application/json"
            )
            self.assertEqual(result.status_code, 401)

    def test_inbox_invalid_bad_signature_delete(self):
        ''' invalid signature for Delete is okay though '''
        with patch('bookwyrm.views.inbox.has_valid_signature') as mock_valid:
            mock_valid.return_value = False
            result = self.client.post(
                '/user/mouse/inbox',
                '{"type": "Delete", "object": "exists"}',
                content_type="application/json"
            )
            self.assertEqual(result.status_code, 200)

    def test_inbox_unknown_type(self):
        ''' never heard of that activity type, don't have a handler for it '''
        with patch('bookwyrm.views.inbox.has_valid_signature') as mock_valid:
            result = self.client.post(
                '/inbox',
                '{"type": "Fish", "object": "exists"}',
                content_type="application/json"
            )
            mock_valid.return_value = True
            self.assertIsInstance(result, HttpResponseNotFound)


    def test_inbox_success(self):
        ''' a known type, for which we start a task '''
        activity = {
            'id': 'hi',
            'type': 'Create',
            'actor': 'hi',
            "to": [
                "https://www.w3.org/ns/activitystreams#Public"
            ],
            "cc": [
                "https://example.com/user/mouse/followers"
            ],
            'object': {
                "id": "https://example.com/list/22",
                "type": "BookList",
                "totalItems": 1,
                "first": "https://example.com/list/22?page=1",
                "last": "https://example.com/list/22?page=1",
                "name": "Test List",
                "owner": "https://example.com/user/mouse",
                "to": [
                    "https://www.w3.org/ns/activitystreams#Public"
                ],
                "cc": [
                    "https://example.com/user/mouse/followers"
                ],
                "summary": "summary text",
                "curation": "curated",
                "@context": "https://www.w3.org/ns/activitystreams"
            }
        }
        with patch('bookwyrm.views.inbox.has_valid_signature') as mock_valid:
            mock_valid.return_value = True

            with patch('bookwyrm.views.inbox.activity_task.delay'):
                result = self.client.post(
                    '/inbox',
                    json.dumps(activity),
                    content_type="application/json"
                )
        self.assertEqual(result.status_code, 200)
