''' test for app action functionality '''
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models
from bookwyrm import views


class DirectMessageViews(TestCase):
    ''' dms '''
    def setUp(self):
        ''' we need basic test data and mocks '''
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            'mouse@local.com', 'mouse@mouse.mouse', 'password',
            local=True, localname='mouse')


    def test_direct_messages_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.DirectMessages.as_view()
        request = self.factory.get('')
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'direct_messages.html')
        self.assertEqual(result.status_code, 200)
