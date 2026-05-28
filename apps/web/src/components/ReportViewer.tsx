"use client";

import { useMemo, useState } from "react";
import type { DailyScenarioSnapshot, ScenarioReport } from "@/lib/types";

const LONG_TIMELINE_WARNING_DAYS = 120;
const TIMELINE_VISIBLE_DAY_LIMIT = 366;

function JsonBlock({ value }: { value: unknown }) {
  return <pre>{JSON.stringify(value, null, 2)}</pre>;
}

function uniqueSorted(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort();
}

function getMonthKey(dateValue: string) {
  return dateValue.slice(0, 7);
}

function snapshotSearchText(snapshot: DailyScenarioSnapshot) {
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
  return (
    <div className="timeline-detail-body">
      <p>{snapshot.daily_summary}</p>
      <div className="grid">
        <div>
          <h3>Astro context</h3>
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
          <h3>Market context</h3>
          <p>{snapshot.market_context.summary}</p>
          <div className="tag-row">
            <span className="tag">stress: {snapshot.market_context.stress_regime}</span>
            <span className="tag">
              volatility: {snapshot.market_context.volatility_regime}
            </span>
            <span className="tag">
              liquidity: {snapshot.market_context.liquidity_regime}
            </span>
          </div>
        </div>
      </div>
      <h3>Agent states</h3>
      <div className="stack">
        {snapshot.agent_states.map((state) => (
          <div className="nested-panel" key={state.agent_id}>
            <strong>{state.agent_name}</strong>
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
          <h3>Daily risk themes</h3>
          <ul>
            {snapshot.daily_risk_themes.map((theme) => (
              <li key={theme}>{theme}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3>Caveats</h3>
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
  const scenarioSummary = report.scenario_summary || report.simulation_summary;
  const riskThemes = report.risk_themes?.length ? report.risk_themes : report.risks;
  const dailyTimeline = report.daily_timeline || [];
  const [timelineSearch, setTimelineSearch] = useState("");
  const [monthFilter, setMonthFilter] = useState("all");
  const [astroFilter, setAstroFilter] = useState("all");
  const [stressFilter, setStressFilter] = useState("all");
  const [volatilityFilter, setVolatilityFilter] = useState("all");
  const [liquidityFilter, setLiquidityFilter] = useState("all");
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
      if (!normalizedSearch) {
        return true;
      }
      return snapshotSearchText(snapshot).includes(normalizedSearch);
    });
  }, [
    astroFilter,
    dailyTimeline,
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
            {report.start_date} to {report.end_date}
          </span>
          {report.assets.map((asset) => (
            <span className="tag" key={asset}>
              {asset}
            </span>
          ))}
          <span className="tag">{report.visibility}</span>
        </div>
      </section>

      <section className="card">
        <h2>Summary</h2>
        <p>{scenarioSummary}</p>
      </section>

      <section className="card">
        <h2>Daily Timeline</h2>
        {dailyTimeline.length ? (
          <div className="stack">
            {dailyTimeline.length > LONG_TIMELINE_WARNING_DAYS ? (
              <div className="notice">
                This scenario contains {dailyTimeline.length} daily snapshots. Use
                search, month grouping, and filters to keep review focused. If a
                filter still returns more than {TIMELINE_VISIBLE_DAY_LIMIT} days,
                only the first {TIMELINE_VISIBLE_DAY_LIMIT} are shown.
              </div>
            ) : null}
            <div className="timeline-toolbar">
              <label className="form-field">
                Search timeline
                <input
                  onChange={(event) => setTimelineSearch(event.target.value)}
                  placeholder="Search date, agent, regime, risk theme..."
                  type="search"
                  value={timelineSearch}
                />
              </label>
              <label className="form-field">
                Month
                <select
                  onChange={(event) => setMonthFilter(event.target.value)}
                  value={monthFilter}
                >
                  <option value="all">All months</option>
                  {timelineFilters.months.map((month) => (
                    <option key={month} value={month}>
                      {month}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                Astro
                <select
                  onChange={(event) => setAstroFilter(event.target.value)}
                  value={astroFilter}
                >
                  <option value="all">All intensity</option>
                  {timelineFilters.astroIntensities.map((intensity) => (
                    <option key={intensity} value={intensity}>
                      {intensity}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                Stress
                <select
                  onChange={(event) => setStressFilter(event.target.value)}
                  value={stressFilter}
                >
                  <option value="all">All stress</option>
                  {timelineFilters.stressRegimes.map((regime) => (
                    <option key={regime} value={regime}>
                      {regime}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                Volatility
                <select
                  onChange={(event) => setVolatilityFilter(event.target.value)}
                  value={volatilityFilter}
                >
                  <option value="all">All volatility</option>
                  {timelineFilters.volatilityRegimes.map((regime) => (
                    <option key={regime} value={regime}>
                      {regime}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                Liquidity
                <select
                  onChange={(event) => setLiquidityFilter(event.target.value)}
                  value={liquidityFilter}
                >
                  <option value="all">All liquidity</option>
                  {timelineFilters.liquidityRegimes.map((regime) => (
                    <option key={regime} value={regime}>
                      {regime}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="timeline-actions">
              <span className="muted">
                Showing {displayedTimeline.length} of {filteredTimeline.length} filtered
                days from {dailyTimeline.length} total.
              </span>
              <div className="button-row">
                <button onClick={expandSelectedOrFirstVisible} type="button">
                  Expand selected
                </button>
                <button onClick={() => setSelectedDate(null)} type="button">
                  Collapse all
                </button>
                <button onClick={resetTimelineFilters} type="button">
                  Reset filters
                </button>
              </div>
            </div>
            {filteredTimeline.length > TIMELINE_VISIBLE_DAY_LIMIT ? (
              <div className="notice">
                Filter result is still long. Narrow the search or pick a month to inspect
                later dates beyond the visible limit.
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
                                <span className="muted">Day {snapshot.day_index}</span>
                              </span>
                              <span>{snapshot.astro_context.intensity}</span>
                              <span>{snapshot.market_context.stress_regime}</span>
                              <span>{snapshot.market_context.volatility_regime}</span>
                              <span>{snapshot.market_context.liquidity_regime}</span>
                              <span>
                                {snapshot.daily_risk_themes.slice(0, 2).join(", ")}
                              </span>
                              <span>{snapshot.confidence}</span>
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
              <div className="notice">No daily snapshots match the current filters.</div>
            )}
            {selectedSnapshot ? (
              <div className="notice">
                Selected day: {selectedSnapshot.date}. Only one daily snapshot is
                expanded at a time.
              </div>
            ) : null}
          </div>
        ) : (
          <div className="notice">
            This saved report does not include a daily timeline yet. Open a newly
            generated scenario to inspect individual days.
          </div>
        )}
      </section>

      <section className="card">
        <h2>Agents</h2>
        <div className="grid">
          {report.agents.map((agent) => (
            <div key={agent.agent_id}>
              <h3>{agent.name}</h3>
              <p className="muted">{agent.description}</p>
              <div className="tag-row">
                <span className="tag">{agent.category}</span>
                <span className="tag">{agent.risk_tolerance}</span>
                <span className="tag">{agent.time_horizon}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Daily context</h2>
        <JsonBlock value={report.daily_context} />
      </section>

      <section className="card">
        <h2>Agent outputs</h2>
        <div className="stack">
          {report.agent_outputs.map((output) => (
            <div key={output.agent_id}>
              <h3>{output.agent_name}</h3>
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
          <h2>Risk Themes</h2>
          <ul>
            {riskThemes.map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h2>Caveats</h2>
          <ul>
            {report.caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="card">
        <h2>Provenance</h2>
        <JsonBlock value={report.provenance} />
      </section>

      <section className="notice">
        <h2>Disclaimer</h2>
        <p>{report.disclaimer}</p>
      </section>

      <section className="card">
        <h2>Markdown report</h2>
        <pre>{report.markdown_report}</pre>
      </section>
    </article>
  );
}
