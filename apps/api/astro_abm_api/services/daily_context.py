from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from astro_abm_api.models.report import DailyAstroContext, DailyDataCoverage, DailyMarketContext
from astro_abm_api.models.scenario import ScenarioCreateRequest
from astro_abm_api.services.daily_research_context import DailyResearchContextProvider


def build_daily_context(request: ScenarioCreateRequest) -> dict[str, Any]:
    """Return the MVP daily context placeholder.

    This boundary is intentionally small so later PRs can replace it with
    DuckDB/Parquet reads without changing the public API contract.
    """
    if request.language == "zh-Hant":
        notes = [
            "MVP 使用日線相關性脈絡。",
            "此版本不執行逐點回測。",
        ]
    else:
        notes = [
            "MVP uses daily association context only.",
            "This version does not perform point-in-time backtesting.",
        ]

    return {
        "data_layer": "daily",
        "date_range": {
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
        },
        "assets": request.assets,
        "available_inputs": [
            "daily_ephemeris",
            "financial_stress_daily",
            "market_daily",
            "macro_daily",
        ],
        "notes": notes,
    }


def iter_calendar_days(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)
    return days


def is_zh_hant(request: ScenarioCreateRequest) -> bool:
    return request.language == "zh-Hant"


def regime_label(value: str, *, language: str) -> str:
    if language != "zh-Hant":
        return value
    labels = {
        "calm": "平穩",
        "watchful": "觀望警戒",
        "elevated": "壓力升高",
        "stress": "壓力狀態",
        "compressed": "波動壓縮",
        "normal": "正常",
        "expanded": "波動擴張",
        "orderly": "有序",
        "selective": "選擇性流動性",
        "thin": "偏薄",
        "low": "低",
        "medium": "中",
        "high": "高",
        "placeholder_fallback": "佔位資料回退",
        "local_research_available": "本地研究資料可用",
        "partial_local_research_available": "部分本地研究資料可用",
    }
    return labels.get(value, value)


def stress_risk_theme(stress_regime: str, *, language: str = "en") -> str:
    if language == "zh-Hant":
        return f"壓力狀態檢視：{regime_label(stress_regime, language=language)}"
    if stress_regime == "stress":
        return "elevated_stress_review"
    return f"{stress_regime}_stress_review"


def snapshot_kind(source: str, *, language: str = "en") -> str:
    if source == "local_research_snapshot":
        if language == "zh-Hant":
            return "只讀日線研究脈絡快照"
        return "read-only daily research context snapshot"
    if language == "zh-Hant":
        return "佔位日線相關性快照"
    return "placeholder daily association snapshot"


def confidence_label(data_quality: str) -> str:
    if data_quality == "local_research_available":
        return "low_research_context_confidence"
    if data_quality == "partial_local_research_available":
        return "low_association_confidence"
    return "low_placeholder_confidence"


def astro_event_tags(
    placeholder_tags: list[str],
    *,
    astro_daily_status: str,
    astro_activity: str,
) -> list[str]:
    if astro_daily_status == "available":
        return ["local_astro_daily", f"astro_activity:{astro_activity}"]
    return placeholder_tags


def localize_coverage_notes(coverage: DailyDataCoverage, *, language: str) -> list[str]:
    if language != "zh-Hant":
        return coverage.notes
    translated: list[str] = []
    for note in coverage.notes:
        if note == "financial_stress_daily local snapshot used for stress and volatility tags":
            translated.append("已使用 financial_stress_daily 本地快照生成壓力與波動標籤")
        elif note == "astro_daily_features local snapshot used for astro activity tags":
            translated.append("已使用 astro_daily_features 本地快照生成天象活動標籤")
        elif note == "market_daily_features local snapshot found for selected assets":
            translated.append("已找到所選資產的 market_daily_features 本地快照")
        elif note == "macro_daily_observations local snapshot found for this date":
            translated.append("已找到此日期的 macro_daily_observations 本地快照")
        elif note == "local research context is read-only and used for association tags only":
            translated.append("本地研究脈絡為只讀資料，僅用於相關性標籤")
        elif "does not cover this future date" in note:
            label = note.split(" does not cover", maxsplit=1)[0]
            translated.append(f"{label} 不覆蓋此未來日期；保留佔位標籤")
        elif "missing for this date" in note:
            label = note.split(" missing", maxsplit=1)[0]
            translated.append(f"{label} 此日期缺失；保留佔位標籤")
        elif "availability unknown" in note:
            label = note.split(" availability", maxsplit=1)[0]
            translated.append(f"{label} 可用性未知；保留佔位標籤")
        else:
            translated.append(note)
    return translated


