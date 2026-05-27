from __future__ import annotations

import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from astro_abm_api.models.scenario import ScenarioCreateRequest  # noqa: E402
from astro_abm_api.services.agents import resolve_agents  # noqa: E402
from astro_abm_api.services.daily_context import build_daily_context  # noqa: E402
from astro_abm_api.services.scenario_store import ScenarioStore  # noqa: E402
from astro_abm_api.services.simulation_engine import generate_scenario_report  # noqa: E402


DEMO_SCENARIO_ID = "demo_2026q3_btc_eth"


def main() -> None:
    request = ScenarioCreateRequest(
        title="2026 Q3 BTC ETH Daily Scenario Demo",
        description="Local deterministic demo scenario for the product MVP.",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 9, 30),
        assets=["BTC", "ETH"],
        agent_ids=["crypto_retail_fomo", "leveraged_trader", "macro_allocator"],
        llm_provider="mock",
        visibility="private",
    )
    agents, unknown = resolve_agents(request.agent_ids)
    if unknown:
        raise SystemExit(f"Unknown demo agents: {', '.join(unknown)}")
    report = generate_scenario_report(
        request=request,
        agents=agents,
        daily_context=build_daily_context(request),
        scenario_id=DEMO_SCENARIO_ID,
    )
    ScenarioStore().save(report)
    print(f"Created demo scenario: {report.scenario_id}")
    print(f"Output directory: {ScenarioStore().output_dir}")


if __name__ == "__main__":
    main()
