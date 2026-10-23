"""Optional OpenTelemetry traces for every model call, using the GenAI semantic conventions.

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set and the `otel` extra is installed; then `emit()` is a no-op
and nothing else in ReqTrace changes. Point it at any OTLP receiver (Grafana Alloy, Grafana Cloud, Tempo):

    pip install 'reqtrace[otel]'
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 reqtrace run
"""
import os
from contextlib import contextmanager

_tracer = None
_root = None  # parent context for spans emitted from worker threads (parse runs chunks in parallel)

if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        _provider = TracerProvider(resource=Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "reqtrace")}))
        _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))  # endpoint + headers come from OTEL_* env
        _tracer = _provider.get_tracer("reqtrace")
    except ImportError:
        pass  # extra not installed: stay off


@contextmanager
def run_span(name="reqtrace.run", **attrs):
    """Root span for one pipeline run; also flushes on exit so a short CLI process does not lose spans."""
    global _root
    if not _tracer:
        yield
        return
    with _tracer.start_as_current_span(name, attributes=attrs) as span:
        _root = trace.set_span_in_context(span)
        try:
            yield
        finally:
            _root = None
    _provider.force_flush()


def emit(row: dict, start_s: float, end_s: float):
    """One span per model attempt, built from the llm_log row (so the trace and the log never disagree)."""
    if not _tracer:
        return
    span = _tracer.start_span(
        f"chat {row['model']}", context=_root, start_time=int(start_s * 1e9),
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": row["backend"],
            "gen_ai.request.model": row["model"],
            "gen_ai.usage.input_tokens": row["input_tokens"],
            "gen_ai.usage.output_tokens": row["output_tokens"],
            "reqtrace.task": row["task"],
            "reqtrace.attempt": row["attempt"],
            "reqtrace.valid": row["valid"],
            "reqtrace.cost_usd_list": row.get("cost_usd_list") or 0.0,
            "reqtrace.replayed": bool(row.get("replayed")),
        })
    if not row["valid"]:
        span.set_status(trace.Status(trace.StatusCode.ERROR, (row["error"] or "")[:200]))
    span.end(end_time=int(end_s * 1e9))


def traced(fn):
    """Decorator: run `fn` inside the root span."""
    import functools

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        with run_span(backend=str(kw.get("backend")), mock=bool(kw.get("mock"))):
            return fn(*a, **kw)
    return wrapper