def build_placeholder_daily_contexts(
    request: ScenarioCreateRequest,
    provider: DailyResearchContextProvider | None = None,
) -> list[dict[str, Any]]:
    """Build deterministic daily contexts with optional local research tags."""
    research_provider = provider or DailyResearchContextProvider()
    stress_regimes = ["calm", "watchful", "elevated"]
    volatility_regimes = ["compressed", "normal", "expanded"]
    liquidity_regimes = ["orderly", "selective", "thin"]
    astro_intensities = ["low", "medium", "high"]
    astro_tags = [
        ["daily_ephemeris_placeholder"],
        ["moon_phase_placeholder", "aspect_context_placeholder"],
        ["station_window_placeholder", "aspect_cluster_placeholder"],
    ]

    contexts: list[dict[str, Any]] = []
    language = request.language
    for day_index, current_date in enumerate(
        iter_calendar_days(request.start_date, request.end_date), start=1
    ):
        selector = (day_index - 1) % 3
        stress_regime = stress_regimes[selector]
        volatility_regime = volatility_regimes[(day_index + 1) % 3]
        liquidity_regime = liquidity_regimes[(day_index + 2) % 3]
        intensity = astro_intensities[selector]
        tags = astro_tags[selector]
        research_context = research_provider.context_for_date(
            current_date,
            assets=request.assets,
            fallback_stress_regime=stress_regime,
            fallback_volatility_regime=volatility_regime,
            fallback_liquidity_regime=liquidity_regime,
            fallback_astro_activity=intensity,
        )
        stress_regime = research_context.signals.stress_regime
        volatility_regime = research_context.signals.volatility_regime
        liquidity_regime = research_context.signals.liquidity_regime
        intensity = research_context.signals.astro_activity
        tags = astro_event_tags(
            tags,
            astro_daily_status=research_context.coverage.astro_daily,
            astro_activity=intensity,
        )
        coverage = research_context.coverage.model_copy(
            update={
                "notes": localize_coverage_notes(
                    research_context.coverage,
                    language=language,
                )
            }
        )
        kind = snapshot_kind(coverage.source, language=language)
        confidence = confidence_label(research_context.signals.data_quality)
        if is_zh_hant(request):
            astro_summary = (
                f"{current_date.isoformat()} 的日線天象脈絡使用"
                f"{regime_label(intensity, language=language)}活動標籤；"
                "若本地研究資料可用則採用本地標籤，否則使用 deterministic 佔位標籤。"
            )
            market_summary = (
                f"日線市場脈絡標記為壓力狀態：{regime_label(stress_regime, language=language)}，"
                f"波動狀態：{regime_label(volatility_regime, language=language)}，"
                f"流動性狀態：{regime_label(liquidity_regime, language=language)}；"
                "標籤在可用時來自只讀本地研究脈絡。"
            )
            daily_summary = (
                f"第 {day_index} 天是 {', '.join(request.assets)} 的{kind}。"
                "它用來推演敘事、壓力、波動與流動性脈絡，不做方向性判斷。"
            )
            daily_risk_themes = [
                stress_risk_theme(stress_regime, language=language),
                f"波動意識：{regime_label(volatility_regime, language=language)}",
                f"流動性規劃：{regime_label(liquidity_regime, language=language)}",
            ]
            caveats = [
                "每日脈絡是只讀相關性脈絡；不是逐點回測。",
                "如果本地研究資料不可用，會保留 deterministic 佔位標籤。",
                "此快照不會抓取外部 API，也不會修改研究資料庫。",
            ]
        else:
            astro_summary = (
                f"Daily astro context for {current_date.isoformat()} uses "
                f"{intensity} activity tags from local research when available, "
                "otherwise deterministic placeholder tags."
            )
            market_summary = (
                f"Daily market context marks stress regime: {stress_regime}, "
                f"volatility regime: {volatility_regime}, and liquidity regime: {liquidity_regime}; "
                "tags are read-only local research context when available."
            )
            daily_summary = (
                f"Day {day_index} is a {kind} for "
                f"{', '.join(request.assets)}. It rehearses narrative, stress, "
                "volatility, and liquidity context without making a directional call."
            )
            daily_risk_themes = [
                stress_risk_theme(stress_regime),
                f"{volatility_regime}_volatility_awareness",
                f"{liquidity_regime}_liquidity_planning",
            ]
            caveats = [
                "Daily context is read-only association context; it is not point-in-time backtesting.",
                "If local research data is unavailable, deterministic placeholder tags are retained.",
                "This snapshot never fetches external APIs or mutates research stores.",
            ]
        contexts.append(
            {
                "date": current_date,
                "day_index": day_index,
                "astro_context": DailyAstroContext(
                    summary=astro_summary,
                    event_tags=tags,
                    intensity=intensity,
                ),
                "market_context": DailyMarketContext(
                    summary=market_summary,
                    stress_regime=stress_regime,
                    volatility_regime=volatility_regime,
                    liquidity_regime=liquidity_regime,
                ),
                "daily_risk_themes": daily_risk_themes,
                "daily_summary": daily_summary,
                "confidence": confidence,
                "caveats": caveats,
                "data_coverage": coverage,
                "research_signals": research_context.signals,
            }
        )
    return contexts
