from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from astro_abm_api.models.agent import AgentOutput, AgentProfile
from astro_abm_api.models.report import DailyAgentState, DailyScenarioSnapshot, ScenarioReport
from astro_abm_api.models.scenario import ReportLanguage, ScenarioCreateRequest
from astro_abm_api.services.daily_context import build_placeholder_daily_contexts
from astro_abm_api.services.llm_client import build_llm_config, provenance_for_llm


DISCLAIMER_BY_LANGUAGE: dict[ReportLanguage, str] = {
    "en": "association only; scenario rehearsal only; not financial advice; not a trading signal.",
    "zh-Hant": "僅為相關性分析；僅為情境推演；不構成財務建議；不是交易訊號。",
}

SAFETY_CAVEATS_BY_LANGUAGE: dict[ReportLanguage, list[str]] = {
    "en": [
        "association only: this report explores historical-style associations and narrative reactions, not causal prediction.",
        "scenario rehearsal only: this is a structured thought exercise for risk discussion.",
        "not financial advice: it does not consider personal objectives, constraints, or suitability.",
        "not a trading signal: it does not provide entries, exits, leverage levels, or position direction.",
    ],
    "zh-Hant": [
        "僅為相關性分析：本報告只探索類歷史相關性與敘事反應，不做因果預測。",
        "僅為情境推演：這是用於風險討論的結構化思考練習。",
        "不構成財務建議：它沒有考慮個人目標、限制條件或適合性。",
        "不是交易訊號：它不提供進出場、槓桿水平或持倉方向。",
    ],
}


def disclaimer_for(language: ReportLanguage) -> str:
    return DISCLAIMER_BY_LANGUAGE[language]


def safety_caveats_for(language: ReportLanguage) -> list[str]:
    return SAFETY_CAVEATS_BY_LANGUAGE[language]


def create_scenario_id(title: str, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40] or "scenario"
    return f"{timestamp}_{slug}_{uuid4().hex[:8]}"


def build_agent_output(agent: AgentProfile, language: ReportLanguage = "en") -> AgentOutput:
    if language == "zh-Hant":
        behavior = (
            f"{agent.name} 被建模為 {agent.category} 參與者，時間視角為 "
            f"{agent.time_horizon}，決策風格為 {agent.decision_style}。"
            "在此 MVP 中，代理群體會把壓力狀態、市場波動、宏觀脈絡、"
            "流動性壓力與天象敘事作為情境輸入來審視。"
        )
        likely_reaction = (
            "可能反應會以風險檢視、耐心、流動性意識與敘事敏感度來表達，"
            "而不是方向性市場判斷。"
        )
        if agent.category == "retail":
            likely_reaction = (
                "可能反應集中在群眾敘事、情緒壓力，以及把社群興奮感與風險規劃分開。"
            )
        elif agent.category == "trading":
            likely_reaction = (
                "可能反應集中在曝險紀律、波動意識，以及在不穩定狀態下避免過度自信。"
            )
        elif agent.category == "institutional":
            likely_reaction = (
                "可能反應集中在情境權重、跨資產壓力、流動性與投資組合層面的風險檢視。"
            )
        elif agent.category == "company_type":
            likely_reaction = (
                "可能反應集中在規劃節奏、流動性緩衝、融資條件與營運韌性。"
            )
        caveats = [
            "Mock deterministic 輸出；沒有使用外部 LLM 推理。",
            "代理行為是原型化描述，只應作為情境視角檢視。",
        ]
    else:
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
        caveats = [
            "Mock deterministic output; no external LLM reasoning was used.",
            "Agent behavior is archetypal and should be reviewed as a scenario lens only.",
        ]

    return AgentOutput(
        agent_id=agent.agent_id,
        agent_name=agent.name,
        role=agent.category,
        behavior_summary=behavior,
        risk_appetite=agent.risk_tolerance,
        likely_reaction=likely_reaction,
        confidence="low_to_medium_mock_confidence",
        caveats=caveats,
    )


