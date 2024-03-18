""" test for app action functionality """
from unittest.mock import patch
import responses
from responses import matchers

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django.utils import timezone

from bookwyrm import forms, models, views
from bookwyrm.views.books.edit_book import add_authors
from bookwyrm.tests.validate_html import validate_html
from bookwyrm.tests.views.books.test_book import _setup_cover_url


class EditBookViews(TestCase):
    """books books books"""

    @classmethod
    def setUpTestData(self):  # pylint: disable=bad-classmethod-argument
        """we need basic test data and mocks"""
        with patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"), patch(
            "bookwyrm.activitystreams.populate_stream_task.delay"
        ), patch("bookwyrm.lists_stream.populate_lists_task.delay"):
            self.local_user = models.User.objects.create_user(
                "mouse@local.com",
                "mouse@mouse.com",
                "mouseword",
                local=True,
                localname="mouse",
                remote_id="https://example.com/users/mouse",
            )
        self.group = Group.objects.create(name="editor")
        self.group.permissions.add(
            Permission.objects.create(
                name="edit_book",
                codename="edit_book",
                content_type=ContentType.objects.get_for_model(models.User),
            ).id
        )
        self.work = models.Work.objects.create(title="Test Work")
        self.book = models.Edition.objects.create(
            title="Example Edition",
            remote_id="https://example.com/book/1",
            parent_work=self.work,
        )
        models.SiteSettings.objects.create()

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()
        # pylint: disable=line-too-long
        self.authors_body = "<?xml version='1.0' encoding='UTF-8' ?><?xml-stylesheet type='text/xsl' href='http://isni.oclc.org/sru/DB=1.2/?xsl=searchRetrieveResponse' ?><srw:searchRetrieveResponse xmlns:srw='http://www.loc.gov/zing/srw/' xmlns:dc='http://purl.org/dc/elements/1.1/' xmlns:diag='http://www.loc.gov/zing/srw/diagnostic/' xmlns:xcql='http://www.loc.gov/zing/cql/xcql/'><srw:version>1.1</srw:version><srw:records><srw:record><isniUnformatted>0000000084510024</isniUnformatted></srw:record></srw:records></srw:searchRetrieveResponse>"
        self.author_body = "<?xml version='1.0' encoding='UTF-8' ?><?xml-stylesheet type='text/xsl' href='http://isni.oclc.org/sru/DB=1.2/?xsl=searchRetrieveResponse' ?><srw:searchRetrieveResponse xmlns:srw='http://www.loc.gov/zing/srw/' xmlns:dc='http://purl.org/dc/elements/1.1/' xmlns:diag='http://www.loc.gov/zing/srw/diagnostic/' xmlns:xcql='http://www.loc.gov/zing/cql/xcql/'><srw:records><srw:record><srw:recordData><responseRecord><ISNIAssigned><isniUnformatted>0000000084510024</isniUnformatted><isniURI>https://isni.org/isni/0000000084510024</isniURI><dataConfidence>60</dataConfidence><ISNIMetadata><identity><personOrFiction><personalName><surname>Catherine Amy Dawson Scott</surname><nameTitle>poet and novelist</nameTitle><nameUse>public</nameUse><source>VIAF</source><source>WKP</source><subsourceIdentifier>Q544961</subsourceIdentifier></personalName><personalName><forename>C. A.</forename><surname>Dawson Scott</surname><marcDate>1865-1934</marcDate><nameUse>public</nameUse><source>VIAF</source><source>NLP</source><subsourceIdentifier>a28927850</subsourceIdentifier></personalName><sources><codeOfSource>VIAF</codeOfSource><sourceIdentifier>45886165</sourceIdentifier><reference><class>ALL</class><role>CRE</role><URI>http://viaf.org/viaf/45886165</URI></reference></sources><externalInformation><information>Wikipedia</information><URI>https://en.wikipedia.org/wiki/Catherine_Amy_Dawson_Scott</URI></externalInformation></ISNIMetadata></ISNIAssigned></responseRecord></srw:recordData></srw:record></srw:records></srw:searchRetrieveResponse>"

        responses.get(
            "http://isni.oclc.org/sru/",
            content_type="text/xml",
            match=[
                matchers.query_param_matcher(
                    {"query": 'pica.na="Sappho"'}, strict_match=False
                )
            ],
            body=self.authors_body,
        )

        responses.get(
            "http://isni.oclc.org/sru/",
            content_type="text/xml",
            match=[
                matchers.query_param_matcher(
                    {"query": 'pica.na="Some Guy"'}, strict_match=False
                )
            ],
            body=self.authors_body,
        )

        responses.get(
            "http://isni.oclc.org/sru/",
            content_type="text/xml",
            match=[
                matchers.query_param_matcher(
                    {"query": 'pica.isn="0000000084510024"'}, strict_match=False
                )
            ],
            body=self.author_body,
        )

    def test_edit_book_get(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.EditBook.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True
        result = view(request, self.book.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_edit_book_post(self):
        """lets a user edit a book"""
        view = views.EditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm(instance=self.book)
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            view(request, self.book.id)

        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "New Title")

    def test_edit_book_post_invalid(self):
        """book form is invalid"""
        view = views.EditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm(instance=self.book)
        form.data["title"] = ""
        form.data["last_edited_by"] = self.local_user.id
        form.data["cover-url"] = "http://local.host/cover.jpg"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request, self.book.id)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        # Title is unchanged
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "Example Edition")
        # transient field values are set correctly
        self.assertEqual(
            result.context_data["cover_url"], "http://local.host/cover.jpg"
        )

    @responses.activate
    def test_edit_book_add_author(self):
        """lets a user edit a book with new authors"""
        view = views.EditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm(instance=self.book)
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        form.data["add_author"] = "Sappho"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request, self.book.id)
        validate_html(result.render())

        # the changes haven't been saved yet
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "Example Edition")

    def test_edit_book_add_new_author_confirm(self):
        """lets a user edit a book confirmed with new authors"""
        view = views.ConfirmEditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm(instance=self.book)
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        form.data["author-match-count"] = 1
        form.data["author_match-0"] = "Sappho"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            view(request, self.book.id)

        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "New Title")
        self.assertEqual(self.book.authors.first().name, "Sappho")

    def test_edit_book_remove_author(self):
        """remove an author from a book"""
        author = models.Author.objects.create(name="Sappho")
        self.book.authors.add(author)
        form = forms.EditionForm(instance=self.book)
        view = views.EditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm(instance=self.book)
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        form.data["remove_authors"] = [author.id]
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            view(request, self.book.id)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "New Title")
        self.assertFalse(self.book.authors.exists())

    def test_create_book(self):
        """create an entirely new book and work"""
        view = views.ConfirmEditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm()
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request)

        book = models.Edition.objects.get(title="New Title")
        self.assertEqual(book.parent_work.title, "New Title")

    def test_published_date_timezone(self):
        """user timezone does not affect publication year"""
        # https://github.com/bookwyrm-social/bookwyrm/issues/3028
        self.local_user.groups.add(self.group)
        create_book = views.CreateBook.as_view()
        book_data = {
            "title": "January 1st test",
            "parent_work": self.work.id,
            "last_edited_by": self.local_user.id,
            "published_date_day": "1",
            "published_date_month": "1",
            "published_date_year": "2020",
        }
        request = self.factory.post("", book_data)
        request.user = self.local_user

        with timezone.override("Europe/Madrid"):  # Ahead of UTC.
            create_book(request)

        book = models.Edition.objects.get(title="January 1st test")
        self.assertEqual(book.edition_info, "2020")

    def test_partial_published_dates(self):
        """create a book with partial publication dates, then update them"""
        self.local_user.groups.add(self.group)
        book_data = {
            "title": "An Edition With Dates",
            "parent_work": self.work.id,
            "last_edited_by": self.local_user.id,
        }
        initial_pub_dates = {
            # published_date: 2023-01-01
            "published_date_day": "1",
            "published_date_month": "01",
            "published_date_year": "2023",
            # first_published_date: 1995
            "first_published_date_day": "",
            "first_published_date_month": "",
            "first_published_date_year": "1995",
        }
        updated_pub_dates = {
            # published_date: full -> year-only
            "published_date_day": "",
            "published_date_month": "",
            "published_date_year": "2023",
            # first_published_date: add month
            "first_published_date_day": "",
            "first_published_date_month": "03",
            "first_published_date_year": "1995",
        }

        # create book
        create_book = views.CreateBook.as_view()
        request = self.factory.post("", book_data | initial_pub_dates)
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            create_book(request)

        book = models.Edition.objects.get(title="An Edition With Dates")

        self.assertEqual("2023-01-01", book.published_date.partial_isoformat())
        self.assertEqual("1995", book.first_published_date.partial_isoformat())

        self.assertTrue(book.published_date.has_day)
        self.assertTrue(book.published_date.has_month)

        self.assertFalse(book.first_published_date.has_day)
        self.assertFalse(book.first_published_date.has_month)

        # now edit publication dates
        edit_book = views.ConfirmEditBook.as_view()
        request = self.factory.post("", book_data | updated_pub_dates)
        request.user = self.local_user

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            result = edit_book(request, book.id)

        self.assertEqual(result.status_code, 302)

        book.refresh_from_db()

        self.assertEqual("2023", book.published_date.partial_isoformat())
        self.assertEqual("1995-03", book.first_published_date.partial_isoformat())

        self.assertFalse(book.published_date.has_day)
        self.assertFalse(book.published_date.has_month)

        self.assertFalse(book.first_published_date.has_day)
        self.assertTrue(book.first_published_date.has_month)

    def test_create_book_existing_work(self):
        """create an entirely new book and work"""
        view = views.ConfirmEditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm()
        form.data["title"] = "New Title"
        form.data["parent_work"] = self.work.id
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request)

        book = models.Edition.objects.get(title="New Title")
        self.assertEqual(book.parent_work, self.work)

    def test_create_book_with_author(self):
        """create an entirely new book and work"""
        view = views.ConfirmEditBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm()
        form.data["title"] = "New Title"
        form.data["author-match-count"] = "1"
        form.data["author_match-0"] = "Sappho"
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user

        view(request)

        book = models.Edition.objects.get(title="New Title")
        self.assertEqual(book.parent_work.title, "New Title")
        self.assertEqual(book.authors.first().name, "Sappho")
        self.assertEqual(book.authors.first(), book.parent_work.authors.first())

    @responses.activate
    def test_create_book_upload_cover_url(self):
        """create an entirely new book and work with cover url"""
        self.assertFalse(self.book.cover)
        self.local_user.groups.add(self.group)
        cover_url = _setup_cover_url()

        form = forms.EditionForm()
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        form.data["cover-url"] = cover_url
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch(
            "bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"
        ) as delay_mock:
            views.upload_cover(request, self.book.id)
            self.assertEqual(delay_mock.call_count, 1)

        self.book.refresh_from_db()
        self.assertTrue(self.book.cover)

    @responses.activate
    def test_add_authors_helper(self):
        """converts form input into author matches"""
        form = forms.EditionForm(instance=self.book)
        form.data["title"] = "New Title"
        form.data["last_edited_by"] = self.local_user.id
        form.data["add_author"] = ["Sappho", "Some Guy"]
        request = self.factory.post("", form.data)
        request.user = self.local_user

        with patch("bookwyrm.utils.isni.find_authors_by_name") as mock:
            mock.return_value = []
            result = add_authors(request, form.data)

        self.assertTrue(result["confirm_mode"])
        self.assertEqual(result["add_author"], ["Sappho", "Some Guy"])
        self.assertEqual(len(result["author_matches"]), 2)
        self.assertEqual(result["author_matches"][0]["name"], "Sappho")
        self.assertEqual(result["author_matches"][1]["name"], "Some Guy")

    def test_create_book_get(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.CreateBook.as_view()
        request = self.factory.get("")
        request.user = self.local_user
        request.user.is_superuser = True
        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_create_book_post_existing_work(self):
        """Adding an edition to an existing work"""
        author = models.Author.objects.create(name="Sappho")
        view = views.CreateBook.as_view()
        form = forms.EditionForm()
        form.data["title"] = "A Title"
        form.data["parent_work"] = self.work.id
        form.data["authors"] = [author.id]
        form.data["last_edited_by"] = self.local_user.id
        request = self.factory.post("", form.data)
        request.user = self.local_user
        request.user.is_superuser = True

        with patch("bookwyrm.models.activitypub_mixin.broadcast_task.apply_async"):
            result = view(request)
        self.assertEqual(result.status_code, 302)

        new_edition = models.Edition.objects.get(title="A Title")
        self.assertEqual(new_edition.parent_work, self.work)
        self.assertEqual(new_edition.authors.first(), author)

    def test_create_book_post_invalid(self):
        """book form is invalid"""
        view = views.CreateBook.as_view()
        self.local_user.groups.add(self.group)
        form = forms.EditionForm(instance=self.book)
        form.data["title"] = ""
        form.data["last_edited_by"] = self.local_user.id
        form.data["cover-url"] = "http://local.host/cover.jpg"
        request = self.factory.post("", form.data)
        request.user = self.local_user

        result = view(request)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)
        # transient field values are set correctly
        self.assertEqual(
            result.context_data["cover_url"], "http://local.host/cover.jpg"
        )
