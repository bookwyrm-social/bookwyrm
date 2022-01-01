from django.apps import AppConfig
from celerywyrm import settings


class CelerywyrmConfig(AppConfig):
    name = "celerywyrm"
    verbose_name = "BookWyrm Celery"

    def ready(self):
        if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            from bookwyrm.telemetry import open_telemetry

            open_telemetry.instrumentCelery()
