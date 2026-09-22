from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from astro_abm.marksix import default_db_path


def _connect() -> sqlite3.Connection:
    path = default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS marksix_llm_worldlines (
          library_id TEXT PRIMARY KEY,
          worldline_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          draw_date TEXT NOT NULL,
          numbers_json TEXT NOT NULL,
          extra_number INTEGER NOT NULL,
          language TEXT NOT NULL,
          provider TEXT NOT NULL,
          model TEXT NOT NULL,
          generation_mode TEXT NOT NULL,
          rationale TEXT NOT NULL,
          confidence TEXT NOT NULL,
          caveats_json TEXT NOT NULL,
          disclaimer TEXT NOT NULL,
          astro_context_json TEXT NOT NULL,
          prompt_context_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_marksix_llm_worldlines_created
          ON marksix_llm_worldlines(created_at DESC);
        """
    )
    return connection


def _public_prompt_context(value: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "next_draw_date",
        "astro_context_type",
        "historical_condition",
        "condition_draws",
        "selected_astro_features",
        "included_astro_sections",
    )
    return {key: value[key] for key in allowed if key in value}


def save_public_llm_worldline(result: dict[str, Any], *, language: str) -> str:
    worldline = result["worldline"]
    draw = worldline["draws"][0]
    if worldline.get("generation_mode") != "llm_astro_entertainment_v1":
        raise ValueError("Only LLM Mark Six entertainment worldlines can enter the public library")
    if result.get("network_call_performed") is not True:
        raise ValueError("Only completed LLM calls can enter the public library")

    created_at = datetime.now(UTC)
    library_id = f"marksix-public-{created_at:%Y%m%d%H%M%S}-{uuid4().hex[:10]}"
    prompt_context = _public_prompt_context(dict(result.get("prompt_context") or {}))
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO marksix_llm_worldlines (
              library_id, worldline_id, created_at, draw_date, numbers_json,
              extra_number, language, provider, model, generation_mode,
              rationale, confidence, caveats_json, disclaimer,
              astro_context_json, prompt_context_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                library_id,
                worldline["worldline_id"],
                created_at.isoformat(),
                draw["date"],
                json.dumps(draw["numbers"], separators=(",", ":")),
                draw["extra_number"],
                language,
                result["provider"],
                result["model"],
                worldline["generation_mode"],
                result["rationale"],
                result["confidence"],
                json.dumps(result.get("caveats") or [], ensure_ascii=False, separators=(",", ":")),
                worldline["disclaimer"],
                json.dumps(worldline.get("astro_context") or {}, ensure_ascii=False, separators=(",", ":")),
                json.dumps(prompt_context, ensure_ascii=False, separators=(",", ":")),
            ),
        )
    return library_id


def _record(row: sqlite3.Row, *, detail: bool) -> dict[str, Any]:
    value: dict[str, Any] = {
        "library_id": row["library_id"],
        "worldline_id": row["worldline_id"],
        "created_at": row["created_at"],
        "draw_date": row["draw_date"],
        "numbers": json.loads(row["numbers_json"]),
        "extra_number": row["extra_number"],
        "language": row["language"],
        "provider": row["provider"],
        "model": row["model"],
        "confidence": row["confidence"],
        "astro_context_type": json.loads(row["prompt_context_json"]).get("astro_context_type", "unknown"),
        "historical_condition": json.loads(row["prompt_context_json"]).get("historical_condition", "unknown"),
    }
    if detail:
        value.update(
            generation_mode=row["generation_mode"],
            rationale=row["rationale"],
            caveats=json.loads(row["caveats_json"]),
            disclaimer=row["disclaimer"],
            astro_context=json.loads(row["astro_context_json"]),
            prompt_context=json.loads(row["prompt_context_json"]),
        )
    return value


def list_public_llm_worldlines(*, limit: int = 30, offset: int = 0) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM marksix_llm_worldlines ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_record(row, detail=False) for row in rows]


def get_public_llm_worldline(library_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM marksix_llm_worldlines WHERE library_id = ?",
            (library_id,),
        ).fetchone()
    return _record(row, detail=True) if row else None
