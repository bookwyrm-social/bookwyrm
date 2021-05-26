""" customize the info available in context for rendering templates """
from bookwyrm import models
from bookwyrm.settings import SITE_PATH, STATIC_URL, STATIC_PATH, MEDIA_URL, MEDIA_PATH


def site_settings(request):  # pylint: disable=unused-argument
    """include the custom info about the site"""
    return {
        "site": models.SiteSettings.objects.get(),
        "active_announcements": models.Announcement.active_announcements(),
        "site_path": SITE_PATH,
        "static_url": STATIC_URL,
        "media_url": MEDIA_URL,
        "static_path": STATIC_PATH,
        "media_path": MEDIA_PATH,
    }
