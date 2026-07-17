"""test for app action functionality"""

from django.contrib.auth.models import Group, Permission
from django.template.response import TemplateResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from bookwyrm import models, views
from bookwyrm.views.admin.data_quality import get_diff_string
from bookwyrm.management.commands import initdb
from bookwyrm.tests.validate_html import validate_html


class AutomodViews(TestCase):
    """every response to a get request, html or json"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        cls.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        initdb.init_groups()
        initdb.init_permissions()
        group = Group.objects.get(name="admin")
        cls.local_user.groups.set([group])

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_data_quality_get(self):
        """there are so many views, this just makes sure it LOADS"""
        schedule = IntervalSchedule.objects.create(every=1, period="days")
        PeriodicTask.objects.create(
            interval=schedule,
            name="dedupe-task",
            task="bookwyrm.models.housekeeping.mark_duplicate_data_task",
        )
        view = views.DataQuality.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_data_quality_get_empty(self):
        """there are so many views, this just makes sure it LOADS"""
        view = views.DataQuality.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)


class ManualMergeViews(TestCase):
    """every response to a get request, html or json"""

    @classmethod
    def setUpTestData(cls):
        """we need basic test data and mocks"""
        cls.local_user = models.User.objects.create_user(
            "mouse@local.com",
            "mouse@mouse.mouse",
            "password",
            local=True,
            localname="mouse",
        )
        perm = Permission.objects.get(codename="manage_data")
        cls.local_user.user_permissions.add(perm)

        cls.work_one = models.Work.objects.create(
            title="Frog and Toad are friends", openlibrary_key="OL1234"
        )
        cls.work_two = models.Work.objects.create(
            title="Frog and Toad are friends", openlibrary_key="OL1234"
        )

        cls.edition_one = models.Edition.objects.create(
            title="Frog and Toad are friends",
            finna_key="F1234",
            parent_work=cls.work_one,
        )
        cls.edition_two = models.Edition.objects.create(
            title="Frog and Toad are friends",
            finna_key="F1234",
            parent_work=cls.work_two,
        )

        cls.author_one = models.Author.objects.create(
            name="Arnold Lobel", isni="0000000081603022"
        )
        cls.author_two = models.Author.objects.create(
            name="لوبيل، أرنولد،", isni="0000000081603022"
        )

        cls.series_one = models.Series.objects.create(
            name="Frog and Toad", wikidata="Q5505227", user=cls.local_user
        )
        cls.series_two = models.Series.objects.create(
            name="Kvak a Žbluňk", wikidata="Q5505227", user=cls.local_user
        )

    def setUp(self):
        """individual test setup"""
        self.factory = RequestFactory()

    def test_merge_data_get_loads(self):
        """does the page load?"""
        view = views.MergeData.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_merge_data_gets_data(self):
        """does the data load?"""
        view = views.MergeData.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        for model in [models.Edition, models.Work, models.Author, models.Series]:
            model.mark_merge_candidates()

        result = view(request)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        self.assertEqual(result.context_data["works_count"], 1)
        self.assertEqual(result.context_data["editions_count"], 1)
        self.assertEqual(result.context_data["authors_count"], 1)
        self.assertEqual(result.context_data["series_count"], 1)

    def test_merge_data_get_editions(self):
        """does the edition data load?"""

        models.Edition.mark_merge_candidates()
        view = views.MergeData.as_view()
        request = self.factory.get("/settings/manage-data/merge?merge_type=edition")
        request.user = self.local_user
        result = view(request)

        self.assertEqual(result.context_data["editions"][0].finna_key, "F1234")

    def test_manual_merge_get(self):
        """does the manual merge page load?"""

        models.Edition.mark_merge_candidates()
        view = views.ManualMerge.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, "edition", self.edition_one.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

    def test_manual_merge_get_data(self):
        """does the manual merge data load?"""

        models.Edition.mark_merge_candidates()
        view = views.ManualMerge.as_view()
        request = self.factory.get("")
        request.user = self.local_user

        result = view(request, "edition", self.edition_one.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        self.assertEqual(result.context_data["canonical"].id, self.edition_one.id)
        self.assertEqual(len(result.context_data["objects"]), 2)
        self.assertEqual(result.context_data["objects"][1].id, self.edition_two.id)

    def test_manual_merge_post_data(self):
        """does POSTing the data work as expected?"""

        models.Edition.mark_merge_candidates()
        view = views.ManualMerge.as_view()
        request = self.factory.post("")
        request.user = self.local_user

        # does it load a template response
        result = view(request, "edition", self.edition_one.id)
        self.assertIsInstance(result, TemplateResponse)
        validate_html(result.render())
        self.assertEqual(result.status_code, 200)

        # does it load the right template
        self.assertEqual(
            result.template_name, "settings/manage-data/confirm-merge.html"
        )

    def test_confirm_manual_merge(self):
        """does the data come through correctly?"""

        models.Edition.mark_merge_candidates()
        view = views.confirm_manual_merge
        data = {"subtitle": "test 1234", "pages": "999"}
        request = self.factory.post("", data)
        request.user = self.local_user
        result = view(request, "edition", self.edition_one.id)

        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, self.edition_one.remote_id)

        self.edition_one.refresh_from_db()
        self.assertEqual(self.edition_one.title, "Frog and Toad are friends")
        self.assertEqual(self.edition_one.subtitle, "test 1234")
        self.assertEqual(self.edition_one.pages, 999)

    def test_get_diff_string(self):
        """does the correct diff string get returned?"""

        canonical = "I am candid"
        candidate = "I candidate"
        return_string = "I<span class='has-background-danger-light has-text-danger has-text-weight-semibold'><strike> </strike></span><span class='has-background-danger-light has-text-danger has-text-weight-semibold'><strike>a</strike></span><span class='has-background-danger-light has-text-danger has-text-weight-semibold'><strike>m</strike></span> candid<span class='has-background-success-light has-text-success has-text-weight-semibold'>a</span><span class='has-background-success-light has-text-success has-text-weight-semibold'>t</span><span class='has-background-success-light has-text-success has-text-weight-semibold'>e</span>"

        result = get_diff_string(canonical, candidate)
        self.assertEqual(result, return_string)
