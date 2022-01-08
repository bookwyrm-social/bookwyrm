class Strategy:
    """
    A strategy that generates the image on source saved (Optimistic),
    but also on demand, for old images (JustInTime).
    """

    def on_source_saved(self, file):
        file.generate()

    def on_existence_required(self, file):
        file.generate()

    def on_content_required(self, file):
        file.generate()
