from __future__ import annotations

from astro_abm_api.models.agent import AgentProfile


DEFAULT_AGENT_PROFILES = (
    AgentProfile(
        agent_id="crypto_retail_fomo",
        name="Crypto Retail FOMO",
        category="retail",
        description="Short-horizon crypto participant sensitive to narrative momentum and crowd excitement.",
        risk_tolerance="high",
        time_horizon="hours_to_days",
        macro_sensitivity="medium",
        astro_narrative_sensitivity="high",
        liquidity_sensitivity="medium",
        decision_style="reactive narrative-following",
    ),
    AgentProfile(
        agent_id="long_term_holder",
        name="Long-Term Holder",
        category="retail",
        description="Patient allocator focused on broad cycles, drawdowns, and accumulation discipline.",
        risk_tolerance="medium",
        time_horizon="months_to_years",
        macro_sensitivity="medium",
        astro_narrative_sensitivity="low",
        liquidity_sensitivity="low",
        decision_style="slow conviction-based review",
    ),
    AgentProfile(
        agent_id="leveraged_trader",
        name="Leveraged Trader",
        category="trading",
        description="Positioning-sensitive participant focused on volatility, funding, and liquidation risk.",
        risk_tolerance="very_high",
        time_horizon="intraday_to_days",
        macro_sensitivity="medium",
        astro_narrative_sensitivity="medium",
        liquidity_sensitivity="high",
        decision_style="fast risk-adjustment",
    ),
    AgentProfile(
        agent_id="macro_allocator",
        name="Macro Allocator",
        category="institutional",
        description="Cross-asset allocator weighing macro stress, rates, dollar strength, and volatility.",
        risk_tolerance="medium",
        time_horizon="weeks_to_quarters",
        macro_sensitivity="high",
        astro_narrative_sensitivity="low",
        liquidity_sensitivity="medium",
        decision_style="scenario-weighted allocation review",
    ),
    AgentProfile(
        agent_id="big_tech_company_type",
        name="Big Tech Company Type",
        category="company_type",
        description="Large technology company archetype sensitive to capital expenditure, liquidity, and risk appetite.",
        risk_tolerance="medium",
        time_horizon="quarters_to_years",
        macro_sensitivity="high",
        astro_narrative_sensitivity="low",
        liquidity_sensitivity="medium",
        decision_style="committee-based strategic planning",
    ),
    AgentProfile(
        agent_id="global_bank_type",
        name="Global Bank Type",
        category="company_type",
        description="Large bank archetype focused on funding markets, credit stress, regulation, and counterparty risk.",
        risk_tolerance="low_to_medium",
        time_horizon="weeks_to_quarters",
        macro_sensitivity="very_high",
        astro_narrative_sensitivity="low",
        liquidity_sensitivity="very_high",
        decision_style="risk committee balance-sheet review",
    ),
    AgentProfile(
        agent_id="energy_company_type",
        name="Energy Company Type",
        category="company_type",
        description="Energy company archetype sensitive to macro demand, dollar moves, geopolitical stress, and financing costs.",
        risk_tolerance="medium",
        time_horizon="quarters_to_years",
        macro_sensitivity="high",
        astro_narrative_sensitivity="low",
        liquidity_sensitivity="medium",
        decision_style="operational hedging and capital planning",
    ),
)


def list_agents() -> list[AgentProfile]:
    return list(DEFAULT_AGENT_PROFILES)


def agent_registry() -> dict[str, AgentProfile]:
    return {agent.agent_id: agent for agent in DEFAULT_AGENT_PROFILES}


def resolve_agents(agent_ids: list[str]) -> tuple[list[AgentProfile], list[str]]:
    registry = agent_registry()
    agents = []
    unknown = []
    for agent_id in agent_ids:
        agent = registry.get(agent_id)
        if agent is None:
            unknown.append(agent_id)
        else:
            agents.append(agent)
    return agents, unknown
