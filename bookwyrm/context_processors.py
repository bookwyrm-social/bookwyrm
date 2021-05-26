""" customize the info available in context for rendering templates """
from bookwyrm import models
from bookwyrm.settings import DOMAIN


def site_settings(request):  # pylint: disable=unused-argument
    """include the custom info about the site"""
    return {
        "site": models.SiteSettings.objects.get(),
        "active_announcements": models.Announcement.active_announcements(),
        "site_path": "https://%s" % DOMAIN,
    }
