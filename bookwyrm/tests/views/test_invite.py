''' test for app action functionality '''
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import views


class InviteViews(TestCase):
    ''' every response to a get request, html or json '''
    def setUp(self):
        ''' we need basic test data and mocks '''
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            'mouse@local.com', 'mouse@mouse.mouse', 'password',
            local=True, localname='mouse')


    def test_invite_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.Invite.as_view()
        models.SiteInvite.objects.create(code='hi', user=self.local_user)
        request = self.factory.get('')
        request.user = AnonymousUser
        # why?? this is annoying.
        request.user.is_authenticated = False
        with patch('bookwyrm.models.site.SiteInvite.valid') as invite:
            invite.return_value = True
            result = view(request, 'hi')
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'invite.html')
        self.assertEqual(result.status_code, 200)


    def test_manage_invites(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.ManageInvites.as_view()
        request = self.factory.get('')
        request.user = self.local_user
        request.user.is_superuser = True
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'settings/manage_invites.html')
        self.assertEqual(result.status_code, 200)