def build_daily_agent_state(
    agent: AgentProfile,
    snapshot_context: dict[str, object],
    language: ReportLanguage = "en",
) -> DailyAgentState:
    market_context = snapshot_context["market_context"]
    astro_context = snapshot_context["astro_context"]
    research_signals = snapshot_context["research_signals"]
    stress_regime = market_context.stress_regime
    volatility_regime = market_context.volatility_regime
    liquidity_regime = market_context.liquidity_regime
    astro_tags = ", ".join(astro_context.event_tags)

    mood = "watchful"
    if agent.category == "retail":
        mood = "narrative-sensitive"
    elif agent.category == "trading":
        mood = "exposure-aware"
    elif agent.category == "institutional":
        mood = "portfolio-aware"
    elif agent.category == "company_type":
        mood = "planning-focused"

    if language == "zh-Hant":
        likely_reaction = (
            f"檢視壓力狀態：{stress_regime}、波動狀態：{volatility_regime}、"
            f"流動性狀態：{liquidity_regime}，以及天象敘事標籤（{astro_tags}）。"
            f"資料品質為 {research_signals.data_quality}；這些內容僅作為風險討論的情境脈絡。"
        )
        caveats = [
            "每日代理狀態是 deterministic mock 輸出。",
            "這不是方向性市場判斷，也不是交易訊號。",
        ]
    else:
        likely_reaction = (
            f"Reviews stress regime: {stress_regime}, volatility regime: {volatility_regime}, "
            f"liquidity regime: {liquidity_regime}, and astro narrative tags ({astro_tags}) "
            f"with {research_signals.data_quality} data quality as scenario context "
            "for risk discussion only."
        )
        caveats = [
            "Daily agent state is deterministic mock output.",
            "This is not a directional market call and not a trading signal.",
        ]

    return DailyAgentState(
        agent_id=agent.agent_id,
        agent_name=agent.name,
        mood=mood,
        risk_appetite=agent.risk_tolerance,
        likely_reaction=likely_reaction,
        attention_triggers=[
            f"stress_regime:{stress_regime}",
            f"volatility_regime:{volatility_regime}",
            f"liquidity_regime:{liquidity_regime}",
            f"astro_intensity:{astro_context.intensity}",
            f"data_quality:{research_signals.data_quality}",
        ],
        caveats=caveats,
    )


def build_daily_timeline(
    request: ScenarioCreateRequest,
    agents: list[AgentProfile],
) -> list[DailyScenarioSnapshot]:
    snapshots: list[DailyScenarioSnapshot] = []
    for context in build_placeholder_daily_contexts(request):
        agent_states = [
            build_daily_agent_state(agent, context, request.language) for agent in agents
        ]
        snapshots.append(
            DailyScenarioSnapshot(
                date=context["date"],
                day_index=context["day_index"],
                assets=request.assets,
                astro_context=context["astro_context"],
                market_context=context["market_context"],
                data_coverage=context["data_coverage"],
                research_signals=context["research_signals"],
                agent_states=agent_states,
                daily_risk_themes=context["daily_risk_themes"],
                daily_summary=context["daily_summary"],
                confidence=context["confidence"],
                caveats=context["caveats"],
                disclaimer=disclaimer_for(request.language),
            )
        )
    return snapshots


