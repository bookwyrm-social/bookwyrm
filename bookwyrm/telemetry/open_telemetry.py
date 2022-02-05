from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))


def instrumentDjango():
    from opentelemetry.instrumentation.django import DjangoInstrumentor

    DjangoInstrumentor().instrument()


def instrumentCelery():
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from celery.signals import worker_process_init

    @worker_process_init.connect(weak=False)
    def init_celery_tracing(*args, **kwargs):
        CeleryInstrumentor().instrument()
