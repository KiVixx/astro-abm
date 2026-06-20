from __future__ import annotations

from collections import Counter
import re
from datetime import UTC, date, datetime
from uuid import uuid4

from astro_abm_api.models.agent import AgentOutput, AgentProfile
from astro_abm_api.models.report import (
    AssetCoverageSummary,
    DailyAgentState,
    DailyAssetContext,
    DailyScenarioSnapshot,
    ScenarioCoverageSummary,
    ScenarioReport,
)
from astro_abm_api.models.scenario import ReportLanguage, ScenarioCreateRequest
from astro_abm_api.services.asset_registry import profile_for_asset, profiles_for_assets
from astro_abm_api.services.daily_context import build_placeholder_daily_contexts
from astro_abm_api.services.llm_client import (
    build_llm_config,
    generate_llm_scenario_report,
    provenance_for_llm,
)
from astro_abm_api.services.worldline_simulation import generate_worldline_simulation


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
                asset_contexts=build_daily_asset_contexts(
                    request.assets,
                    context,
                    language=request.language,
                ),
                agent_states=agent_states,
                daily_risk_themes=context["daily_risk_themes"],
                daily_summary=context["daily_summary"],
                confidence=context["confidence"],
                caveats=context["caveats"],
                disclaimer=disclaimer_for(request.language),
            )
        )
    return snapshots


def build_daily_asset_contexts(
    assets: list[str],
    snapshot_context: dict[str, object],
    *,
    language: ReportLanguage,
) -> list[DailyAssetContext]:
    data_coverage = snapshot_context["data_coverage"]
    research_signals = snapshot_context["research_signals"]
    contexts: list[DailyAssetContext] = []
    for asset in assets:
        profile = profile_for_asset(asset)
        if profile.supported:
            market_daily = data_coverage.market_daily
            data_source = data_coverage.source
            notes = supported_asset_notes(market_daily, language=language)
        else:
            market_daily = "custom_missing"
            data_source = "custom_asset_no_local_snapshot"
            notes = unsupported_asset_notes(language=language)
        contexts.append(
            DailyAssetContext(
                asset=profile.asset,
                label=profile.label,
                series_type=profile.series_type,
                supported=profile.supported,
                market_daily=market_daily,
                data_source=data_source,
                data_quality=research_signals.data_quality if profile.supported else "unsupported",
                volatility_regime=(
                    research_signals.volatility_regime if profile.supported else "unknown"
                ),
                stress_sentiment=stress_sentiment_for(
                    research_signals.stress_regime,
                    market_daily=market_daily,
                    supported=profile.supported,
                ),
                notes=notes,
            )
        )
    return contexts


def supported_asset_notes(market_daily: str, *, language: ReportLanguage) -> list[str]:
    if language == "zh-Hant":
        notes = ["支援的日線市場序列；僅作描述性情境脈絡。"]
        if market_daily == "available":
            notes.append("當日可使用本地 market_daily 快照。")
        elif market_daily == "future_placeholder":
            notes.append("未來日期尚無已觀測 market_daily 資料。")
        else:
            notes.append("當日沒有可用的逐資產 market_daily 快照。")
        notes.append("不是交易訊號。")
        return notes
    notes = ["Supported daily market series; descriptive scenario context only."]
    if market_daily == "available":
        notes.append("Local market_daily snapshot is available for this day.")
    elif market_daily == "future_placeholder":
        notes.append("No observed market_daily data is available for this future date.")
    else:
        notes.append("No per-asset market_daily snapshot is available for this day.")
    notes.append("Not a trading signal.")
    return notes


def unsupported_asset_notes(*, language: ReportLanguage) -> list[str]:
    if language == "zh-Hant":
        return [
            "自訂或未支援資產為相容性保留；目前沒有註冊本地日線市場序列。",
            "此資產不會被當作支援的日線市場資料來源。",
        ]
    return [
        "Custom or unsupported asset retained for compatibility; no registered local daily market series exists yet.",
        "This asset is not treated as a supported daily market data source.",
    ]


def stress_sentiment_for(stress_regime: str, *, market_daily: str, supported: bool) -> str:
    if not supported:
        return "unknown"
    if market_daily == "future_placeholder":
        return "unknown_future"
    if market_daily not in {"available", "future_placeholder"}:
        return "unknown"
    if stress_regime == "stress":
        return "stressed"
    if stress_regime == "elevated":
        return "elevated"
    if stress_regime == "watchful":
        return "watchful"
    return "normal"


