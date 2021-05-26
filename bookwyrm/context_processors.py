""" customize the info available in context for rendering templates """
from bookwyrm import models
from bookwyrm.settings import STATIC_URL, STATIC_PATH, MEDIA_URL, MEDIA_PATH


def site_settings(request):  # pylint: disable=unused-argument
    """include the custom info about the site"""
    request_protocol = "https://" if request.is_secure() else "http://"

    return {
        "site": models.SiteSettings.objects.get(),
        "active_announcements": models.Announcement.active_announcements(),
        "static_url": STATIC_URL,
        "media_url": MEDIA_URL,
        "static_path": STATIC_PATH,
        "media_path": MEDIA_PATH,
        "request_protocol": request_protocol,
    }
