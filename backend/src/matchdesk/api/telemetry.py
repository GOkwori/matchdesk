"""Traces and metrics to Azure Application Insights, when the host provides a connection.

Agent Framework already describes every model call in OpenTelemetry's generative-AI terms;
MatchDesk adds one span per planner question, live agent run and live replay stream, with
counts (intents, steps, verified cues, tokens) and never the question text or model output.
Without APPLICATIONINSIGHTS_CONNECTION_STRING nothing is exported and the spans are no-ops.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping

from opentelemetry import trace

_log = logging.getLogger("matchdesk.telemetry")
_ENV = "APPLICATIONINSIGHTS_CONNECTION_STRING"

tracer = trace.get_tracer("matchdesk")


def configure_telemetry(environ: Mapping[str, str] | None = None) -> bool:
    """Export to Application Insights if a connection string is set; report whether it is."""
    env = os.environ if environ is None else environ
    connection = (env.get(_ENV) or "").strip()
    if not connection:
        return False
    try:
        from agent_framework.observability import configure_otel_providers
        from azure.monitor.opentelemetry.exporter import (
            AzureMonitorMetricExporter,
            AzureMonitorTraceExporter,
        )

        configure_otel_providers(
            service_name="matchdesk-api",
            exporters=[
                AzureMonitorTraceExporter(connection_string=connection),
                AzureMonitorMetricExporter(connection_string=connection),
            ],
            # Prompts and replies stay out of telemetry; counts and timings go in.
            enable_sensitive_data=False,
        )
    except Exception:  # noqa: BLE001 - telemetry must never stop the API from starting
        _log.warning("Application Insights export could not be configured", exc_info=True)
        return False
    return True