def build_coverage_summary(
    daily_timeline: list[DailyScenarioSnapshot],
    assets: list[str],
    *,
    created_at: datetime,
    language: ReportLanguage,
) -> ScenarioCoverageSummary:
    total_days = len(daily_timeline)
    source_counts = Counter(snapshot.data_coverage.source for snapshot in daily_timeline)
    data_quality_counts = Counter(
        snapshot.research_signals.data_quality for snapshot in daily_timeline
    )
    component_keys = (
        "astro_daily",
        "financial_stress_daily",
        "market_daily",
        "macro_daily",
    )

    def status_values(snapshot: DailyScenarioSnapshot) -> list[str]:
        coverage = snapshot.data_coverage
        return [
            coverage.astro_daily,
            coverage.financial_stress_daily,
            coverage.market_daily,
            coverage.macro_daily,
        ]

    def is_future_placeholder(snapshot: DailyScenarioSnapshot) -> bool:
        return (
            snapshot.data_coverage.source == "future_placeholder"
            or snapshot.research_signals.data_quality == "future_placeholder"
            or "future_placeholder" in status_values(snapshot)
        )

    def is_placeholder(snapshot: DailyScenarioSnapshot) -> bool:
        return (
            snapshot.data_coverage.source in {"placeholder_fallback", "legacy_report"}
            or snapshot.research_signals.data_quality
            in {"placeholder_fallback", "low_placeholder_confidence", "legacy_report"}
        )

    def is_mixed(snapshot: DailyScenarioSnapshot) -> bool:
        values = status_values(snapshot)
        return "available" in values and any(value != "available" for value in values)

    component_available_counts = {
        key: sum(getattr(snapshot.data_coverage, key) == "available" for snapshot in daily_timeline)
        for key in component_keys
    }
    all_assets = sorted({asset for snapshot in daily_timeline for asset in snapshot.assets} | set(assets))
    asset_coverage = [
        build_asset_coverage_summary(asset, daily_timeline, language=language)
        for asset in all_assets
    ]

    notes = coverage_summary_notes(language)
    return ScenarioCoverageSummary(
        total_days=total_days,
        local_research_days=source_counts.get("local_research_snapshot", 0),
        placeholder_days=sum(is_placeholder(snapshot) for snapshot in daily_timeline),
        future_placeholder_days=sum(is_future_placeholder(snapshot) for snapshot in daily_timeline),
        mixed_context_days=sum(is_mixed(snapshot) for snapshot in daily_timeline),
        astro_daily_available_days=component_available_counts["astro_daily"],
        financial_stress_available_days=component_available_counts["financial_stress_daily"],
        market_daily_available_days=component_available_counts["market_daily"],
        macro_daily_available_days=component_available_counts["macro_daily"],
        data_sources=sorted(source_counts),
        data_quality_counts=dict(sorted(data_quality_counts.items())),
        source_counts=dict(sorted(source_counts.items())),
        asset_coverage=asset_coverage,
        date_range_mode=date_range_mode(
            [snapshot.date for snapshot in daily_timeline],
            created_at.date(),
        ),
        notes=notes,
    )


