"""Event metrics. One aggregation path for all three."""

from __future__ import annotations

from enum import Enum


class Metric(str, Enum):
    CALL_RECEIVED = "call_received"
    LEAD_CREATED = "lead_created"
    APPOINTMENT_SET = "appointment_set"


METRIC_LABELS: dict[Metric, str] = {
    Metric.CALL_RECEIVED: "Calls received",
    Metric.LEAD_CREATED: "Leads created",
    Metric.APPOINTMENT_SET: "Appointments set",
}
