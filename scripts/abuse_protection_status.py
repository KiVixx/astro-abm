#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from astro_abm_api.services.auth_store import AuthStore  # noqa: E402
from astro_abm_api.services.scenario_store import ScenarioStore  # noqa: E402


LIMIT_ENVIRONMENTS = (
    "ASTRO_ABM_IP_CREATE_RATE_PER_HOUR",
    "ASTRO_ABM_IP_CREATE_RATE_PER_DAY",
    "ASTRO_ABM_IP_LLM_RATE_PER_HOUR",
    "ASTRO_ABM_GUEST_SCENARIO_QUOTA",
    "ASTRO_ABM_USER_SCENARIO_QUOTA",
    "ASTRO_ABM_MAX_REQUEST_BODY_BYTES",
    "ASTRO_ABM_SCENARIO_MAX_REPORT_BYTES",
    "ASTRO_ABM_SCENARIO_STORE_MAX_REPORTS",
    "ASTRO_ABM_SCENARIO_STORE_MAX_BYTES",
    "ASTRO_ABM_GENERATION_GLOBAL_CONCURRENCY",
    "ASTRO_ABM_GENERATION_OWNER_CONCURRENCY",
)


def main() -> int:
    status = {
        "storage": ScenarioStore().storage_usage(),
        "runtime": AuthStore().abuse_protection_status(),
        "configured_limits": {name: os.getenv(name, "default") for name in LIMIT_ENVIRONMENTS},
        "raw_client_ips_stored": False,
    }
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
