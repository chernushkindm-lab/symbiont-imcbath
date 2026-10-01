"""Versioned, JSON-serializable evidence contracts for M10.

No field can turn a preparation date or import timestamp into a result's
availability time. Null timestamps and null numbers are intentional evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SCHEMA_VERSION = "m10.evidence/1.0"
Classification = Literal["measured", "source-derived", "recalculated", "imputed", "assumed/synthetic", "predicted", "setpoint"]


@dataclass
class SourceLocator:
    source_id: str
    sheet: str
    row: int
    column: int | None = None
    cell: str | None = None


@dataclass
class Observation:
    observation_id: str
    run_id: str
    parameter_code: str
    raw_value: Any
    raw_unit: str | None
    value: float | None
    unit: str | None
    classification: Classification
    source_locator: dict
    event_time: str | None
    local_time: str | None
    basis: str
    matrix: str
    segment_id: str | None = None
    sample_id: str | None = None
    equipment_id: str = "EQ-BR-001"
    sensor_id: str | None = None
    availability_time: str | None = None
    timezone: str = "Asia/Yekaterinburg"
    calibration_version: str | None = None
    qc_flags: list[str] = field(default_factory=list)
    accepted: bool = True
    exclusion_reasons: list[str] = field(default_factory=list)
    lower_bound: float | None = None
    upper_bound: float | None = None
    censoring: str | None = None
    uncertainty: dict | None = None
    parent_observation_ids: list[str] = field(default_factory=list)
    equation_version: str | None = None
    information_cutoff: str | None = None
    forecast_origin: str | None = None
    horizon_h: float | None = None
    model_version: str | None = None
    scenario_version: str | None = None
    imputation_method: str | None = None
    validity_interval: list[str] | None = None

    def to_dict(self) -> dict:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        return result


@dataclass
class Run:
    run_id: str
    equipment_id: str = "EQ-BR-001"
    aliases: tuple[str, ...] = ("LAB005", "FA10", "F10", "Ф10", "YFC-10L")
    timezone: str = "Asia/Yekaterinburg"
    authoritative_volume_L: float = 10.0
    endpoint: str = "total_dry_residue"
    time_zero: str | None = None


@dataclass
class Segment:
    segment_id: str
    run_id: str
    start: str
    end: str | None
    event_ids: list[str] = field(default_factory=list)
    interpretation: str = "conservative interpolation boundary; not a confirmed biological phase"


@dataclass
class Sample:
    sample_id: str
    run_id: str
    matrix: str
    source_locator: dict
    event_time: str | None = None
    availability_time: str | None = None


@dataclass
class Equipment:
    equipment_id: str
    aliases: list[str]
    sensor_ids: list[str] = field(default_factory=list)


@dataclass
class Calibration:
    calibration_id: str
    source_id: str
    endpoint: str
    coefficient: float
    coefficient_unit: str
    supported_range: list[float]
    instrument: str | None = None
    availability_time: str | None = None


@dataclass
class FeedBatch:
    batch_id: str
    matrix: str
    source_locator: dict
    preparation_time: str | None = None
    connection_time: str | None = None
    recipe_observation_ids: list[str] = field(default_factory=list)


@dataclass
class DeliveryInterval:
    delivery_id: str
    run_id: str
    stream_id: str
    start: str
    end: str
    volume_L: float | None
    parent_observation_ids: list[str]
    status: str = "unverified"


@dataclass
class Event:
    event_id: str
    run_id: str
    kind: str
    source_locator: dict
    event_time: str | None
    description: str
    availability_time: str | None = None
    review_state: str = "requires_review"


@dataclass
class ModelRelease:
    release_id: str
    sha256: str
    source_uri: str
    audit_status: str


@dataclass
class Scenario:
    scenario_id: str
    model_release_id: str
    assumptions: list[str]
    bound_changes: list[dict]


@dataclass
class Forecast:
    forecast_id: str
    run_id: str
    forecast_origin: str
    information_cutoff: str
    horizon_h: float
    scenario_id: str
    model_release_id: str
    parent_observation_ids: list[str]


@dataclass
class Hypothesis:
    hypothesis_id: str
    claim: str
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    missing_evidence: list[str]
    review_state: str = "unreviewed"


def observation_schema() -> dict:
    """Portable minimum JSON Schema; dataclass fields define the full contract."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_VERSION,
        "type": "object",
        "required": ["observation_id", "run_id", "parameter_code", "raw_value", "value", "classification", "source_locator", "event_time", "availability_time", "basis", "matrix", "qc_flags", "parent_observation_ids"],
        "properties": {
            "classification": {"enum": ["measured", "source-derived", "recalculated", "imputed", "assumed/synthetic", "predicted", "setpoint"]},
            "value": {"type": ["number", "null"]},
            "event_time": {"type": ["string", "null"], "format": "date-time"},
            "availability_time": {"type": ["string", "null"], "format": "date-time"},
            "source_locator": {"type": "object", "required": ["source_id", "sheet", "row"]},
            "qc_flags": {"type": "array", "items": {"type": "string"}},
            "parent_observation_ids": {"type": "array", "items": {"type": "string"}},
        },
    }
