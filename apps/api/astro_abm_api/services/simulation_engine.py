from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from astro_abm_api.models.agent import AgentOutput, AgentProfile
from astro_abm_api.models.report import ScenarioReport
from astro_abm_api.models.scenario import ScenarioCreateRequest
from astro_abm_api.services.llm_client import build_llm_config, provenance_for_llm


DISCLAIMER = (
    "association only; scenario rehearsal only; not financial advice; not a trading signal."
)

SAFETY_CAVEATS = [
    "association only: this report explores historical-style associations and narrative reactions, not causal prediction.",
    "scenario rehearsal only: this is a structured thought exercise for risk discussion.",
    "not financial advice: it does not consider personal objectives, constraints, or suitability.",
    "not a trading signal: it does not provide entries, exits, leverage levels, or position direction.",
]


def create_scenario_id(title: str, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40] or "scenario"
    return f"{timestamp}_{slug}_{uuid4().hex[:8]}"


def build_agent_output(agent: AgentProfile) -> AgentOutput:
    behavior = (
        f"{agent.name} is modeled as a {agent.category} participant with "
        f"{agent.time_horizon} horizon and {agent.decision_style} behavior. "
        "In this MVP, the agent reviews stress regime, market volatility, macro context, "
        "liquidity pressure, and astro narrative as scenario inputs."
    )
    likely_reaction = (
        "Likely reaction is framed as risk review, patience, liquidity awareness, "
        "and narrative sensitivity rather than a directional market call."
    )
    if agent.category == "retail":
        likely_reaction = (
            "Likely reaction centers on crowd narrative, emotional pressure, and the need "
            "to separate social excitement from risk planning."
        )
    elif agent.category == "trading":
        likely_reaction = (
            "Likely reaction centers on exposure discipline, volatility awareness, "
            "and avoiding overconfidence during unstable regimes."
        )
    elif agent.category == "institutional":
        likely_reaction = (
            "Likely reaction centers on scenario weights, cross-asset stress, liquidity, "
            "and portfolio-level risk review."
        )
    elif agent.category == "company_type":
        likely_reaction = (
            "Likely reaction centers on planning cadence, liquidity buffers, financing conditions, "
            "and operational resilience."
        )

    return AgentOutput(
        agent_id=agent.agent_id,
        agent_name=agent.name,
        role=agent.category,
        behavior_summary=behavior,
        risk_appetite=agent.risk_tolerance,
        likely_reaction=likely_reaction,
        confidence="low_to_medium_mock_confidence",
        caveats=[
            "Mock deterministic output; no external LLM reasoning was used.",
            "Agent behavior is archetypal and should be reviewed as a scenario lens only.",
        ],
    )


def render_markdown(report: ScenarioReport) -> str:
    agent_lines = "\n".join(
        [
            (
                f"### {output.agent_name}\n"
                f"- Role: {output.role}\n"
                f"- Behavior summary: {output.behavior_summary}\n"
                f"- Likely reaction: {output.likely_reaction}\n"
                f"- Confidence: {output.confidence}\n"
            )
            for output in report.agent_outputs
        ]
    )
    risk_lines = "\n".join(f"- {risk}" for risk in report.risks)
    caveat_lines = "\n".join(f"- {caveat}" for caveat in report.caveats)
    inputs = (
        f"- Date range: {report.start_date.isoformat()} to {report.end_date.isoformat()}\n"
        f"- Assets: {', '.join(report.assets)}\n"
        f"- Agents: {', '.join(agent.name for agent in report.agents)}\n"
        f"- Visibility: {report.visibility}\n"
        f"- Mode: {report.mode}"
    )
    context_lines = "\n".join(
        f"- {key}: {value}" for key, value in report.daily_context.items()
    )

    return f"""# {report.title}

## Executive Summary
{report.simulation_summary}

## Scenario Inputs
{inputs}

## Daily Context
{context_lines}

## Agent Behavior Outputs
{agent_lines}

## Main Risk Themes
{risk_lines}

## Caveats
{caveat_lines}

## Provenance
- Engine: {report.provenance.get("engine")}
- LLM provider: {report.provenance.get("llm", {}).get("provider")}
- Network call performed: {report.provenance.get("llm", {}).get("network_call_performed")}

## Disclaimer
{report.disclaimer}
""".strip() + "\n"


def generate_scenario_report(
    request: ScenarioCreateRequest,
    agents: list[AgentProfile],
    daily_context: dict[str, object],
    scenario_id: str | None = None,
) -> ScenarioReport:
    llm_config = build_llm_config(
        provider=request.llm_provider,
        base_url=request.llm_base_url,
        model=request.llm_model,
    )
    created_at = datetime.now(UTC)
    report_id = scenario_id or create_scenario_id(request.title, created_at)
    agent_outputs = [build_agent_output(agent) for agent in agents]
    summary = (
        "This local-first scenario report rehearses how selected agent archetypes may "
        "discuss daily market, macro, stress, and astro context. It is association only, "
        "scenario rehearsal only, not financial advice, and not a trading signal."
    )
    risks = [
        "Narrative amplification may make participants overreact to uncertain context.",
        "Liquidity and volatility can change the meaning of the same daily signal across regimes.",
        "Mock outputs may miss details that a real analyst or later LLM layer would surface.",
    ]
    provenance = {
        "engine": "mock_deterministic_simulation_v1",
        "data_context": "daily_context_placeholder_v0",
        "llm": provenance_for_llm(llm_config),
        "created_by": "astro-abm-api",
    }
    report = ScenarioReport(
        scenario_id=report_id,
        title=request.title,
        description=request.description,
        created_at=created_at,
        start_date=request.start_date,
        end_date=request.end_date,
        assets=request.assets,
        agents=agents,
        daily_context=daily_context,
        simulation_summary=summary,
        agent_outputs=agent_outputs,
        risks=risks,
        caveats=SAFETY_CAVEATS,
        provenance=provenance,
        visibility=request.visibility,
        mode=request.mode,
        markdown_report="",
        disclaimer=DISCLAIMER,
    )
    return report.model_copy(update={"markdown_report": render_markdown(report)})
