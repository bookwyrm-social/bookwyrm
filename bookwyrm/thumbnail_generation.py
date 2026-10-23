"""thumbnail generation strategy for django-imagekit"""

import logging
from PIL import UnidentifiedImageError

logger = logging.getLogger(__name__)


class Strategy:
    """
    A strategy that generates the image on source saved (Optimistic),
    but also on demand, for old images (JustInTime).
    """

    def on_source_saved(self, file):
        """What happens on source saved"""
        self._generate(file)

    def on_existence_required(self, file):
        """What happens on existence required"""
        self._generate(file)

    def on_content_required(self, file):
        """What happens on content required"""
        self._generate(file)

    @staticmethod
    def _generate(file):
        """Safely generate a thumbnail file, ignoring corrupted or unidentifiable images"""
        try:
            file.generate()
        except (OSError, UnidentifiedImageError, ValueError) as err:
            logger.warning("Failed to generate thumbnail for %s: %s", file, err)