def build_asset_coverage_summary(
    asset: str,
    daily_timeline: list[DailyScenarioSnapshot],
    *,
    language: ReportLanguage,
) -> AssetCoverageSummary:
    relevant_days = [snapshot for snapshot in daily_timeline if asset in snapshot.assets]
    profile = profile_for_asset(asset)
    if not profile.supported:
        if language == "zh-Hant":
            notes = [
                "自訂或未支援資產沒有註冊本地日線市場資料。",
                "此摘要只用於相容性與資料脈絡說明。",
            ]
        else:
            notes = [
                "Custom or unsupported asset has no registered local daily market data.",
                "This summary is retained for compatibility and data context only.",
            ]
        return AssetCoverageSummary(
            asset=asset,
            available_days=0,
            missing_days=len(relevant_days),
            future_placeholder_days=0,
            coverage_status="custom_missing",
            notes=notes,
        )
    available_days = sum(
        snapshot.data_coverage.market_daily == "available" for snapshot in relevant_days
    )
    future_placeholder_days = sum(
        snapshot.data_coverage.market_daily == "future_placeholder"
        or snapshot.data_coverage.source == "future_placeholder"
        or snapshot.research_signals.data_quality == "future_placeholder"
        for snapshot in relevant_days
    )
    missing_days = max(len(relevant_days) - available_days - future_placeholder_days, 0)
    if relevant_days and available_days == len(relevant_days):
        coverage_status = "available"
    elif relevant_days and future_placeholder_days == len(relevant_days):
        coverage_status = "future_placeholder"
    elif available_days:
        coverage_status = "mixed"
    elif future_placeholder_days:
        coverage_status = "future_placeholder"
    else:
        coverage_status = "missing"

    if language == "zh-Hant":
        notes = [
            "資產層級覆蓋由每日 market_daily 狀態保守推導；此 MVP 尚未在每個快照內保存逐資產觀測覆蓋。",
            "此摘要只用於描述資料脈絡，不是逐點回測。",
        ]
    else:
        notes = [
            "Asset-level coverage is conservatively inferred from daily market_daily status; this MVP does not store per-asset observed coverage inside each snapshot.",
            "This summary is descriptive context only, not point-in-time backtesting.",
        ]
    return AssetCoverageSummary(
        asset=asset,
        available_days=available_days,
        missing_days=missing_days,
        future_placeholder_days=future_placeholder_days,
        coverage_status=coverage_status,
        notes=notes,
    )


def date_range_mode(dates: list[date], today: date) -> str:
    if not dates:
        return "empty"
    if all(value > today for value in dates):
        return "future"
    if all(value <= today for value in dates):
        return "historical"
    return "mixed"


def coverage_summary_notes(language: ReportLanguage) -> list[str]:
    if language == "zh-Hant":
        return [
            "local_research_snapshot 表示當天可使用只讀本地研究脈絡。",
            "computed_ephemeris 表示當天星曆由本機 Swiss Ephemeris 即時計算，不代表市場觀測資料可用。",
            "future_placeholder 表示未來日期尚無已觀測市場或壓力資料。",
            "coverage summary 只描述資料覆蓋，不代表逐點回測。",
            "資產覆蓋為保守估算，因為每日快照目前只保存情境資產與 market_daily 整體狀態。",
        ]
    return [
        "local_research_snapshot indicates read-only local research context was available for that day.",
        "computed_ephemeris indicates local Swiss Ephemeris calculations were used for astro context; it does not imply observed market data is available.",
        "future_placeholder indicates no observed market/stress data is available for future dates.",
        "coverage summary is descriptive only and is not a point-in-time backtest.",
        "Asset coverage is conservative because daily snapshots currently store scenario assets and overall market_daily status, not a full per-asset audit.",
    ]


def render_coverage_markdown(
    coverage_summary: ScenarioCoverageSummary | None,
    *,
    language: ReportLanguage,
) -> str:
    if coverage_summary is None:
        if language == "zh-Hant":
            return "此保存報告尚未包含情境層級資料覆蓋摘要。"
        return "This saved report does not include a scenario-level coverage summary yet."

    if language == "zh-Hant":
        asset_lines = "\n".join(
            (
                f"- {asset.asset}: 狀態={asset.coverage_status}; "
                f"可用={asset.available_days}; 缺失={asset.missing_days}; "
                f"未來佔位={asset.future_placeholder_days}"
            )
            for asset in coverage_summary.asset_coverage
        )
        note_lines = "\n".join(f"- {note}" for note in coverage_summary.notes)
        return f"""- 總天數：{coverage_summary.total_days}
- 本地研究天數：{coverage_summary.local_research_days}
- 佔位資料天數：{coverage_summary.placeholder_days}
- 未來佔位天數：{coverage_summary.future_placeholder_days}
- 混合脈絡天數：{coverage_summary.mixed_context_days}
- 天象日線可用天數：{coverage_summary.astro_daily_available_days}
- 金融壓力可用天數：{coverage_summary.financial_stress_available_days}
- 市場日線可用天數：{coverage_summary.market_daily_available_days}
- 宏觀日線可用天數：{coverage_summary.macro_daily_available_days}
- 資料來源：{', '.join(coverage_summary.data_sources) or '無'}
- 日期範圍模式：{coverage_summary.date_range_mode}

### 資產覆蓋
{asset_lines or '- 無資產覆蓋資料'}

### 覆蓋說明
{note_lines}
"""

    asset_lines = "\n".join(
        (
            f"- {asset.asset}: status={asset.coverage_status}; "
            f"available={asset.available_days}; missing={asset.missing_days}; "
            f"future_placeholder={asset.future_placeholder_days}"
        )
        for asset in coverage_summary.asset_coverage
    )
    note_lines = "\n".join(f"- {note}" for note in coverage_summary.notes)
    return f"""- Total days: {coverage_summary.total_days}
- Local research days: {coverage_summary.local_research_days}
- Placeholder days: {coverage_summary.placeholder_days}
- Future placeholder days: {coverage_summary.future_placeholder_days}
- Mixed context days: {coverage_summary.mixed_context_days}
- Astro daily available days: {coverage_summary.astro_daily_available_days}
- Financial stress available days: {coverage_summary.financial_stress_available_days}
- Market daily available days: {coverage_summary.market_daily_available_days}
- Macro daily available days: {coverage_summary.macro_daily_available_days}
- Data sources: {', '.join(coverage_summary.data_sources) or 'none'}
- Date range mode: {coverage_summary.date_range_mode}

### Asset coverage
{asset_lines or '- No asset coverage data'}

### Coverage notes
{note_lines}
"""


