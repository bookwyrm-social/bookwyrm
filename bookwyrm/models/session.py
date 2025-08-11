""" functions for managing user sessions """
import ua_parser

from django.contrib.sessions.backends.db import SessionStore
from django.db import models

from bookwyrm.models import User


class UserSession(models.Model):
    """A session for a logged-in user. We only use this model to save info about
    a logged-in session when the user first logs in, so users can remove sessions
    e.g. for devices they have lost."""

    user = models.ForeignKey("User", on_delete=models.PROTECT, related_name="sessions")
    session_key = models.CharField(max_length=40)
    created_date = models.DateTimeField(auto_now_add=True)
    operating_system = models.CharField(max_length=50)
    browser_type = models.CharField(max_length=50)
    # account for full IPv4-as-IPv6 strings, in case we need to
    ip_address = models.CharField(max_length=45)

    def logout(self):
        """log out the session and delete the UserSession"""

        s = SessionStore(session_key=self.session_key)
        s.delete()
        self.delete()


def create_user_session(
    user_id: int, session_key: str, ip_address: str, agent_string: str = ""
):
    """create a session object"""

    user = User.objects.get(id=user_id)
    os = ua_parser.parse_os(agent_string)
    user_agent = ua_parser.parse_user_agent(agent_string)
    system = getattr(os, "family", "Unknown")
    browser = getattr(user_agent, "family", "Unknown")

    sess = UserSession(
        user=user,
        session_key=session_key,
        operating_system=system,
        browser_type=browser,
        ip_address=ip_address,
    )
    sess.save()
