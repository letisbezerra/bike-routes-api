"""Local-only technical demo (docker-compose --profile observability),
never enabled in production — see README "Observability demo". Gated
behind settings.enable_observability, off by default."""

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator

from app.shared.config import APP_NAME

_TEMPO_OTLP_ENDPOINT = "localhost:4317"


def setup_observability(app: FastAPI) -> None:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: APP_NAME}))
    # insecure=True: Tempo's OTLP receiver here has no TLS configured (local
    # demo only) — the exporter defaults to a secure channel and fails
    # silently in its background thread without this.
    exporter = OTLPSpanExporter(endpoint=_TEMPO_OTLP_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)

    from app.shared.database import engine

    SQLAlchemyInstrumentor().instrument(engine=engine)
