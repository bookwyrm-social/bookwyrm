""" Compile themes """
import os
from django.contrib.staticfiles.utils import get_files
from django.contrib.staticfiles.storage import StaticFilesStorage
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

import sass
from sass_processor.processor import SassProcessor

# pylint: disable=line-too-long
class Command(BaseCommand):
    """Compile themes"""

    help = "Compile theme scss files"

    # pylint: disable=no-self-use,unused-argument
    def handle(self, *args, **options):
        """compile themes"""
        storage = StaticFilesStorage()
        theme_files = list(get_files(storage, location="css/themes"))
        theme_files = [t for t in theme_files if t[-5:] == ".scss"]
        for filename in theme_files:
            path = storage.path(filename)
            content = sass.compile(
                filename=path,
                include_paths=SassProcessor.include_paths,
            )
            basename, _ = os.path.splitext(path)
            destination_filename = basename + ".css"
            print(f"saving f{destination_filename}")
            storage.save(destination_filename, ContentFile(content))
