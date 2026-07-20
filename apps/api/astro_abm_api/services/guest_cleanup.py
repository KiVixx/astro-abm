from __future__ import annotations

from astro_abm_api.services.auth_store import AuthStore
from astro_abm_api.services.scenario_store import ScenarioNotFoundError, ScenarioStore


def cleanup_expired_guest_worldlines() -> tuple[int, int]:
    auth_store = AuthStore()
    scenario_store = ScenarioStore()
    removed_reports = 0
    for scenario_id in auth_store.expired_guest_scenario_ids():
        try:
            scenario_store.delete(scenario_id)
            removed_reports += 1
        except ScenarioNotFoundError:
            pass
    return removed_reports, auth_store.delete_expired_guests()
