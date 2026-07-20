from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from astro_abm_api.models.portability import ScenarioExportEnvelope
from astro_abm_api.models.report import ScenarioReport


SCENARIO_EXPORT_SCHEMA_VERSION = "astro-abm-worldline-v1"


def canonical_report_bytes(report_data: dict[str, Any]) -> bytes:
    return json.dumps(
        report_data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def content_hash(report_data: dict[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(canonical_report_bytes(report_data)).hexdigest()}"


def export_scenario(report: ScenarioReport) -> ScenarioExportEnvelope:
    report_data = report.model_dump(mode="json")
    return ScenarioExportEnvelope(
        schema_version=SCENARIO_EXPORT_SCHEMA_VERSION,
        exported_at=datetime.now(UTC),
        content_hash=content_hash(report_data),
        report=report_data,
        notes=[
            "Canonical JSON uses sorted UTF-8 keys and compact separators.",
            "The hash verifies this exported artifact; it is not an investment or prediction credential.",
        ],
    )


def validate_export(envelope: ScenarioExportEnvelope) -> ScenarioReport:
    if envelope.schema_version != SCENARIO_EXPORT_SCHEMA_VERSION:
        raise ValueError("unsupported scenario export schema version")
    if content_hash(envelope.report) != envelope.content_hash:
        raise ValueError("scenario export content hash mismatch")
    return ScenarioReport.model_validate(envelope.report)
