from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider, Tracer
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from bookwyrm import settings

trace.set_tracer_provider(TracerProvider())
if settings.OTEL_EXPORTER_CONSOLE:
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(ConsoleSpanExporter())
    )
elif settings.OTEL_EXPORTER_OTLP_ENDPOINT:
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter())
    )


def instrumentDjango() -> None:
    from opentelemetry.instrumentation.django import DjangoInstrumentor

    DjangoInstrumentor().instrument()


def instrumentPostgres() -> None:
    from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

    Psycopg2Instrumentor().instrument()


def instrumentCelery() -> None:
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from celery.signals import worker_process_init

    @worker_process_init.connect(weak=False)
    def init_celery_tracing(*args, **kwargs):
        CeleryInstrumentor().instrument()


def tracer() -> Tracer:
    return trace.get_tracer(__name__)
