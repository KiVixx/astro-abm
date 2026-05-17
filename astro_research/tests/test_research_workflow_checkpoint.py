from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("research_workflow_checkpoint", ROOT / "scripts" / "research_workflow_checkpoint.py")
assert SPEC is not None and SPEC.loader is not None
checkpoint = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checkpoint
SPEC.loader.exec_module(checkpoint)


def test_checkpoint_validates_output_paths_language_and_git_boundaries(tmp_path, monkeypatch):
    output_root = tmp_path / "astro_research" / "output"
    casebook = output_root / "reports" / "checkpoint" / "casebook"
    batch = output_root / "reports" / "checkpoint" / "batch"
    readout = output_root / "reports" / "checkpoint" / "readout.md"
    casebook.mkdir(parents=True)
    batch.mkdir(parents=True)
    readout.parent.mkdir(parents=True, exist_ok=True)
    (casebook / "index.md").write_text("# Crisis Casebook Index\n")
    (batch / "run_manifest.json").write_text("{}\n")
    readout.write_text(
        "This readout is for historical association review only and does not assert causality, prediction, investment advice, or a trading signal.\n"
    )
    monkeypatch.setattr(checkpoint, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(checkpoint, "validate_exploratory_batch_outputs", lambda _: [])
    monkeypatch.setattr(checkpoint, "_git", lambda _: "")

    warnings = checkpoint.validate_checkpoint(
        checkpoint.WorkflowPaths(casebook_output=casebook, batch_output=batch, readout_output=readout)
    )

    assert warnings == []


def test_checkpoint_warns_for_outputs_outside_output_and_staged_artifacts(tmp_path, monkeypatch):
    output_root = tmp_path / "astro_research" / "output"
    outside = tmp_path / "reports"
    outside.mkdir()
    readout = outside / "readout.md"
    readout.write_text("No boundary text.\n")

    def fake_git(args: list[str]) -> str:
        if args == ["diff", "--cached", "--name-only"]:
            return "astro_research/output/reports/readout.md\nastro_research/data/local/private.csv\n"
        if args == ["diff", "--cached"]:
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(checkpoint, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(checkpoint, "validate_exploratory_batch_outputs", lambda _: [])
    monkeypatch.setattr(checkpoint, "_git", fake_git)

    warnings = checkpoint.validate_checkpoint(
        checkpoint.WorkflowPaths(casebook_output=outside / "casebook", batch_output=outside / "batch", readout_output=readout)
    )

    assert "casebook_output: outside astro_research/output" in warnings
    assert "batch_output: outside astro_research/output" in warnings
    assert "readout_output: outside astro_research/output" in warnings
    assert "research_readout: missing descriptive-only boundary" in warnings
    assert "staged generated output: astro_research/output/reports/readout.md" in warnings
    assert "staged local csv: astro_research/data/local/private.csv" in warnings
