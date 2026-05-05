"""OpenTelemetry bootstrap — call configure_tracing(app, engine) once at startup."""
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from app.core.config import settings


def configure_tracing(app, sync_engine=None) -> None:
    if not settings.OTEL_ENABLED:
        return
    resource = Resource.create({
        SERVICE_NAME: settings.APP_NAME,
        SERVICE_VERSION: settings.APP_VERSION,
        "deployment.environment": settings.ENVIRONMENT,
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    if sync_engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=sync_engine, enable_commenter=True)
    RedisInstrumentor().instrument()
