import functools
import os
from typing import Callable, Any

_tracing_initialized = False

def init_tracing(service_name: str = "agent-trust-ledger"):
    global _tracing_initialized
    if _tracing_initialized:
        return
    
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

        provider = TracerProvider()
        processor = BatchSpanProcessor(CloudTraceSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        _tracing_initialized = True
        print(f"[Tracing] Initialized OpenTelemetry Cloud Trace exporter for {service_name}.")
    except Exception as e:
        print(f"[Tracing] Cloud Trace export initialization skipped ({e}). Using no-op tracing.")

def get_tracer(name: str = "agent-trust-ledger"):
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return None

def traced_step(step_name: str):
    """Decorator to trace functions and attach OpenTelemetry spans."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            if tracer:
                with tracer.start_as_current_span(step_name) as span:
                    span.set_attribute("agent.step", step_name)
                    return func(*args, **kwargs)
            return func(*args, **kwargs)
        return wrapper
    return decorator
