""" testing models """
from django.test import TestCase

from bookwyrm import models
from bookwyrm.models import base_model
from bookwyrm.settings import DOMAIN


class BaseModel(TestCase):
    """ functionality shared across models """

    def test_remote_id(self):
        """ these should be generated """
        instance = base_model.BookWyrmModel()
        instance.id = 1
        expected = instance.get_remote_id()
        self.assertEqual(expected, "https://%s/bookwyrmmodel/1" % DOMAIN)

    def test_remote_id_with_user(self):
        """ format of remote id when there's a user object """
        user = models.User.objects.create_user(
            "mouse", "mouse@mouse.com", "mouseword", local=True, localname="mouse"
        )
        instance = base_model.BookWyrmModel()
        instance.user = user
        instance.id = 1
        expected = instance.get_remote_id()
        self.assertEqual(expected, "https://%s/user/mouse/bookwyrmmodel/1" % DOMAIN)

    def test_set_remote_id(self):
        """ this function sets remote ids after creation """
        # using Work because it BookWrymModel is abstract and this requires save
        # Work is a relatively not-fancy model.
        instance = models.Work.objects.create(title="work title")
        instance.remote_id = None
        base_model.set_remote_id(None, instance, True)
        self.assertEqual(
            instance.remote_id, "https://%s/book/%d" % (DOMAIN, instance.id)
        )

        # shouldn't set remote_id if it's not created
        instance.remote_id = None
        base_model.set_remote_id(None, instance, False)
        self.assertIsNone(instance.remote_id)
