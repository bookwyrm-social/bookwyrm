''' test for app action functionality '''
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http.response import Http404
from django.template.response import TemplateResponse
from django.test import TestCase

from bookwyrm import models, views
from bookwyrm.settings import DOMAIN


# pylint: disable=too-many-public-methods
class AuthenticationViews(TestCase):
    ''' login and password management '''
    def test_login_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        request = self.factory.get('')
        request.user = AnonymousUser
        result = views.Login.get(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'login.html')
        self.assertEqual(result.status_code, 200)

        request.user = self.local_user
        result = views.Login.get(request)
        self.assertEqual(result.url, '/')
        self.assertEqual(result.status_code, 302)


    def test_password_reset_request(self):
        ''' there are so many views, this just makes sure it LOADS '''
        request = self.factory.get('')
        request.user = self.local_user
        result = views.PasswordResetRequest.get(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'password_reset_request.html')
        self.assertEqual(result.status_code, 200)


    def test_password_reset_request_post(self):
        ''' send 'em an email '''
        request = self.factory.post('', {'email': 'aa@bb.ccc'})
        resp = views.PasswordReset.post_request(request)
        self.assertEqual(resp.status_code, 302)

        request = self.factory.post(
            '', {'email': 'mouse@mouse.com'})
        with patch('bookwyrm.emailing.send_email.delay'):
            resp = views.PasswordReset.post_request(request)
        self.assertEqual(resp.template_name, 'password_reset_request.html')

        self.assertEqual(
            models.PasswordReset.objects.get().user, self.local_user)

    def test_password_reset(self):
        ''' there are so many views, this just makes sure it LOADS '''
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.get('')
        request.user = AnonymousUser
        result = views.PasswordReset.get(request, code.code)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'password_reset.html')
        self.assertEqual(result.status_code, 200)


    def test_password_reset_post(self):
        ''' reset from code '''
        code = models.PasswordReset.objects.create(user=self.local_user)
        request = self.factory.post('', {
            'reset-code':  code.code,
            'password': 'hi',
            'confirm-password': 'hi'
        })
        with patch('bookwyrm.views.Login.get'):
            resp = views.PasswordReset.post(request)
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
        resp = views.PasswordReset.post(request)
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
        resp = views.PasswordReset.post(request)
        self.assertEqual(resp.template_name, 'password_reset.html')
        self.assertTrue(models.PasswordReset.objects.exists())


    def test_register(self):
        ''' create a user '''
        self.assertEqual(models.User.objects.count(), 2)
        request = self.factory.post(
            'register/',
            {
                'localname': 'nutria-user.user_nutria',
                'password': 'mouseword',
                'email': 'aa@bb.cccc'
            })
        with patch('bookwyrm.views.Login.get'):
            response = views.Register.post(request)
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
                'localname': 'nutria ',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        with patch('bookwyrm.views.Login.get'):
            response = views.Register.post(request)
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
                'localname': 'nutria',
                'password': 'mouseword',
                'email': 'aa'
            })
        response = views.Register.post(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.template_name, 'login.html')

    def test_register_invalid_username(self):
        ''' gotta have an email '''
        self.assertEqual(models.User.objects.count(), 2)
        request = self.factory.post(
            'register/',
            {
                'localname': 'nut@ria',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        response = views.Register.post(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.template_name, 'login.html')

        request = self.factory.post(
            'register/',
            {
                'localname': 'nutr ia',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        response = views.Register.post(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.template_name, 'login.html')

        request = self.factory.post(
            'register/',
            {
                'localname': 'nut@ria',
                'password': 'mouseword',
                'email': 'aa@bb.ccc'
            })
        response = views.Register.post(request)
        self.assertEqual(models.User.objects.count(), 2)
        self.assertEqual(response.template_name, 'login.html')


    def test_register_closed_instance(self):
        ''' you can't just register '''
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
            views.Register.post(request)

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
                'localname': 'nutria',
                'password': 'mouseword',
                'email': 'aa@bb.ccc',
                'invite_code': 'testcode'
            })
        with patch('bookwyrm.views.Login.get'):
            response = views.Register.post(request)
        self.assertEqual(models.User.objects.count(), 3)
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
            response = views.Register.post(request)
        self.assertEqual(models.User.objects.count(), 3)

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
            response = views.Register.post(request)
        self.assertEqual(models.User.objects.count(), 3)


    def test_password_change(self):
        ''' change password '''
        password_hash = self.local_user.password
        request = self.factory.post('', {
            'password': 'hi',
            'confirm-password': 'hi'
        })
        request.user = self.local_user
        with patch('bookwyrm.views.Login.get'):
            views.ChangePassword.post(request)
        self.assertNotEqual(self.local_user.password, password_hash)

    def test_password_change_mismatch(self):
        ''' change password '''
        password_hash = self.local_user.password
        request = self.factory.post('', {
            'password': 'hi',
            'confirm-password': 'hihi'
        })
        request.user = self.local_user
        views.ChangePassword.post(request)
        self.assertEqual(self.local_user.password, password_hash)
