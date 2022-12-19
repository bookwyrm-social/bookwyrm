""" Our own command to all scss themes """
import glob
import os

import sass

from django.core.management.base import BaseCommand

from sass_processor.apps import APPS_INCLUDE_DIRS
from sass_processor.processor import SassProcessor
from sass_processor.utils import get_custom_functions

from bookwyrm import settings


class Command(BaseCommand):
    """command-line options"""

    help = "SCSS compile all BookWyrm themes"

    # pylint: disable=unused-argument
    def handle(self, *args, **options):
        """compile"""
        themes_dir = os.path.join(
            settings.BASE_DIR, "bookwyrm", "static", "css", "themes", "*.scss"
        )
        for theme_scss in glob.glob(themes_dir):
            basename, _ = os.path.splitext(theme_scss)
            theme_css = f"{basename}.css"
            self.compile_sass(theme_scss, theme_css)

    def compile_sass(self, sass_path, css_path):
        compile_kwargs = {
            "filename": sass_path,
            "include_paths": SassProcessor.include_paths + APPS_INCLUDE_DIRS,
            "custom_functions": get_custom_functions(),
            "precision": getattr(settings, "SASS_PRECISION", 8),
            "output_style": getattr(
                settings,
                "SASS_OUTPUT_STYLE",
                "nested" if settings.DEBUG else "compressed",
            ),
        }

        content = sass.compile(**compile_kwargs)
        with open(css_path, "w") as f:
            f.write(content)
        self.stdout.write("Compiled SASS/SCSS file: '{0}'\n".format(sass_path))
