"""
Phoenix tracing initialization for LLM observability.

Phoenix automatically captures all OpenAI API calls (prompts, responses, tokens, latency)
and visualizes them in a web UI at http://localhost:6006.

Usage:
    Call init_phoenix_tracing() once at application startup, before any OpenAI calls.
    All subsequent OpenAI interactions will be automatically traced.

Environment variables:
    PHOENIX_COLLECTOR_ENDPOINT: Collector URL (default: http://localhost:6006)
    PHOENIX_PROJECT_NAME: Project name in UI (default: book-mate)
"""

import os
from phoenix.otel import register
from openinference.instrumentation.openai import OpenAIInstrumentor

_phoenix_initialized = False


def init_phoenix_tracing():
    """Initialize Phoenix tracing. Call once at startup."""
    global _phoenix_initialized

    if _phoenix_initialized:
        return

    try:
        collector_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:4317")
        project_name = os.getenv("PHOENIX_PROJECT_NAME", "book-mate")

        tracer_provider = register(
            project_name=project_name,
            endpoint=collector_endpoint,
        )

        OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

        _phoenix_initialized = True
        print(f"[PHOENIX] Initialized | Project: {project_name} | UI: {collector_endpoint}")

    except Exception as e:
        print(f"[PHOENIX] Failed to initialize: {e}")


def is_phoenix_enabled() -> bool:
    """Check if Phoenix tracing is enabled."""
    return _phoenix_initialized
