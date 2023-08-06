from django.apps import AppConfig
from celerywyrm import settings


class CelerywyrmConfig(AppConfig):
    name = "celerywyrm"
    verbose_name = "BookWyrm Celery"

    def ready(self) -> None:
        if settings.OTEL_EXPORTER_OTLP_ENDPOINT or settings.OTEL_EXPORTER_CONSOLE:
            from bookwyrm.telemetry import open_telemetry

            open_telemetry.instrumentCelery()
            open_telemetry.instrumentPostgres()
