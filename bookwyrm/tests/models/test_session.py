""" test session functions """
from importlib import import_module

from django.conf import settings
from django.test import TestCase

from bookwyrm import models


SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


class Session(TestCase):
    """test session tracking functions"""

    def setUp(self):
        """need a user and some pre-existing sessions"""

        self.user = models.User.objects.create_user(
            "mouse", "mouse@mouse.mouse", "password", local=True, localname="mouse"
        )

        self.session = SessionStore()
        self.session["_auth_user_id"] = self.user.id
        self.session.create()

        self.agent_string = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_4) \
        AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.104 Safari/537.36"

    def test_save_bookwyrm_session(self):
        """test saving session info to user"""

        self.assertEqual(models.UserSession.objects.count(), 0)

        models.create_user_session(
            user_id=self.user.id,
            session_key=self.session.session_key,
            ip_address="10.1.1.1",
            agent_string=self.agent_string,
        )

        self.assertEqual(models.UserSession.objects.count(), 1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.sessions.count(), 1)

        sess = models.UserSession.objects.first()

        self.assertEqual(sess.user, self.user)
        self.assertEqual(sess.session_key, self.session.session_key)
        self.assertEqual(sess.operating_system, "Mac OS X")
        self.assertEqual(sess.ip_address, "10.1.1.1")
        self.assertEqual(sess.browser_type, "Chrome")

    def test_refresh_user_sessions(self):
        """can we refresh the sessions list?"""

        models.create_user_session(
            user_id=self.user.id,
            session_key=self.session.session_key,
            ip_address="10.1.1.1",
            agent_string=self.agent_string,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.sessions.count(), 1)

        self.session.delete()
        self.assertFalse(self.session.exists(session_key=self.session.session_key))

        self.user.refresh_user_sessions()
        self.assertEqual(self.user.sessions.count(), 0)

    def test_logout(self):
        """does logout clear both sessions?"""

        models.create_user_session(
            user_id=self.user.id,
            session_key=self.session.session_key,
            ip_address="10.1.1.1",
            agent_string=self.agent_string,
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.sessions.count(), 1)
        self.assertTrue(self.session.exists(session_key=self.session.session_key))

        sess = self.user.sessions.first()
        sess.logout()

        self.assertFalse(self.session.exists(session_key=self.session.session_key))
        self.user.refresh_from_db()
        self.assertEqual(self.user.sessions.count(), 0)
