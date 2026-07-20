#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from astro_abm_api.services.guest_cleanup import cleanup_expired_guest_worldlines  # noqa: E402


def main() -> int:
    removed_reports, removed_guests = cleanup_expired_guest_worldlines()
    print(f"Expired guest cleanup: reports={removed_reports}, workspaces={removed_guests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
