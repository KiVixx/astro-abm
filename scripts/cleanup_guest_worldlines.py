#!/usr/bin/env python3
from __future__ import annotations

from astro_abm_api.services.guest_cleanup import cleanup_expired_guest_worldlines


def main() -> int:
    removed_reports, removed_guests = cleanup_expired_guest_worldlines()
    print(f"Expired guest cleanup: reports={removed_reports}, workspaces={removed_guests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
