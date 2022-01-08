"""thumbnail generation strategy for django-imagekit"""


class Strategy:
    """
    A strategy that generates the image on source saved (Optimistic),
    but also on demand, for old images (JustInTime).
    """

    def on_source_saved(self, file):  # pylint: disable=no-self-use
        """What happens on source saved"""
        file.generate()

    def on_existence_required(self, file):  # pylint: disable=no-self-use
        """What happens on existence required"""
        file.generate()

    def on_content_required(self, file):  # pylint: disable=no-self-use
        """What happens on content required"""
        file.generate()