def render_daily_asset_contexts(
    snapshot: DailyScenarioSnapshot,
    *,
    language: ReportLanguage,
) -> str:
    if not snapshot.asset_contexts:
        return "無" if language == "zh-Hant" else "none"
    if language == "zh-Hant":
        return "; ".join(
            (
                f"{context.asset}: {context.market_daily}, "
                f"{context.series_type}, supported={context.supported}"
            )
            for context in snapshot.asset_contexts
        )
    return "; ".join(
        (
            f"{context.asset}: {context.market_daily}, "
            f"{context.series_type}, supported={context.supported}"
        )
        for context in snapshot.asset_contexts
    )


def render_llm_report_markdown(report: ScenarioReport, *, language: ReportLanguage) -> str:
    llm_report = report.llm_report
    if llm_report is None:
        if language == "zh-Hant":
            return "此情境未請求 LLM 輔助報告。"
        return "No LLM-assisted scenario report was requested."

    if language == "zh-Hant":
        if llm_report.status != "completed":
            return f"""- 狀態：{llm_report.status}
- 提供者：{llm_report.provider}
- 模型：{llm_report.model or '未設定'}
- 訊息：{llm_report.executive_summary}
- 網路呼叫：{llm_report.provenance.network_call_performed}
- 輸出驗證：{llm_report.provenance.output_validation_status}
- 安全檢查：{llm_report.provenance.safety_check_status}
"""
        daily_lines = "\n".join(
            (
                f"### {item.date.isoformat()}\n"
                f"- 摘要：{item.summary}\n"
                f"- 關鍵脈絡：{'; '.join(item.key_context)}\n"
                f"- 代理焦點：{'; '.join(item.agent_focus)}\n"
                f"- 注意事項：{'; '.join(item.caveats)}"
            )
            for item in llm_report.daily_highlights
        )
        agent_lines = "\n".join(
            (
                f"### {item.agent_name}\n"
                f"- 解讀：{item.interpretation}\n"
                f"- 風險焦點：{'; '.join(item.risk_focus)}\n"
                f"- 注意事項：{'; '.join(item.caveats)}"
            )
            for item in llm_report.agent_interpretations
        )
        indicator_lines = "\n".join(
            (
                f"- {item.date.isoformat()} {item.asset}: "
                f"{item.sentiment_stress_support:.1f} ({item.label}) — "
                f"{item.rationale}"
            )
            for item in llm_report.asset_stress_indicators
        )
        return f"""- 狀態：{llm_report.status}
- 提供者：{llm_report.provider}
- 模型：{llm_report.model or '未設定'}
- 網路呼叫：{llm_report.provenance.network_call_performed}
- 輸出驗證：{llm_report.provenance.output_validation_status}
- 安全檢查：{llm_report.provenance.safety_check_status}

### 執行摘要
{llm_report.executive_summary}

### 情境解讀
{llm_report.scenario_reading}

### 每日重點
{daily_lines or '無'}

### 代理解讀
{agent_lines or '無'}

### 資產情緒壓力支撐指標
{indicator_lines or '無'}

### 風險主題
{chr(10).join(f'- {item}' for item in llm_report.risk_themes) or '- 無'}

### 注意事項
{chr(10).join(f'- {item}' for item in llm_report.caveats) or '- 無'}

### 免責聲明
{llm_report.disclaimer}
"""

    if llm_report.status != "completed":
        return f"""- Status: {llm_report.status}
- Provider: {llm_report.provider}
- Model: {llm_report.model or 'not configured'}
- Message: {llm_report.executive_summary}
- Network call performed: {llm_report.provenance.network_call_performed}
- Output validation: {llm_report.provenance.output_validation_status}
- Safety check: {llm_report.provenance.safety_check_status}
"""
    daily_lines = "\n".join(
        (
            f"### {item.date.isoformat()}\n"
            f"- Summary: {item.summary}\n"
            f"- Key context: {'; '.join(item.key_context)}\n"
            f"- Agent focus: {'; '.join(item.agent_focus)}\n"
            f"- Caveats: {'; '.join(item.caveats)}"
        )
        for item in llm_report.daily_highlights
    )
    agent_lines = "\n".join(
        (
            f"### {item.agent_name}\n"
            f"- Interpretation: {item.interpretation}\n"
            f"- Risk focus: {'; '.join(item.risk_focus)}\n"
            f"- Caveats: {'; '.join(item.caveats)}"
        )
        for item in llm_report.agent_interpretations
    )
    indicator_lines = "\n".join(
        (
            f"- {item.date.isoformat()} {item.asset}: "
            f"{item.sentiment_stress_support:.1f} ({item.label}) — "
            f"{item.rationale}"
        )
        for item in llm_report.asset_stress_indicators
    )
    return f"""- Status: {llm_report.status}
- Provider: {llm_report.provider}
- Model: {llm_report.model or 'not configured'}
- Network call performed: {llm_report.provenance.network_call_performed}
- Output validation: {llm_report.provenance.output_validation_status}
- Safety check: {llm_report.provenance.safety_check_status}

### Executive summary
{llm_report.executive_summary}

### Scenario reading
{llm_report.scenario_reading}

### Daily highlights
{daily_lines or 'none'}

### Agent interpretations
{agent_lines or 'none'}

### Asset stress support indicators
{indicator_lines or '- none'}

### Risk themes
{chr(10).join(f'- {item}' for item in llm_report.risk_themes) or '- none'}

### Caveats
{chr(10).join(f'- {item}' for item in llm_report.caveats) or '- none'}

### Disclaimer
{llm_report.disclaimer}
"""


