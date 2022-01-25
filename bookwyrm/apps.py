import os
import urllib
import logging

from django.apps import AppConfig

from bookwyrm import settings

logger = logging.getLogger(__name__)

def download_file(url, destination):
    try:
        stream = urllib.request.urlopen(url)
        with open(destination, "b+w") as f:
            f.write(stream.read())
    except (urllib.error.HTTPError, urllib.error.URLError):
        logger.error("Failed to download file %s", url)


class BookwyrmConfig(AppConfig):
    name = "bookwyrm"
    verbose_name = "BookWyrm"

    def ready(self):
        if settings.ENABLE_PREVIEW_IMAGES and settings.FONTS:
            # Download any fonts that we don't have yet
            logger.debug("Downloading fonts..")
            for name, config in settings.FONTS.items():
                font_path = os.path.join(
                    settings.FONT_DIR, config["directory"], config["filename"]
                )

                if "url" in config and not os.path.exists(font_path):
                    logger.info("Just a sec, downloading %s", name)
                    download_file(config["url"], font_path)
