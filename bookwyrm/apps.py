from django.apps import AppConfig
from bookwyrm import settings


class BookwyrmConfig(AppConfig):
    name = "bookwyrm"
    verbose_name = "BookWyrm"

    def ready(self):
        if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            from bookwyrm.telemetry import open_telemetry

            open_telemetry.instrumentDjango()
