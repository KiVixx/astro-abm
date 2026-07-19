from __future__ import annotations

import argparse
import json
import re
import subprocess
import tomllib
from collections.abc import Sequence
from pathlib import Path


EXPECTED_LICENSE = "AGPL-3.0-or-later"
REQUIRED_FILES = (
    "LICENSE",
    "LICENSE_NOTES.md",
    "DATA_LICENSE.md",
    "THIRD_PARTY_NOTICES.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
)
IGNORE_PROBES = (
    ".env",
    ".local/llm_presets.json",
    "apps/web/.next-build",
    "apps/web/node_modules",
    "astro_research/output/scenarios/audit-example.json",
    "astro_research/data/local/equity/spx_daily.csv",
)
SECRET_PATTERNS = {
    "openai_style_key": re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    "google_style_key": re.compile(rb"(?<![A-Za-z0-9])(?:AQ\.|AIza)[A-Za-z0-9_-]{20,}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "fred_assignment": re.compile(rb"FRED_API_KEY\s*=\s*[A-Fa-f0-9]{24,}"),
    "llm_assignment": re.compile(
        rb"ASTRO_ABM_LLM_API_KEY\s*=\s*(?:sk-|AQ\.|AIza)[A-Za-z0-9_.-]{20,}"
    ),
}
HISTORY_SECRET_FIXTURE_PATHS = frozenset({"tests/test_open_source_audit.py"})


def secret_categories(data: bytes) -> list[str]:
    return sorted(name for name, pattern in SECRET_PATTERNS.items() if pattern.search(data))


def allowed_tracked_path(path: str) -> bool:
    if path == ".env.example" or path.endswith("/.gitkeep"):
        return True
    if path == "astro_research/data/local/LOCAL_DATA_PROVENANCE.json":
        return True
    return path.startswith("astro_research/data/local/examples/") and path.endswith(
        ".example.csv"
    )


def suspicious_tracked_paths(paths: Sequence[str]) -> list[str]:
    suspicious: list[str] = []
    for path in paths:
        matches = (
            path == ".env"
            or path.startswith(".local/")
            or "/node_modules/" in f"/{path}"
            or "/.next" in f"/{path}"
            or path.startswith("astro_research/output/scenarios/")
            or (
                path.startswith("astro_research/data/local/")
                and path.endswith((".csv", ".json", ".parquet"))
            )
        )
        if matches and not allowed_tracked_path(path):
            suspicious.append(path)
    return sorted(suspicious)


def history_secret_candidates(repo: Path) -> list[tuple[str, str]]:
    process = subprocess.Popen(
        ["git", "log", "-p", "--all", "--full-history", "--no-color"],
        cwd=repo,
        stdout=subprocess.PIPE,
    )
    assert process.stdout is not None
    current_path = "unknown"
    findings: set[tuple[str, str]] = set()
    for raw_line in process.stdout:
        if raw_line.startswith(b"diff --git a/"):
            current_path = raw_line.decode("utf-8", errors="replace").split(" b/", 1)[-1].strip()
        elif raw_line[:1] in (b"+", b"-") and not raw_line.startswith((b"+++", b"---")):
            if current_path not in HISTORY_SECRET_FIXTURE_PATHS:
                findings.update((category, current_path) for category in secret_categories(raw_line))
    if process.wait() != 0:
        raise RuntimeError("git history scan failed")
    return sorted(findings)


def _run(repo: Path, *args: str) -> str:
    return subprocess.check_output(args, cwd=repo, text=True).strip()


def run_audit(repo: Path, *, scan_history: bool = False) -> int:
    failures: list[str] = []
    warnings: list[str] = []

    missing = [path for path in REQUIRED_FILES if not (repo / path).is_file()]
    if missing:
        failures.append(f"missing required files: {', '.join(missing)}")

    license_text = (repo / "LICENSE").read_text(encoding="utf-8")
    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in license_text:
        failures.append("LICENSE is not the canonical AGPL license text")

    pyproject = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    if pyproject.get("project", {}).get("license") != EXPECTED_LICENSE:
        failures.append("pyproject.toml license metadata is not AGPL-3.0-or-later")

    web_package = json.loads((repo / "apps/web/package.json").read_text(encoding="utf-8"))
    if web_package.get("license") != EXPECTED_LICENSE:
        failures.append("apps/web/package.json license metadata is not AGPL-3.0-or-later")

    tracked = _run(repo, "git", "ls-files").splitlines()
    suspicious = suspicious_tracked_paths(tracked)
    if suspicious:
        failures.append(f"sensitive/generated paths are tracked: {', '.join(suspicious)}")

    for probe in IGNORE_PROBES:
        result = subprocess.run(
            ["git", "check-ignore", "-q", probe],
            cwd=repo,
            check=False,
        )
        if result.returncode != 0:
            failures.append(f"expected ignored path is not ignored: {probe}")

    env_path = repo / ".env"
    if env_path.exists():
        categories = secret_categories(env_path.read_bytes())
        if categories:
            warnings.append(
                "local .env contains credential categories (expected locally; never commit): "
                + ", ".join(categories)
            )

    history_findings: list[tuple[str, str]] = []
    if scan_history:
        history_findings = history_secret_candidates(repo)
        if history_findings:
            failures.append(
                "Git history contains possible credentials: "
                + ", ".join(f"{category}:{path}" for category, path in history_findings)
            )

    print(f"license: {EXPECTED_LICENSE}")
    print(f"required policy files: {len(REQUIRED_FILES) - len(missing)}/{len(REQUIRED_FILES)}")
    print(f"tracked files checked: {len(tracked)}")
    print(f"history scan: {'enabled' if scan_history else 'skipped (use --history)'}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for failure in failures:
        print(f"FAIL: {failure}")
    if failures:
        return 1
    print("Open-source readiness audit passed.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Astro ABM open-source release readiness")
    parser.add_argument("--history", action="store_true", help="scan all Git history for secret patterns")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[3]
    return run_audit(repo, scan_history=args.history)


if __name__ == "__main__":
    raise SystemExit(main())
