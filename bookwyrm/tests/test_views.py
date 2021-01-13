''' test for app action functionality '''
from unittest.mock import patch

from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import vviews as views
from bookwyrm.settings import USER_AGENT


# pylint: disable=too-many-public-methods
class Views(TestCase):
    ''' every response to a get request, html or json '''
    def setUp(self):
        ''' we need basic test data and mocks '''
        self.factory = RequestFactory()
        self.work = models.Work.objects.create(title='Test Work')
        self.book = models.Edition.objects.create(
            title='Test Book', parent_work=self.work)
        models.Connector.objects.create(
            identifier='self',
            connector_file='self_connector',
            local=True
        )
        self.local_user = models.User.objects.create_user(
            'mouse@local.com', 'mouse@mouse.mouse', 'password',
            local=True, localname='mouse')
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            self.remote_user = models.User.objects.create_user(
                'rat', 'rat@rat.com', 'ratword',
                local=False,
                remote_id='https://example.com/users/rat',
                inbox='https://example.com/users/rat/inbox',
                outbox='https://example.com/users/rat/outbox',
            )


    def test_get_user_from_username(self):
        ''' works for either localname or username '''
        self.assertEqual(
            views.get_user_from_username('mouse'), self.local_user)
        self.assertEqual(
            views.get_user_from_username('mouse@local.com'), self.local_user)
        with self.assertRaises(models.User.DoesNotExist):
            views.get_user_from_username('mojfse@example.com')


    def test_is_api_request(self):
        ''' should it return html or json '''
        request = self.factory.get('/path')
        request.headers = {'Accept': 'application/json'}
        self.assertTrue(views.is_api_request(request))

        request = self.factory.get('/path.json')
        request.headers = {'Accept': 'Praise'}
        self.assertTrue(views.is_api_request(request))

        request = self.factory.get('/path')
        request.headers = {'Accept': 'Praise'}
        self.assertFalse(views.is_api_request(request))


    def test_get_activity_feed(self):
        ''' loads statuses '''
        rat = models.User.objects.create_user(
            'rat', 'rat@rat.rat', 'password', local=True)

        public_status = models.Comment.objects.create(
            content='public status', book=self.book, user=self.local_user)
        direct_status = models.Status.objects.create(
            content='direct', user=self.local_user, privacy='direct')

        rat_public = models.Status.objects.create(
            content='blah blah', user=rat)
        rat_unlisted = models.Status.objects.create(
            content='blah blah', user=rat, privacy='unlisted')
        remote_status = models.Status.objects.create(
            content='blah blah', user=self.remote_user)
        followers_status = models.Status.objects.create(
            content='blah', user=rat, privacy='followers')
        rat_mention = models.Status.objects.create(
            content='blah blah blah', user=rat, privacy='followers')
        rat_mention.mention_users.set([self.local_user])

        statuses = views.get_activity_feed(
            self.local_user,
            ['public', 'unlisted', 'followers'],
            following_only=True,
            queryset=models.Comment.objects
        )
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0], public_status)

        statuses = views.get_activity_feed(
            self.local_user,
            ['public', 'followers'],
            local_only=True
        )
        self.assertEqual(len(statuses), 2)
        self.assertEqual(statuses[1], public_status)
        self.assertEqual(statuses[0], rat_public)

        statuses = views.get_activity_feed(self.local_user, 'direct')
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0], direct_status)

        statuses = views.get_activity_feed(
            self.local_user,
            ['public', 'followers'],
        )
        self.assertEqual(len(statuses), 3)
        self.assertEqual(statuses[2], public_status)
        self.assertEqual(statuses[1], rat_public)
        self.assertEqual(statuses[0], remote_status)

        statuses = views.get_activity_feed(
            self.local_user,
            ['public', 'unlisted', 'followers'],
            following_only=True
        )
        self.assertEqual(len(statuses), 2)
        self.assertEqual(statuses[1], public_status)
        self.assertEqual(statuses[0], rat_mention)

        rat.followers.add(self.local_user)
        statuses = views.get_activity_feed(
            self.local_user,
            ['public', 'unlisted', 'followers'],
            following_only=True
        )
        self.assertEqual(len(statuses), 5)
        self.assertEqual(statuses[4], public_status)
        self.assertEqual(statuses[3], rat_public)
        self.assertEqual(statuses[2], rat_unlisted)
        self.assertEqual(statuses[1], followers_status)
        self.assertEqual(statuses[0], rat_mention)


    def test_is_bookwyrm_request(self):
        ''' checks if a request came from a bookwyrm instance '''
        request = self.factory.get('', {'q': 'Test Book'})
        self.assertFalse(views.is_bookworm_request(request))

        request = self.factory.get(
            '', {'q': 'Test Book'},
            HTTP_USER_AGENT=\
                "http.rb/4.4.1 (Mastodon/3.3.0; +https://mastodon.social/)"
        )
        self.assertFalse(views.is_bookworm_request(request))

        request = self.factory.get(
            '', {'q': 'Test Book'}, HTTP_USER_AGENT=USER_AGENT)
        self.assertTrue(views.is_bookworm_request(request))
