''' test for app action functionality '''
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http.response import Http404
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.settings import DOMAIN


# pylint: disable=too-many-public-methods
class AuthenticationViews(TestCase):
    ''' login and password management '''
    def setUp(self):
        ''' we need basic test data and mocks '''
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            'mouse@local.com', 'mouse@mouse.com', 'password',
            local=True, localname='mouse')
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        self.settings = models.SiteSettings.objects.create(id=1)

    def test_login_get(self):
        ''' there are so many views, this just makes sure it LOADS '''
        login = views.Login.as_view()
        request = self.factory.get('')
        request.user = self.anonymous_user

        result = login(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'login.html')
        self.assertEqual(result.status_code, 200)

        request.user = self.local_user
        result = login(request)
        self.assertEqual(result.url, '/')
        self.assertEqual(result.status_code, 302)


    def test_password_reset_request(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.PasswordResetRequest.as_view()
        request = self.factory.get('')
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'password_reset_request.html')
        self.assertEqual(result.status_code, 200)


    def test_password_reset_request_post(self):
        ''' send 'em an email '''
        request = self.factory.post('', {'email': 'aa@bb.ccc'})
        view = views.PasswordResetRequest.as_view()
        resp = view(request)
        self.assertEqual(resp.status_code, 302)

        request = self.factory.post('', {'email': 'mouse@mouse.com'})
        with patch('bookwyrm.emailing.send_email.delay'):
            resp = view(request)
        self.assertEqual(resp.template_name, 'password_reset_request.html')

        self.assertEqual(
            models.PasswordReset.objects.get().user, self.local_user)

    def test_password_reset(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.PasswordReset.as_view()
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.get('')
        request.user = self.anonymous_user
        result = view(request, code.code)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'password_reset.html')
        self.assertEqual(result.status_code, 200)


    def test_password_reset_post(self):
        ''' reset from code '''
        view = views.PasswordReset.as_view()
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.post('', {
            'password': 'hi',
            'confirm-password': 'hi'
        })
        with patch('bookwyrm.views.password.login'):
            resp = view(request, code.code)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(models.PasswordReset.objects.exists())

    def test_password_reset_wrong_code(self):
        ''' reset from code '''
        view = views.PasswordReset.as_view()
        models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.post('', {
            'password': 'hi',
            'confirm-password': 'hi'
        })
        resp = view(request, 'jhgdkfjgdf')
        self.assertEqual(resp.template_name, 'password_reset.html')
        self.assertTrue(models.PasswordReset.objects.exists())

    def test_password_reset_mismatch(self):
        ''' reset from code '''
        view = views.PasswordReset.as_view()
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.post('', {
            'password': 'hi',
            'confirm-password': 'hihi'
        })
        resp = view(request, code.code)
        self.assertEqual(resp.template_name, 'password_reset.html')
        self.assertTrue(models.PasswordReset.objects.exists())


    def test_register(self):
        ''' create a user '''
        view = views.Register.as_view()
        self.assertEqual(models.User.objects.count(), 1)
        request = self.factory.post(
            'register/',
            {
                'localname': 'nutria-user.user_nutria',
                'password': 'mouseword',
                'email': 'aa@bb.cccc'
            })
        with patch('bookwyrm.views.authentication.login'):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.status_code, 302)
        nutria = models.User.objects.last()
        self.assertEqual(nutria.username, 'nutria-user.user_nutria@%s' % DOMAIN)
        self.assertEqual(nutria.localname, 'nutria-user.user_nutria')
        self.assertEqual(nutria.local, True)

    def test_register_trailing_space(self):
        ''' django handles this so weirdly '''
        view = views.Register.as_view()
        request = self.factory.post(
            'register/',
            {
                'localname': 'nutria ',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        with patch('bookwyrm.views.authentication.login'):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.status_code, 302)
        nutria = models.User.objects.last()
        self.assertEqual(nutria.username, 'nutria@%s' % DOMAIN)
        self.assertEqual(nutria.localname, 'nutria')
        self.assertEqual(nutria.local, True)

    def test_register_invalid_email(self):
        ''' gotta have an email '''
        view = views.Register.as_view()
        self.assertEqual(models.User.objects.count(), 1)
        request = self.factory.post(
            'register/',
            {
                'localname': 'nutria',
                'password': 'mouseword',
                'email': 'aa'
            })
        response = view(request)
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(response.template_name, 'login.html')

    def test_register_invalid_username(self):
        ''' gotta have an email '''
        view = views.Register.as_view()
        self.assertEqual(models.User.objects.count(), 1)
        request = self.factory.post(
            'register/',
            {
                'localname': 'nut@ria',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        response = view(request)
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(response.template_name, 'login.html')

        request = self.factory.post(
            'register/',
            {
                'localname': 'nutr ia',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        response = view(request)
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(response.template_name, 'login.html')

        request = self.factory.post(
            'register/',
            {
                'localname': 'nut@ria',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        response = view(request)
        self.assertEqual(models.User.objects.count(), 1)
        self.assertEqual(response.template_name, 'login.html')


    def test_register_closed_instance(self):
        ''' you can't just register '''
        view = views.Register.as_view()
        self.settings.allow_registration = False
        self.settings.save()
        request = self.factory.post(
            'register/',
            {
                'localname': 'nutria ',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_register_invite(self):
        ''' you can't just register '''
        view = views.Register.as_view()
        self.settings.allow_registration = False
        self.settings.save()
        models.SiteInvite.objects.create(
            code='testcode', user=self.local_user, use_limit=1)
        self.assertEqual(models.SiteInvite.objects.get().times_used, 0)

        request = self.factory.post(
            'register/',
            {
                'localname': 'nutria',
                'password': 'mouseword',
                'email': 'aa@bb.ccc',
                'invite_code': 'testcode'
            })
        with patch('bookwyrm.views.authentication.login'):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.SiteInvite.objects.get().times_used, 1)

        # invite already used to max capacity
        request = self.factory.post(
            'register/',
            {
                'localname': 'nutria2',
                'password': 'mouseword',
                'email': 'aa@bb.ccc',
                'invite_code': 'testcode'
            })
        with self.assertRaises(PermissionDenied):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)

        # bad invite code
        request = self.factory.post(
            'register/',
            {
                'localname': 'nutria3',
                'password': 'mouseword',
                'email': 'aa@bb.ccc',
                'invite_code': 'dkfkdjgdfkjgkdfj'
            })
        with self.assertRaises(Http404):
            response = view(request)
        self.assertEqual(models.User.objects.count(), 2)


    def test_password_change(self):
        ''' change password '''
        view = views.ChangePassword.as_view()
        password_hash = self.local_user.password
        request = self.factory.post('', {
            'password': 'hi',
            'confirm-password': 'hi'
        })
        request.user = self.local_user
        with patch('bookwyrm.views.password.login'):
            view(request)
        self.assertNotEqual(self.local_user.password, password_hash)

    def test_password_change_mismatch(self):
        ''' change password '''
        view = views.ChangePassword.as_view()
        password_hash = self.local_user.password
        request = self.factory.post('', {
            'password': 'hi',
            'confirm-password': 'hihi'
        })
        request.user = self.local_user
        view(request)
        self.assertEqual(self.local_user.password, password_hash)
