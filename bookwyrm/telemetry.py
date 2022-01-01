def InstallOpenTelemetry():
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    DjangoInstrumentor().instrument()
    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
