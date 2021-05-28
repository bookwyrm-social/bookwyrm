""" customize the info available in context for rendering templates """
from bookwyrm import models, settings


def site_settings(request):  # pylint: disable=unused-argument
    """include the custom info about the site"""
    request_protocol = "https://"
    if not request.is_secure():
        request_protocol = "http://"

    return {
        "site": models.SiteSettings.objects.get(),
        "active_announcements": models.Announcement.active_announcements(),
        "static_url": settings.STATIC_URL,
        "media_url": settings.MEDIA_URL,
        "static_path": settings.STATIC_PATH,
        "media_path": settings.MEDIA_PATH,
        "preview_images_enabled": settings.ENABLE_PREVIEW_IMAGES,
        "request_protocol": request_protocol,
    }