def render_markdown(report: ScenarioReport) -> str:
    language: ReportLanguage = report.language or "en"
    is_chinese = language == "zh-Hant"

    if is_chinese:
        agent_lines = "\n".join(
            [
                (
                    f"### {output.agent_name}\n"
                    f"- 角色：{output.role}\n"
                    f"- 行為摘要：{output.behavior_summary}\n"
                    f"- 可能反應：{output.likely_reaction}\n"
                    f"- 信心：{output.confidence}\n"
                )
                for output in report.agent_outputs
            ]
        )
    else:
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
    risk_themes = report.risk_themes or report.risks
    risk_lines = "\n".join(f"- {risk}" for risk in risk_themes)
    caveat_lines = "\n".join(f"- {caveat}" for caveat in report.caveats)
    if is_chinese:
        inputs = (
            f"- 日期範圍：{report.start_date.isoformat()} 至 {report.end_date.isoformat()}\n"
            f"- 資產：{', '.join(report.assets)}\n"
            f"- 代理群體：{', '.join(agent.name for agent in report.agents)}\n"
            f"- 可見性：{report.visibility}\n"
            f"- 模式：{report.mode}\n"
            f"- 生成語言：{language}"
        )
    else:
        inputs = (
            f"- Date range: {report.start_date.isoformat()} to {report.end_date.isoformat()}\n"
            f"- Assets: {', '.join(report.assets)}\n"
            f"- Agents: {', '.join(agent.name for agent in report.agents)}\n"
            f"- Visibility: {report.visibility}\n"
            f"- Mode: {report.mode}\n"
            f"- Generated language: {language}"
        )
    context_lines = "\n".join(
        f"- {key}: {value}" for key, value in report.daily_context.items()
    )
    if is_chinese:
        timeline_lines = "\n\n".join(
            [
                (
                    f"## {snapshot.date.isoformat()}\n"
                    f"- 天象：{snapshot.astro_context.summary} "
                    f"（強度：{snapshot.astro_context.intensity}；"
                    f"標籤：{', '.join(snapshot.astro_context.event_tags)}）\n"
                    f"- 市場：{snapshot.market_context.summary}\n"
                    f"- 資料覆蓋：astro_daily={snapshot.data_coverage.astro_daily}; "
                    f"financial_stress_daily={snapshot.data_coverage.financial_stress_daily}; "
                    f"market_daily={snapshot.data_coverage.market_daily}; "
                    f"macro_daily={snapshot.data_coverage.macro_daily}; "
                    f"source={snapshot.data_coverage.source}\n"
                    f"- 研究訊號：stress={snapshot.research_signals.stress_regime}; "
                    f"volatility={snapshot.research_signals.volatility_regime}; "
                    f"liquidity={snapshot.research_signals.liquidity_regime}; "
                    f"astro_activity={snapshot.research_signals.astro_activity}; "
                    f"data_quality={snapshot.research_signals.data_quality}\n"
                    f"- 代理狀態：\n"
                    + "\n".join(
                        [
                            (
                                f"  - {state.agent_name}: {state.mood}; "
                                f"{state.likely_reaction}"
                            )
                            for state in snapshot.agent_states
                        ]
                    )
                    + "\n"
                    f"- 每日風險主題：{', '.join(snapshot.daily_risk_themes)}\n"
                    f"- 來源/回退備註：{'; '.join(snapshot.data_coverage.notes)}\n"
                    f"- 注意事項：{'; '.join(snapshot.caveats)}"
                )
                for snapshot in report.daily_timeline
            ]
        )

        return f"""# {report.title}

## 執行摘要
{report.scenario_summary or report.simulation_summary}

## 情境輸入
{inputs}

## 日線脈絡摘要
{context_lines}

## 每日時間線
{timeline_lines}

## 代理總覽
{agent_lines}

## 風險主題
{risk_lines}

## 注意事項
{caveat_lines}

## 來源紀錄
- 引擎：{report.provenance.get("engine")}
- LLM 提供者：{report.provenance.get("llm", {}).get("provider")}
- 是否執行網路呼叫：{report.provenance.get("llm", {}).get("network_call_performed")}

## 免責聲明
{report.disclaimer}
""".strip() + "\n"

    timeline_lines = "\n\n".join(
        [
            (
                f"## {snapshot.date.isoformat()}\n"
                f"- Astro: {snapshot.astro_context.summary} "
                f"(intensity: {snapshot.astro_context.intensity}; "
                f"tags: {', '.join(snapshot.astro_context.event_tags)})\n"
                f"- Market: {snapshot.market_context.summary}\n"
                f"- Data coverage: astro_daily={snapshot.data_coverage.astro_daily}; "
                f"financial_stress_daily={snapshot.data_coverage.financial_stress_daily}; "
                f"market_daily={snapshot.data_coverage.market_daily}; "
                f"macro_daily={snapshot.data_coverage.macro_daily}; "
                f"source={snapshot.data_coverage.source}\n"
                f"- Research signals: stress={snapshot.research_signals.stress_regime}; "
                f"volatility={snapshot.research_signals.volatility_regime}; "
                f"liquidity={snapshot.research_signals.liquidity_regime}; "
                f"astro_activity={snapshot.research_signals.astro_activity}; "
                f"data_quality={snapshot.research_signals.data_quality}\n"
                f"- Agent states:\n"
                + "\n".join(
                    [
                        (
                            f"  - {state.agent_name}: {state.mood}; "
                            f"{state.likely_reaction}"
                        )
                        for state in snapshot.agent_states
                    ]
                )
                + "\n"
                f"- Daily risk themes: {', '.join(snapshot.daily_risk_themes)}\n"
                f"- Source/fallback notes: {'; '.join(snapshot.data_coverage.notes)}\n"
                f"- Caveats: {'; '.join(snapshot.caveats)}"
            )
            for snapshot in report.daily_timeline
        ]
    )

    return f"""# {report.title}

## Executive Summary
{report.scenario_summary or report.simulation_summary}

## Scenario Inputs
{inputs}

## Daily Context Summary
{context_lines}

## Daily Timeline
{timeline_lines}

## Agent Overview
{agent_lines}

## Risk Themes
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
    agent_outputs = [build_agent_output(agent, request.language) for agent in agents]
    daily_timeline = build_daily_timeline(request, agents)
    if request.language == "zh-Hant":
        summary = (
            "這份本地優先情境報告，用來推演所選代理原型如何討論日線市場、宏觀、"
            "壓力與天象脈絡。它僅為相關性分析，僅為情境推演，"
            "不構成財務建議，也不是交易訊號。"
        )
        risk_themes = [
            "敘事放大可能讓參與者對不確定脈絡反應過度。",
            "流動性與波動會讓同一個日線訊號在不同狀態下呈現不同含義。",
            "Mock 輸出可能缺少真實分析師或後續 LLM 層會補充的細節。",
        ]
    else:
        summary = (
            "This local-first scenario report rehearses how selected agent archetypes may "
            "discuss daily market, macro, stress, and astro context. It is association only, "
            "scenario rehearsal only, not financial advice, and not a trading signal."
        )
        risk_themes = [
            "Narrative amplification may make participants overreact to uncertain context.",
            "Liquidity and volatility can change the meaning of the same daily signal across regimes.",
            "Mock outputs may miss details that a real analyst or later LLM layer would surface.",
        ]
    provenance = {
        "engine": "mock_deterministic_simulation_v1",
        "data_context": "read_only_daily_research_context_v1_with_placeholder_fallback",
        "language": request.language,
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
        scenario_summary=summary,
        agent_outputs=agent_outputs,
        risks=risk_themes,
        risk_themes=risk_themes,
        daily_timeline=daily_timeline,
        caveats=safety_caveats_for(request.language),
        provenance=provenance,
        visibility=request.visibility,
        mode=request.mode,
        language=request.language,
        markdown_report="",
        disclaimer=disclaimer_for(request.language),
    )
    return report.model_copy(update={"markdown_report": render_markdown(report)})