def render_worldline_markdown(report: ScenarioReport, *, language: ReportLanguage) -> str:
    worldline = report.worldline_simulation
    if worldline is None:
        return "此情境未包含模擬世界線。" if language == "zh-Hant" else "No simulated worldline is available."

    if language == "zh-Hant":
        day_lines = "\n\n".join(
            (
                f"### {day.date.isoformat()}\n"
                f"- 輸入脈絡：{day.input_context_summary}\n"
                f"- 推演前狀態：sentiment={day.world_state_before.sentiment_state}; "
                f"narrative={day.world_state_before.narrative_pressure}; "
                f"leverage={day.world_state_before.leverage_pressure}; "
                f"liquidity={day.world_state_before.liquidity_pressure}; "
                f"volatility={day.world_state_before.volatility_pressure}; "
                f"stress={day.world_state_before.stress_pressure}\n"
                "- 群體事件：\n"
                + "\n".join(
                    (
                        f"  - {event.agent_name}: {event.what_happened} "
                        f"對明天：{event.impact_on_tomorrow}"
                    )
                    for event in day.agent_events
                )
                + "\n"
                "- 模擬因果鏈：\n"
                + "\n".join(
                    f"  - {link.source} -> {link.target}: {link.description}"
                    for link in day.causal_links
                )
                + "\n"
                f"- 明日情境鋪墊：{day.next_day_update}\n"
                f"- 推演後狀態：sentiment={day.world_state_after.sentiment_state}; "
                f"regime={day.world_state_after.regime_label}; "
                f"narrative={day.world_state_after.narrative_pressure}; "
                f"leverage={day.world_state_after.leverage_pressure}; "
                f"liquidity={day.world_state_after.liquidity_pressure}; "
                f"volatility={day.world_state_after.volatility_pressure}; "
                f"stress={day.world_state_after.stress_pressure}\n"
                f"- 免責：{day.disclaimer}"
            )
            for day in worldline.days
        )
        return f"""- 狀態：{worldline.status}
- 模式：{worldline.mode}
- 推演天數：{worldline.horizon_days}
- 摘要：{worldline.summary}

{day_lines}

### 注意事項
{chr(10).join(f'- {item}' for item in worldline.caveats) or '- 無'}
"""

    day_lines = "\n\n".join(
        (
            f"### {day.date.isoformat()}\n"
            f"- Input context: {day.input_context_summary}\n"
            f"- World state before: sentiment={day.world_state_before.sentiment_state}; "
            f"narrative={day.world_state_before.narrative_pressure}; "
            f"leverage={day.world_state_before.leverage_pressure}; "
            f"liquidity={day.world_state_before.liquidity_pressure}; "
            f"volatility={day.world_state_before.volatility_pressure}; "
            f"stress={day.world_state_before.stress_pressure}\n"
            "- Agent events:\n"
            + "\n".join(
                (
                    f"  - {event.agent_name}: {event.what_happened} "
                    f"Tomorrow setup: {event.impact_on_tomorrow}"
                )
                for event in day.agent_events
            )
            + "\n"
            "- Simulated causal links:\n"
            + "\n".join(
                f"  - {link.source} -> {link.target}: {link.description}"
                for link in day.causal_links
            )
            + "\n"
            f"- Next-day setup: {day.next_day_update}\n"
            f"- World state after: sentiment={day.world_state_after.sentiment_state}; "
            f"regime={day.world_state_after.regime_label}; "
            f"narrative={day.world_state_after.narrative_pressure}; "
            f"leverage={day.world_state_after.leverage_pressure}; "
            f"liquidity={day.world_state_after.liquidity_pressure}; "
            f"volatility={day.world_state_after.volatility_pressure}; "
            f"stress={day.world_state_after.stress_pressure}\n"
            f"- Disclaimer: {day.disclaimer}"
        )
        for day in worldline.days
    )
    return f"""- Status: {worldline.status}
- Mode: {worldline.mode}
- Horizon days: {worldline.horizon_days}
- Summary: {worldline.summary}

{day_lines}

### Caveats
{chr(10).join(f'- {item}' for item in worldline.caveats) or '- none'}
"""


