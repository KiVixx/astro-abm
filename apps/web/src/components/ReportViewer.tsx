"use client";

import { useMemo, useState } from "react";
import { SafetyPhrases } from "./SafetyPhrases";
import type {
  DailyDataCoverage,
  DailyResearchSignals,
  DailyScenarioSnapshot,
  ScenarioReport,
} from "@/lib/types";
import { formatAgentName, formatAgentProfileName, formatEnumLabel } from "@/i18n/labels";
import { interpolate, useI18n } from "@/i18n/useI18n";

const LONG_TIMELINE_WARNING_DAYS = 120;
const TIMELINE_VISIBLE_DAY_LIMIT = 366;

function JsonBlock({ value }: { value: unknown }) {
  return <pre>{JSON.stringify(value, null, 2)}</pre>;
}

function MarkdownReportBlock({ markdown }: { markdown: string }) {
  const { t } = useI18n();
  const [showMarkdown, setShowMarkdown] = useState(false);

  return (
    <div className="stack">
      <p className="muted">
        {t("report.rawMarkdownHelp")}
      </p>
      <button onClick={() => setShowMarkdown((current) => !current)} type="button">
        {showMarkdown ? t("report.hideMarkdown") : t("report.showMarkdown")}
      </button>
      {showMarkdown ? <pre>{markdown}</pre> : null}
    </div>
  );
}

function uniqueSorted(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort();
}

function getMonthKey(dateValue: string) {
  return dateValue.slice(0, 7);
}

function dataCoverageFor(snapshot: DailyScenarioSnapshot): DailyDataCoverage {
  return (
    snapshot.data_coverage || {
      astro_daily: "unknown",
      financial_stress_daily: "unknown",
      market_daily: "unknown",
      macro_daily: "unknown",
      source: "legacy_report",
      notes: ["This saved report does not include PR5 data coverage fields."],
    }
  );
}

function researchSignalsFor(snapshot: DailyScenarioSnapshot): DailyResearchSignals {
  return (
    snapshot.research_signals || {
      stress_regime: snapshot.market_context.stress_regime || "unknown",
      volatility_regime: snapshot.market_context.volatility_regime || "unknown",
      liquidity_regime: snapshot.market_context.liquidity_regime || "unknown",
      astro_activity: snapshot.astro_context.intensity || "unknown",
      data_quality: "legacy_report",
    }
  );
}

function snapshotSearchText(snapshot: DailyScenarioSnapshot) {
  const dataCoverage = dataCoverageFor(snapshot);
  const researchSignals = researchSignalsFor(snapshot);
  return [
    snapshot.date,
    snapshot.astro_context.intensity,
    snapshot.astro_context.summary,
    snapshot.astro_context.event_tags.join(" "),
    snapshot.market_context.stress_regime,
    snapshot.market_context.volatility_regime,
    snapshot.market_context.liquidity_regime,
    snapshot.market_context.summary,
    snapshot.daily_risk_themes.join(" "),
    snapshot.confidence,
    dataCoverage.source,
    dataCoverage.notes.join(" "),
    researchSignals.data_quality,
    researchSignals.astro_activity,
    snapshot.agent_states
      .map((state) =>
        [
          state.agent_name,
          state.mood,
          state.risk_appetite,
          state.likely_reaction,
          state.attention_triggers.join(" "),
        ].join(" "),
      )
      .join(" "),
  ]
    .join(" ")
    .toLowerCase();
}

