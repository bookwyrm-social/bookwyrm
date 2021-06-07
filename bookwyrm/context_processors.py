""" customize the info available in context for rendering templates """
from bookwyrm import models, settings


def site_settings(request):  # pylint: disable=unused-argument
    """include the custom info about the site"""
    return {
        "site": models.SiteSettings.objects.get(),
        "active_announcements": models.Announcement.active_announcements(),
        "enable_thumbnail_generation": settings.ENABLE_THUMBNAIL_GENERATION,
    }
