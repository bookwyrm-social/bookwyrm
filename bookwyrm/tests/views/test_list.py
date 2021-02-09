''' test for app action functionality '''
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import models, views
from bookwyrm.activitypub import ActivitypubResponse


@patch('bookwyrm.broadcast.broadcast_task.delay')
class ListViews(TestCase):
    ''' tag views'''
    def setUp(self):
        ''' we need basic test data and mocks '''
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            'mouse@local.com', 'mouse@mouse.com', 'mouseword',
            local=True, localname='mouse',
            remote_id='https://example.com/users/mouse',
        )
        self.rat = models.User.objects.create_user(
            'rat@local.com', 'rat@rat.com', 'ratword',
            local=True, localname='rat',
            remote_id='https://example.com/users/rat',
        )
        work = models.Work.objects.create(title='Work')
        self.book = models.Edition.objects.create(
            title='Example Edition',
            remote_id='https://example.com/book/1',
            parent_work=work,
        )
        self.list = models.List.objects.create(
            name='Test List', user=self.local_user)
        self.anonymous_user = AnonymousUser
        self.anonymous_user.is_authenticated = False
        models.SiteSettings.objects.create()


    def test_lists_page(self, _):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.Lists.as_view()
        models.List.objects.create(name='Public list', user=self.local_user)
        models.List.objects.create(
            name='Private list', privacy='private', user=self.local_user)
        request = self.factory.get('')
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)


    def test_lists_create(self, _):
        ''' create list view '''
        view = views.Lists.as_view()
        request = self.factory.post('', {
            'name': 'A list',
            'description': 'wow',
            'privacy': 'unlisted',
            'curation': 'open',
            'user': self.local_user.id,
        })
        request.user = self.local_user
        result = view(request)
        self.assertEqual(result.status_code, 302)
        new_list = models.List.objects.filter(name='A list').get()
        self.assertEqual(new_list.description, 'wow')
        self.assertEqual(new_list.privacy, 'unlisted')
        self.assertEqual(new_list.curation, 'open')


    def test_list_page(self, _):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.List.as_view()
        request = self.factory.get('')
        request.user = self.local_user

        with patch('bookwyrm.views.list.is_api_request') as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user
        with patch('bookwyrm.views.list.is_api_request') as is_api:
            is_api.return_value = False
            result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        with patch('bookwyrm.views.list.is_api_request') as is_api:
            is_api.return_value = True
            result = view(request, self.list.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)

        request = self.factory.get('/?page=1')
        request.user = self.local_user
        with patch('bookwyrm.views.list.is_api_request') as is_api:
            is_api.return_value = True
            result = view(request, self.list.id)
        self.assertIsInstance(result, ActivitypubResponse)
        self.assertEqual(result.status_code, 200)


    def test_list_edit(self, _):
        ''' edit a list '''
        view = views.List.as_view()
        request = self.factory.post('', {
            'name': 'New Name',
            'description': 'wow',
            'privacy': 'direct',
            'curation': 'curated',
            'user': self.local_user.id,
        })
        request.user = self.local_user

        result = view(request, self.list.id)
        self.assertEqual(result.status_code, 302)

        self.list.refresh_from_db()
        self.assertEqual(self.list.name, 'New Name')
        self.assertEqual(self.list.description, 'wow')
        self.assertEqual(self.list.privacy, 'direct')
        self.assertEqual(self.list.curation, 'curated')


    def test_curate_page(self, _):
        ''' there are so many views, this just makes sure it LOADS '''
        view = views.Curate.as_view()
        models.List.objects.create(name='Public list', user=self.local_user)
        models.List.objects.create(
            name='Private list', privacy='private', user=self.local_user)
        request = self.factory.get('')
        request.user = self.local_user

        result = view(request, self.list.id)
        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

        request.user = self.anonymous_user
        result = view(request, self.list.id)
        self.assertEqual(result.status_code, 302)


    def test_curate_approve(self, _):
        ''' approve a pending item '''
        view = views.Curate.as_view()
        pending = models.ListItem.objects.create(
            book_list=self.list,
            added_by=self.local_user,
            book=self.book,
            approved=False
        )

        request = self.factory.post('', {
            'item': pending.id,
            'approved': 'true',
        })
        request.user = self.local_user

        view(request, self.list.id)
        pending.refresh_from_db()
        self.assertEqual(self.list.books.count(), 1)
        self.assertEqual(self.list.listitem_set.first(), pending)
        self.assertTrue(pending.approved)


    def test_curate_reject(self, _):
        ''' approve a pending item '''
        view = views.Curate.as_view()
        pending = models.ListItem.objects.create(
            book_list=self.list,
            added_by=self.local_user,
            book=self.book,
            approved=False
        )

        request = self.factory.post('', {
            'item': pending.id,
            'approved': 'false',
        })
        request.user = self.local_user

        view(request, self.list.id)
        self.assertFalse(self.list.books.exists())
        self.assertFalse(models.ListItem.objects.exists())


    def test_add_book(self, _):
        ''' put a book on a list '''
        request = self.factory.post('', {
            'book': self.book.id,
        })
        request.user = self.local_user

        views.list.add_book(request, self.list.id)
        item = self.list.listitem_set.get()
        self.assertEqual(item.book, self.book)
        self.assertEqual(item.added_by, self.local_user)
        self.assertTrue(item.approved)


    def test_add_book_outsider(self, _):
        ''' put a book on a list '''
        self.list.curation = 'open'
        self.list.save()
        request = self.factory.post('', {
            'book': self.book.id,
        })
        request.user = self.rat

        views.list.add_book(request, self.list.id)
        item = self.list.listitem_set.get()
        self.assertEqual(item.book, self.book)
        self.assertEqual(item.added_by, self.rat)
        self.assertTrue(item.approved)


    def test_add_book_pending(self, _):
        ''' put a book on a list '''
        self.list.curation = 'curated'
        self.list.save()
        request = self.factory.post('', {
            'book': self.book.id,
        })
        request.user = self.rat

        views.list.add_book(request, self.list.id)
        item = self.list.listitem_set.get()
        self.assertEqual(item.book, self.book)
        self.assertEqual(item.added_by, self.rat)
        self.assertFalse(item.approved)


    def test_add_book_self_curated(self, _):
        ''' put a book on a list '''
        self.list.curation = 'curated'
        self.list.save()
        request = self.factory.post('', {
            'book': self.book.id,
        })
        request.user = self.local_user

        views.list.add_book(request, self.list.id)
        item = self.list.listitem_set.get()
        self.assertEqual(item.book, self.book)
        self.assertEqual(item.added_by, self.local_user)
        self.assertTrue(item.approved)


    def test_remove_book(self, _):
        ''' take an item off a list '''
        item = models.ListItem.objects.create(
            book_list=self.list,
            added_by=self.local_user,
            book=self.book,
        )
        self.assertTrue(self.list.listitem_set.exists())
        request = self.factory.post('', {
            'item': item.id,
        })
        request.user = self.local_user

        views.list.remove_book(request, self.list.id)

        self.assertFalse(self.list.listitem_set.exists())


    def test_remove_book_unauthorized(self, _):
        ''' take an item off a list '''
        item = models.ListItem.objects.create(
            book_list=self.list,
            added_by=self.local_user,
            book=self.book,
        )
        self.assertTrue(self.list.listitem_set.exists())
        request = self.factory.post('', {
            'item': item.id,
        })
        request.user = self.rat

        views.list.remove_book(request, self.list.id)

        self.assertTrue(self.list.listitem_set.exists())
