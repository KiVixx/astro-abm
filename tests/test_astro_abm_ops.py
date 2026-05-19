from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_ops_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "astro_abm_ops.py"
    spec = importlib.util.spec_from_file_location("astro_abm_ops", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_split_sql_statements_keeps_semicolon_inside_string():
    ops = load_ops_module()
    sql = "CREATE TABLE x (note VARCHAR); INSERT INTO x VALUES ('a;b');"

    statements = ops.split_sql_statements(sql)

    assert statements == ["CREATE TABLE x (note VARCHAR)", "INSERT INTO x VALUES ('a;b')"]


def test_read_env_file_ignores_comments_and_strips_quotes(tmp_path):
    ops = load_ops_module()
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
        # comment
        QUESTDB_HOST=localhost
        FRED_API_KEY="abc123"
        EMPTY=
        """.strip()
    )

    values = ops.read_env_file(env_path)

    assert values["QUESTDB_HOST"] == "localhost"
    assert values["FRED_API_KEY"] == "abc123"
    assert values["EMPTY"] == ""


def test_local_data_checks_report_missing_and_present_files(tmp_path):
    ops = load_ops_module()
    present = tmp_path / "astro_research/data/local/equity/spx_daily.csv"
    present.parent.mkdir(parents=True)
    present.write_text("date,close\n2020-01-01,100\n")

    checks = {check.name: check for check in ops.local_data_checks(root=tmp_path)}

    assert checks["local_data_SPX"].ok is True
    assert checks["local_data_Gold"].ok is False
    assert "missing" in checks["local_data_Gold"].detail


def test_research_input_checks_report_existing_directory(tmp_path):
    ops = load_ops_module()
    aspect_dir = tmp_path / "astro_research/output/parquet/aspect_chunks_mvp35/macro_core_1926_2025/aspects"
    aspect_dir.mkdir(parents=True)

    checks = {check.name: check for check in ops.research_input_checks(root=tmp_path)}

    assert checks["research_input_macro_core_aspect_chunks"].ok is True
    assert checks["research_input_research_events"].ok is False
