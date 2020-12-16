''' test for app action functionality '''
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.http.response import Http404
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import view_actions as actions, models
from bookwyrm.settings import DOMAIN


#pylint: disable=too-many-public-methods
class ViewActions(TestCase):
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
        self.settings = models.SiteSettings.objects.create(id=1)
        self.factory = RequestFactory()


    def test_register(self):
        ''' create a user '''
        self.assertEqual(models.User.objects.count(), 2)
        request = self.factory.post(
            'register/',
            {
                'username': 'nutria-user.user_nutria',
                'password': 'mouseword',
                'email': 'aa@bb.cccc'
            })
        with patch('bookwyrm.view_actions.login'):
            response = actions.register(request)
        self.assertEqual(models.User.objects.count(), 3)
        self.assertEqual(response.status_code, 302)
        nutria = models.User.objects.last()
        self.assertEqual(nutria.username, 'nutria-user.user_nutria@%s' % DOMAIN)
        self.assertEqual(nutria.localname, 'nutria-user.user_nutria')
        self.assertEqual(nutria.local, True)

    def test_register_trailing_space(self):
        ''' django handles this so weirdly '''
        request = self.factory.post(
            'register/',
            {
                'username': 'nutria ',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        with patch('bookwyrm.view_actions.login'):
            response = actions.register(request)
        self.assertEqual(models.User.objects.count(), 3)
        self.assertEqual(response.status_code, 302)
        nutria = models.User.objects.last()
        self.assertEqual(nutria.username, 'nutria@%s' % DOMAIN)
        self.assertEqual(nutria.localname, 'nutria')
        self.assertEqual(nutria.local, True)

    def test_register_invalid_email(self):
        ''' gotta have an email '''
        self.assertEqual(models.User.objects.count(), 2)
        request = self.factory.post(
            'register/',
            {
                'username': 'nutria',
                'password': 'mouseword',
                'email': 'aa'
            })
        response = actions.register(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.template_name, 'login.html')

    def test_register_invalid_username(self):
        ''' gotta have an email '''
        self.assertEqual(models.User.objects.count(), 2)
        request = self.factory.post(
            'register/',
            {
                'username': 'nut@ria',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        response = actions.register(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.template_name, 'login.html')

        request = self.factory.post(
            'register/',
            {
                'username': 'nutr ia',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        response = actions.register(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.template_name, 'login.html')

        request = self.factory.post(
            'register/',
            {
                'username': 'nut@ria',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        response = actions.register(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.template_name, 'login.html')


    def test_register_closed_instance(self):
        ''' you can't just register '''
        self.settings.allow_registration = False
        self.settings.save()
        request = self.factory.post(
            'register/',
            {
                'username': 'nutria ',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        with self.assertRaises(PermissionDenied):
            actions.register(request)

    def test_register_invite(self):
        ''' you can't just register '''
        self.settings.allow_registration = False
        self.settings.save()
        models.SiteInvite.objects.create(
            code='testcode', user=self.local_user, use_limit=1)
        self.assertEqual(models.SiteInvite.objects.get().times_used, 0)

        request = self.factory.post(
            'register/',
            {
                'username': 'nutria',
                'password': 'mouseword',
                'email': 'aa@bb.ccc',
                'invite_code': 'testcode'
            })
        with patch('bookwyrm.view_actions.login'):
            response = actions.register(request)
        self.assertEqual(models.User.objects.count(), 3)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.SiteInvite.objects.get().times_used, 1)

        # invalid invite
        request = self.factory.post(
            'register/',
            {
                'username': 'nutria2',
                'password': 'mouseword',
                'email': 'aa@bb.ccc',
                'invite_code': 'testcode'
            })
        response = actions.register(request)
        self.assertEqual(models.User.objects.count(), 3)

        # bad invite code
        request = self.factory.post(
            'register/',
            {
                'username': 'nutria3',
                'password': 'mouseword',
                'email': 'aa@bb.ccc',
                'invite_code': 'dkfkdjgdfkjgkdfj'
            })
        with self.assertRaises(Http404):
            response = actions.register(request)
        self.assertEqual(models.User.objects.count(), 3)


    def test_password_reset_request(self):
        ''' send 'em an email '''
        request = self.factory.post('', {'email': 'aa@bb.ccc'})
        resp = actions.password_reset_request(request)
        self.assertEqual(resp.status_code, 302)

        request = self.factory.post(
            '', {'email': 'mouse@mouse.com'})
        with patch('bookwyrm.emailing.send_email.delay'):
            resp = actions.password_reset_request(request)
        self.assertEqual(resp.template_name, 'password_reset_request.html')

        self.assertEqual(
            models.PasswordReset.objects.get().user, self.local_user)

    def test_password_reset(self):
        ''' reset from code '''
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.post('', {
            'reset-code':  code.code,
            'password': 'hi',
            'confirm-password': 'hi'
        })
        with patch('bookwyrm.view_actions.login'):
            resp = actions.password_reset(request)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(models.PasswordReset.objects.exists())

    def test_password_reset_wrong_code(self):
        ''' reset from code '''
        models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.post('', {
            'reset-code': 'jhgdkfjgdf',
            'password': 'hi',
            'confirm-password': 'hi'
        })
        resp = actions.password_reset(request)
        self.assertEqual(resp.template_name, 'password_reset.html')
        self.assertTrue(models.PasswordReset.objects.exists())

    def test_password_reset_mismatch(self):
        ''' reset from code '''
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.post('', {
            'reset-code': code.code,
            'password': 'hi',
            'confirm-password': 'hihi'
        })
        resp = actions.password_reset(request)
        self.assertEqual(resp.template_name, 'password_reset.html')
        self.assertTrue(models.PasswordReset.objects.exists())

    def test_switch_edition(self):
        ''' updates user's relationships to a book '''
        work = models.Work.objects.create(title='test work')
        edition1 = models.Edition.objects.create(
            title='first ed', parent_work=work)
        edition2 = models.Edition.objects.create(
            title='second ed', parent_work=work)
        shelf = models.Shelf.objects.create(
            name='Test Shelf', user=self.local_user)
        shelf.books.add(edition1)
        models.ReadThrough.objects.create(
            user=self.local_user, book=edition1)

        self.assertEqual(models.ShelfBook.objects.get().book, edition1)
        self.assertEqual(models.ReadThrough.objects.get().book, edition1)
        request = self.factory.post('', {
            'edition': edition2.id
        })
        request.user = self.local_user
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            actions.switch_edition(request)

        self.assertEqual(models.ShelfBook.objects.get().book, edition2)
        self.assertEqual(models.ReadThrough.objects.get().book, edition2)
