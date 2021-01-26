''' test for app action functionality '''
import pathlib
from unittest.mock import patch
from PIL import Image

from django.core.files.base import ContentFile
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.activitypub import ActivitypubResponse


class UserViews(TestCase):
    ''' view user and edit profile '''
    def setUp(self):
        ''' we need basic test data and mocks '''
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            'mouse@local.com', 'mouse@mouse.mouse', 'password',
            local=True, localname='mouse')


    def test_user_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.User.as_view()
        request = self.factory.get('')
        request.user = self.local_user
        with patch('bookwyrm.views.user.is_api_request') as is_api:
            is_api.return_value = False
            result = view(request, 'mouse')
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'user.html')
        self.assertEqual(result.status_code, 200)

        with patch('bookwyrm.views.user.is_api_request') as is_api:
            is_api.return_value = True
            result = view(request, 'mouse')
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)


    def test_followers_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.Followers.as_view()
        request = self.factory.get('')
        request.user = self.local_user
        with patch('bookwyrm.views.user.is_api_request') as is_api:
            is_api.return_value = False
            result = view(request, 'mouse')
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'followers.html')
        self.assertEqual(result.status_code, 200)

        with patch('bookwyrm.views.user.is_api_request') as is_api:
            is_api.return_value = True
            result = view(request, 'mouse')
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)


    def test_following_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.Following.as_view()
        request = self.factory.get('')
        request.user = self.local_user
        with patch('bookwyrm.views.user.is_api_request') as is_api:
            is_api.return_value = False
            result = view(request, 'mouse')
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'following.html')
        self.assertEqual(result.status_code, 200)

        with patch('bookwyrm.views.user.is_api_request') as is_api:
            is_api.return_value = True
            result = view(request, 'mouse')
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)


    def test_edit_profile_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.EditUser.as_view()
        request = self.factory.get('')
        request.user = self.local_user
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        self.assertEqual(result.template_name, 'edit_user.html')
        self.assertEqual(result.status_code, 200)


    def test_edit_user(self):
        ''' use a form to update a user '''
        view = views.EditUser.as_view()
        form = forms.EditUserForm(instance=self.local_user)
        form.data['name'] = 'New Name'
        request = self.factory.post('', form.data)
        request.user = self.local_user

        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            view(request)
        self.assertEqual(self.local_user.name, 'New Name')


    def test_crop_avatar(self):
        ''' reduce that image size '''
        image_file = pathlib.Path(__file__).parent.joinpath(
            '../../static/images/no_cover.jpg')
        image = Image.open(image_file)

        result = views.user.crop_avatar(image)
        self.assertIsInstance(result, ContentFile)
        image_result = Image.open(result)
        self.assertEqual(image_result.size, (120, 120))
