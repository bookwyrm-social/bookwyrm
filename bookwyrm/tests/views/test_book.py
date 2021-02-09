''' test for app action functionality '''
from unittest.mock import patch
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views
from bookwyrm.activitypub import ActivitypubResponse


class BookViews(TestCase):
    ''' books books books '''
    def setUp(self):
        ''' we need basic test data and mocks '''
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            'mouse@local.com', 'mouse@mouse.com', 'mouseword',
            local=True, localname='mouse',
            remote_id='https://example.com/users/mouse',
        )
        self.group = Group.objects.create(name='editor')
        self.group.permissions.add(
            Permission.objects.create(
                name='edit_book',
                codename='edit_book',
                content_type=ContentType.objects.get_for_model(models.User)).id
        )
        self.work = models.Work.objects.create(title='Test Work')
        self.book = models.Edition.objects.create(
            title='Example Edition',
            remote_id='https://example.com/book/1',
            parent_work=self.work
        )
        models.SiteSettings.objects.create()


    def test_book_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.Book.as_view()
        request = self.factory.get('')
        request.user = self.local_user
        with patch('bookwyrm.views.books.is_api_request') as is_api:
            is_api.return_value = False
            result = view(request, self.book.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request = self.factory.get('')
        with patch('bookwyrm.views.books.is_api_request') as is_api:
            is_api.return_value = True
            result = view(request, self.book.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)


    def test_edit_book_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.EditBook.as_view()
        request = self.factory.get('')
        request.user = self.local_user
        request.user.is_superuser = True
        result = view(request, self.book.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)


    def test_edit_book(self):
        ''' lets a user edit a book '''
        view = views.EditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm(instance=self.book)
        form.data['title'] = 'New Title'
        form.data['last_edited_by'] = self.local_user.id
        request = self.factory.post('', form.data)
        request.user = self.local_user
        with patch('bookwyrm.broadcast.broadcast_task.delay'):
            view(request, self.book.id)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, 'New Title')


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
            views.switch_edition(request)

        self.assertEqual(models.ShelfBook.objects.get().book, edition2)
        self.assertEqual(models.ReadThrough.objects.get().book, edition2)


    def test_editions_page(self):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.Editions.as_view()
        request = self.factory.get('')
        with patch('bookwyrm.views.books.is_api_request') as is_api:
            is_api.return_value = False
            result = view(request, self.work.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request = self.factory.get('')
        with patch('bookwyrm.views.books.is_api_request') as is_api:
            is_api.return_value = True
            result = view(request, self.work.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)