function DailySnapshotDetail({ snapshot }: { snapshot: DailyScenarioSnapshot }) {
  const { t } = useI18n();
  const dataCoverage = dataCoverageFor(snapshot);
  const researchSignals = researchSignalsFor(snapshot);

  return (
    <div className="timeline-detail-body">
      <p>{snapshot.daily_summary}</p>
      <div className="grid">
        <div>
          <h3>{t("report.astroContext")}</h3>
          <p>{snapshot.astro_context.summary}</p>
          <div className="tag-row">
            {snapshot.astro_context.event_tags.map((tag) => (
              <span className="tag" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div>
          <h3>{t("report.marketContext")}</h3>
          <p>{snapshot.market_context.summary}</p>
          <div className="tag-row">
            <span className="tag">
              {t("common.stress")}:{" "}
              {formatEnumLabel(t, "stress_regime", snapshot.market_context.stress_regime)}
            </span>
            <span className="tag">
              {t("common.volatility")}:{" "}
              {formatEnumLabel(
                t,
                "volatility_regime",
                snapshot.market_context.volatility_regime,
              )}
            </span>
            <span className="tag">
              {t("common.liquidity")}:{" "}
              {formatEnumLabel(
                t,
                "liquidity_regime",
                snapshot.market_context.liquidity_regime,
              )}
            </span>
          </div>
        </div>
      </div>
      <h3>{t("report.agentStates")}</h3>
      <div className="stack">
        {snapshot.agent_states.map((state) => (
          <div className="nested-panel" key={state.agent_id}>
            <strong>{formatAgentName(t, state.agent_id, state.agent_name)}</strong>
            <p>{state.likely_reaction}</p>
            <div className="tag-row">
              <span className="tag">{state.mood}</span>
              <span className="tag">{state.risk_appetite}</span>
              {state.attention_triggers.map((trigger) => (
                <span className="tag" key={trigger}>
                  {trigger}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="grid section">
        <div>
          <h3>{t("report.dataCoverage")}</h3>
          <div className="tag-row">
            <span className="tag">
              {t("common.source")}:{" "}
              {formatEnumLabel(t, "data_source", dataCoverage.source)}
            </span>
            <span className="tag">
              {t("common.astro")}:{" "}
              {formatEnumLabel(t, "coverage_status", dataCoverage.astro_daily)}
            </span>
            <span className="tag">
              {t("common.stress")}:{" "}
              {formatEnumLabel(
                t,
                "coverage_status",
                dataCoverage.financial_stress_daily,
              )}
            </span>
            <span className="tag">
              {t("common.market")}:{" "}
              {formatEnumLabel(t, "coverage_status", dataCoverage.market_daily)}
            </span>
            <span className="tag">
              {t("common.macro")}:{" "}
              {formatEnumLabel(t, "coverage_status", dataCoverage.macro_daily)}
            </span>
          </div>
          <ul>
            {dataCoverage.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3>{t("report.researchSignals")}</h3>
          <div className="tag-row">
            <span className="tag">
              {t("common.stress")}:{" "}
              {formatEnumLabel(t, "stress_regime", researchSignals.stress_regime)}
            </span>
            <span className="tag">
              {t("common.volatility")}:{" "}
              {formatEnumLabel(t, "volatility_regime", researchSignals.volatility_regime)}
            </span>
            <span className="tag">
              {t("common.liquidity")}:{" "}
              {formatEnumLabel(t, "liquidity_regime", researchSignals.liquidity_regime)}
            </span>
            <span className="tag">{t("common.astro")}: {researchSignals.astro_activity}</span>
            <span className="tag">
              {t("common.quality")}:{" "}
              {formatEnumLabel(t, "data_quality", researchSignals.data_quality)}
            </span>
          </div>
        </div>
      </div>
      <div className="grid section">
        <div>
          <h3>{t("report.dailyRiskThemes")}</h3>
          <ul>
            {snapshot.daily_risk_themes.map((theme) => (
              <li key={theme}>{theme}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3>{t("report.caveats")}</h3>
          <ul>
            {snapshot.caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        </div>
      </div>
      <p className="notice">{snapshot.disclaimer}</p>
    </div>
  );
}

export function ReportViewer({ report }: { report: ScenarioReport }) {
  const { t } = useI18n();
  const scenarioSummary = report.scenario_summary || report.simulation_summary;
  const riskThemes = report.risk_themes?.length ? report.risk_themes : report.risks;
  const dailyTimeline = report.daily_timeline || [];
  const [timelineSearch, setTimelineSearch] = useState("");
  const [monthFilter, setMonthFilter] = useState("all");
  const [astroFilter, setAstroFilter] = useState("all");
  const [stressFilter, setStressFilter] = useState("all");
  const [volatilityFilter, setVolatilityFilter] = useState("all");
  const [liquidityFilter, setLiquidityFilter] = useState("all");
  const [dataSourceFilter, setDataSourceFilter] = useState("all");
  const [dataQualityFilter, setDataQualityFilter] = useState("all");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const timelineFilters = useMemo(() => {
    return {
      months: uniqueSorted(dailyTimeline.map((snapshot) => getMonthKey(snapshot.date))),
      astroIntensities: uniqueSorted(
        dailyTimeline.map((snapshot) => snapshot.astro_context.intensity),
      ),
      stressRegimes: uniqueSorted(
        dailyTimeline.map((snapshot) => snapshot.market_context.stress_regime),
      ),
      volatilityRegimes: uniqueSorted(
        dailyTimeline.map((snapshot) => snapshot.market_context.volatility_regime),
      ),
      liquidityRegimes: uniqueSorted(
        dailyTimeline.map((snapshot) => snapshot.market_context.liquidity_regime),
      ),
      dataSources: uniqueSorted(
        dailyTimeline.map((snapshot) => dataCoverageFor(snapshot).source),
      ),
      dataQualities: uniqueSorted(
        dailyTimeline.map((snapshot) => researchSignalsFor(snapshot).data_quality),
      ),
    };
  }, [dailyTimeline]);

  const filteredTimeline = useMemo(() => {
    const normalizedSearch = timelineSearch.trim().toLowerCase();
    return dailyTimeline.filter((snapshot) => {
      if (monthFilter !== "all" && getMonthKey(snapshot.date) !== monthFilter) {
        return false;
      }
      if (astroFilter !== "all" && snapshot.astro_context.intensity !== astroFilter) {
        return false;
      }
      if (
        stressFilter !== "all" &&
        snapshot.market_context.stress_regime !== stressFilter
      ) {
        return false;
      }
      if (
        volatilityFilter !== "all" &&
        snapshot.market_context.volatility_regime !== volatilityFilter
      ) {
        return false;
      }
      if (
        liquidityFilter !== "all" &&
        snapshot.market_context.liquidity_regime !== liquidityFilter
      ) {
        return false;
      }
      if (dataSourceFilter !== "all" && dataCoverageFor(snapshot).source !== dataSourceFilter) {
        return false;
      }
      if (
        dataQualityFilter !== "all" &&
        researchSignalsFor(snapshot).data_quality !== dataQualityFilter
      ) {
        return false;
      }
      if (!normalizedSearch) {
        return true;
      }
      return snapshotSearchText(snapshot).includes(normalizedSearch);
    });
  }, [
    astroFilter,
    dailyTimeline,
    dataQualityFilter,
    dataSourceFilter,
    liquidityFilter,
    monthFilter,
    stressFilter,
    timelineSearch,
    volatilityFilter,
  ]);

  const displayedTimeline = filteredTimeline.slice(0, TIMELINE_VISIBLE_DAY_LIMIT);
  const groupedTimeline = useMemo(() => {
    const groups = new Map<string, DailyScenarioSnapshot[]>();
    for (const snapshot of displayedTimeline) {
      const monthKey = getMonthKey(snapshot.date);
      const existing = groups.get(monthKey) || [];
      existing.push(snapshot);
      groups.set(monthKey, existing);
    }
    return Array.from(groups.entries());
  }, [displayedTimeline]);

  const selectedSnapshot = selectedDate
    ? displayedTimeline.find((snapshot) => snapshot.date === selectedDate)
    : null;

  const resetTimelineFilters = () => {
    setTimelineSearch("");
    setMonthFilter("all");
    setAstroFilter("all");
    setStressFilter("all");
    setVolatilityFilter("all");
    setLiquidityFilter("all");
    setDataSourceFilter("all");
    setDataQualityFilter("all");
  };

  const expandSelectedOrFirstVisible = () => {
    if (
      selectedDate &&
      displayedTimeline.some((snapshot) => snapshot.date === selectedDate)
    ) {
      return;
    }
    setSelectedDate(displayedTimeline[0]?.date || null);
  };

  return (
    <article className="stack">
      <section className="card">
        <h1>{report.title}</h1>
        {report.description ? <p className="lead">{report.description}</p> : null}
        <div className="tag-row">
          <span className="tag">
            {report.start_date} {t("common.to")} {report.end_date}
          </span>
          {report.assets.map((asset) => (
            <span className="tag" key={asset}>
              {asset}
            </span>
          ))}
          <span className="tag">
            {formatEnumLabel(t, "visibility", report.visibility)}
          </span>
        </div>
      </section>

      <section className="card">
        <h2>{t("report.summary")}</h2>
        <p>{scenarioSummary}</p>
      </section>

      <section className="card">
        <h2>{t("report.dailyTimeline")}</h2>
        {dailyTimeline.length ? (
          <div className="stack">
            {dailyTimeline.length > LONG_TIMELINE_WARNING_DAYS ? (
              <div className="notice">
                {interpolate(t("report.longTimelineWarning"), {
                  count: dailyTimeline.length,
                  limit: TIMELINE_VISIBLE_DAY_LIMIT,
                })}
              </div>
            ) : null}
            <div className="timeline-toolbar">
              <label className="form-field">
                {t("report.searchTimeline")}
                <input
                  onChange={(event) => setTimelineSearch(event.target.value)}
                  placeholder={t("report.searchPlaceholder")}
                  type="search"
                  value={timelineSearch}
                />
              </label>
              <label className="form-field">
                {t("report.month")}
                <select
                  onChange={(event) => setMonthFilter(event.target.value)}
                  value={monthFilter}
                >
                  <option value="all">{t("report.allMonths")}</option>
                  {timelineFilters.months.map((month) => (
                    <option key={month} value={month}>
                      {month}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                {t("common.astro")}
                <select
                  onChange={(event) => setAstroFilter(event.target.value)}
                  value={astroFilter}
                >
                  <option value="all">{t("report.allIntensity")}</option>
                  {timelineFilters.astroIntensities.map((intensity) => (
                    <option key={intensity} value={intensity}>
                      {formatEnumLabel(t, "astro_intensity", intensity)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                {t("common.stress")}
                <select
                  onChange={(event) => setStressFilter(event.target.value)}
                  value={stressFilter}
                >
                  <option value="all">{t("report.allStress")}</option>
                  {timelineFilters.stressRegimes.map((regime) => (
                    <option key={regime} value={regime}>
                      {formatEnumLabel(t, "stress_regime", regime)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                {t("common.volatility")}
                <select
                  onChange={(event) => setVolatilityFilter(event.target.value)}
                  value={volatilityFilter}
                >
                  <option value="all">{t("report.allVolatility")}</option>
                  {timelineFilters.volatilityRegimes.map((regime) => (
                    <option key={regime} value={regime}>
                      {formatEnumLabel(t, "volatility_regime", regime)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                {t("common.liquidity")}
                <select
                  onChange={(event) => setLiquidityFilter(event.target.value)}
                  value={liquidityFilter}
                >
                  <option value="all">{t("report.allLiquidity")}</option>
                  {timelineFilters.liquidityRegimes.map((regime) => (
                    <option key={regime} value={regime}>
                      {formatEnumLabel(t, "liquidity_regime", regime)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                {t("report.dataSource")}
                <select
                  onChange={(event) => setDataSourceFilter(event.target.value)}
                  value={dataSourceFilter}
                >
                  <option value="all">{t("report.allSources")}</option>
                  {timelineFilters.dataSources.map((source) => (
                    <option key={source} value={source}>
                      {formatEnumLabel(t, "data_source", source)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                {t("report.dataQuality")}
                <select
                  onChange={(event) => setDataQualityFilter(event.target.value)}
                  value={dataQualityFilter}
                >
                  <option value="all">{t("report.allQuality")}</option>
                  {timelineFilters.dataQualities.map((quality) => (
                    <option key={quality} value={quality}>
                      {formatEnumLabel(t, "data_quality", quality)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="timeline-actions">
              <span className="muted">
                {t("report.showing")} {displayedTimeline.length} {t("common.of")}{" "}
                {filteredTimeline.length} {t("report.filteredDays")}{" "}
                {dailyTimeline.length} {t("report.total")}.
              </span>
              <div className="button-row">
                <button onClick={expandSelectedOrFirstVisible} type="button">
                  {t("report.expandSelected")}
                </button>
                <button onClick={() => setSelectedDate(null)} type="button">
                  {t("report.collapseAll")}
                </button>
                <button onClick={resetTimelineFilters} type="button">
                  {t("report.resetFilters")}
                </button>
              </div>
            </div>
            {filteredTimeline.length > TIMELINE_VISIBLE_DAY_LIMIT ? (
              <div className="notice">
                {t("report.filterLongWarning")}
              </div>
            ) : null}
            {groupedTimeline.length ? (
              <div className="timeline-list">
                {groupedTimeline.map(([month, snapshots]) => (
                  <div className="timeline-month" key={month}>
                    <h3>{month}</h3>
                    <div className="timeline-table">
                      {snapshots.map((snapshot) => {
                        const isSelected = snapshot.date === selectedDate;
                        const researchSignals = researchSignalsFor(snapshot);
                        return (
                          <div className="timeline-detail" key={snapshot.date}>
                            <button
                              className="timeline-summary"
                              onClick={() =>
                                setSelectedDate(isSelected ? null : snapshot.date)
                              }
                              type="button"
                            >
                              <span>
                                <strong>{snapshot.date}</strong>
                                <br />
                                <span className="muted">
                                  {t("common.day")} {snapshot.day_index}
                                </span>
                              </span>
                              <span>
                                {formatEnumLabel(
                                  t,
                                  "astro_intensity",
                                  snapshot.astro_context.intensity,
                                )}
                              </span>
                              <span>
                                {formatEnumLabel(
                                  t,
                                  "stress_regime",
                                  snapshot.market_context.stress_regime,
                                )}
                              </span>
                              <span>
                                {formatEnumLabel(
                                  t,
                                  "volatility_regime",
                                  snapshot.market_context.volatility_regime,
                                )}
                              </span>
                              <span>
                                {formatEnumLabel(
                                  t,
                                  "liquidity_regime",
                                  snapshot.market_context.liquidity_regime,
                                )}
                              </span>
                              <span>
                                {snapshot.daily_risk_themes.slice(0, 2).join(", ")}
                              </span>
                              <span>
                                {formatEnumLabel(
                                  t,
                                  "data_quality",
                                  researchSignals.data_quality,
                                )}
                                <br />
                                <span className="muted">{snapshot.confidence}</span>
                              </span>
                            </button>
                            {isSelected ? <DailySnapshotDetail snapshot={snapshot} /> : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="notice">{t("report.noDailyMatches")}</div>
            )}
            {selectedSnapshot ? (
              <div className="notice">
                {interpolate(t("report.selectedDay"), { date: selectedSnapshot.date })}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="notice">
            {t("report.noTimeline")}
          </div>
        )}
      </section>

      <section className="card">
        <h2>{t("report.agents")}</h2>
        <div className="grid">
          {report.agents.map((agent) => (
            <div key={agent.agent_id}>
              <h3>{formatAgentProfileName(t, agent)}</h3>
              <p className="muted">{agent.description}</p>
              <div className="tag-row">
                <span className="tag">
                  {formatEnumLabel(t, "agent_category", agent.category)}
                </span>
                <span className="tag">{agent.risk_tolerance}</span>
                <span className="tag">{agent.time_horizon}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>{t("report.dailyContext")}</h2>
        <JsonBlock value={report.daily_context} />
      </section>

      <section className="card">
        <h2>{t("report.agentOutputs")}</h2>
        <div className="stack">
          {report.agent_outputs.map((output) => (
            <div key={output.agent_id}>
              <h3>{formatAgentName(t, output.agent_id, output.agent_name)}</h3>
              <p>{output.behavior_summary}</p>
              <p>{output.likely_reaction}</p>
              <div className="tag-row">
                <span className="tag">{output.role}</span>
                <span className="tag">{output.risk_appetite}</span>
                <span className="tag">{output.confidence}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid">
        <div className="card">
          <h2>{t("report.riskThemes")}</h2>
          <ul>
            {riskThemes.map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h2>{t("report.caveats")}</h2>
          <ul>
            {report.caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="card">
        <h2>{t("report.provenance")}</h2>
        <JsonBlock value={report.provenance} />
      </section>

      <section className="notice">
        <h2>{t("report.disclaimer")}</h2>
        <SafetyPhrases />
        <p>{report.disclaimer}</p>
      </section>

      <section className="card">
        <h2>{t("report.markdownReport")}</h2>
        <MarkdownReportBlock markdown={report.markdown_report} />
      </section>
    </article>
  );
}
