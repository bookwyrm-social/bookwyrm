""" test for app action functionality """
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory

from bookwyrm import forms, models, views


class AnnouncementViews(TestCase):
    """every response to a get request, html or json"""

    def setUp(self):
        """we need basic test data and mocks"""
        self.factory = RequestFactory()
        self.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        models.SiteSettings.objects.create()

    def test_announcements_page(self):
        """there are so many views, this just makes sure it LOADS"""
        models.Announcement.objects.create(preview="hi", user=self.local_user)

        view = views.Announcements.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_announcements_page_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.Announcements.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True

        result = view(request)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_announcement_page(self):
        """there are so many views, this just makes sure it LOADS"""
        announcement = models.Announcement.objects.create(
            preview="hi", user=self.local_user
        )

        view = views.Announcement.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True

        result = view(request, announcement.id)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)

    def test_create_announcement(self):
        """create a new announcement"""
        view = views.Announcements.as_view()
        form = forms.AnnouncementForm()
        form.data["preview"] = "hi hi"
        form.data["start_date"] = "2021-05-20"
        form.data["user"] = self.local_user.id

        request = self.factory.post("", form.data)
        request.user = self.local_user
        request.user.is_superuser = True

        view(request)

        announcement = models.Announcement.objects.get()
        self.assertEqual(announcement.preview, "hi hi")
        self.assertEqual(announcement.start_date.year, 2021)
        self.assertEqual(announcement.start_date.month, 5)
        self.assertEqual(announcement.start_date.day, 20)

    def test_edit_announcement(self):
        """edit an announcement"""
        announcement = models.Announcement.objects.create(
            preview="hi", user=self.local_user
        )
        view = views.Announcement.as_view()
        form = forms.AnnouncementForm(instance=announcement)
        form.data["preview"] = "hi hi"
        form.data["start_date"] = "2021-05-20"
        form.data["user"] = self.local_user.id

        request = self.factory.post("", form.data)
        request.user = self.local_user
        request.user.is_superuser = True

        view(request, announcement.id)

        announcement.refresh_from_db()
        self.assertEqual(announcement.preview, "hi hi")
        self.assertEqual(announcement.start_date.year, 2021)
        self.assertEqual(announcement.start_date.month, 5)
        self.assertEqual(announcement.start_date.day, 20)

    def test_delete_announcement(self):
        """delete an announcement"""
        announcement = models.Announcement.objects.create(
            preview="hi", user=self.local_user
        )
        view = views.delete_announcement

        request = self.factory.post("")
        request.user = self.local_user
        request.user.is_superuser = True

        view(request, announcement.id)

        self.assertFalse(models.Announcement.objects.exists())

    def test_view_announcement(self):
        """display announcement on other pages"""
        view = views.User.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, self.local_user.localname)

        self.assertIsInstance(result, TemplateResponse)
        result.render()
        self.assertEqual(result.status_code, 200)
