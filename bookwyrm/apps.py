"""Do further startup configuration and initialization"""
import os
import urllib
import logging

from django.apps import AppConfig

from bookwyrm import settings

logger = logging.getLogger(__name__)


def download_file(url, destination):
    """Downloads a file to the given path"""
    try:
        # Ensure our destination directory exists
        os.makedirs(os.path.dirname(destination))
        with urllib.request.urlopen(url) as stream:
            with open(destination, "b+w") as outfile:
                outfile.write(stream.read())
    except (urllib.error.HTTPError, urllib.error.URLError):
        logger.info("Failed to download file %s", url)
    except OSError:
        logger.info("Couldn't open font file %s for writing", destination)
    except:  # pylint: disable=bare-except
        logger.info("Unknown error in file download")


class BookwyrmConfig(AppConfig):
    """Handles additional configuration"""

    name = "bookwyrm"
    verbose_name = "BookWyrm"

    # pylint: disable=no-self-use
    def ready(self):
        """set up OTLP and preview image files, if desired"""
        if settings.OTEL_EXPORTER_OTLP_ENDPOINT or settings.OTEL_EXPORTER_CONSOLE:
            # pylint: disable=import-outside-toplevel
            from bookwyrm.telemetry import open_telemetry

            open_telemetry.instrumentDjango()
            open_telemetry.instrumentPostgres()

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