def render_markdown(report: ScenarioReport) -> str:
    language: ReportLanguage = report.language or "en"
    is_chinese = language == "zh-Hant"
    coverage_lines = render_coverage_markdown(report.coverage_summary, language=language)
    llm_lines = render_llm_report_markdown(report, language=language)
    worldline_lines = render_worldline_markdown(report, language=language)

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
                    f"- 市場序列脈絡：{render_daily_asset_contexts(snapshot, language=language)}\n"
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

## 情境資料覆蓋摘要
{coverage_lines}

## 模擬世界線
{worldline_lines}

## LLM 情境報告
{llm_lines}

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
                f"- Market series context: {render_daily_asset_contexts(snapshot, language=language)}\n"
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

## Context Coverage Summary
{coverage_lines}

## Simulated Worldline
{worldline_lines}

## LLM Scenario Report
{llm_lines}

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
        api_key=request.llm_api_key,
        real_enabled=request.llm_real_enabled,
        timeout_seconds=request.llm_timeout_seconds,
        max_output_tokens=request.llm_max_output_tokens,
    )
    created_at = datetime.now(UTC)
    report_id = scenario_id or create_scenario_id(request.title, created_at)
    agent_outputs = [build_agent_output(agent, request.language) for agent in agents]
    asset_profiles = profiles_for_assets(request.assets)
    daily_timeline = build_daily_timeline(request, agents)
    coverage_summary = build_coverage_summary(
        daily_timeline,
        request.assets,
        created_at=created_at,
        language=request.language,
    )
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
        asset_profiles=asset_profiles,
        agents=agents,
        daily_context=daily_context,
        simulation_summary=summary,
        scenario_summary=summary,
        agent_outputs=agent_outputs,
        risks=risk_themes,
        risk_themes=risk_themes,
        daily_timeline=daily_timeline,
        coverage_summary=coverage_summary,
        caveats=safety_caveats_for(request.language),
        provenance=provenance,
        visibility=request.visibility,
        mode=request.mode,
        language=request.language,
        llm_report=None,
        markdown_report="",
        disclaimer=disclaimer_for(request.language),
    )
    llm_report = generate_llm_scenario_report(request, report)
    report = report.model_copy(update={"llm_report": llm_report})
    worldline_simulation = generate_worldline_simulation(report)
    report = report.model_copy(update={"worldline_simulation": worldline_simulation})
    return report.model_copy(update={"markdown_report": render_markdown(report)})
