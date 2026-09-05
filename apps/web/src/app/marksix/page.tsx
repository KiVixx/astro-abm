"use client";

import { useEffect, useMemo, useState } from "react";
import { useI18n } from "@/i18n/useI18n";
import {
  createMarkSixWorldlines,
  getMarkSixAstroResearch,
  getMarkSixDraws,
  getMarkSixFrequencies,
  getMarkSixStatus,
} from "@/lib/api";
import type {
  MarkSixDrawRecord,
  MarkSixAstroResearch,
  MarkSixFrequency,
  MarkSixStatus,
  MarkSixWorldlineResponse,
  MarkSixMotionCondition,
} from "@/lib/types";

function Ball({ number, extra = false }: { number: number; extra?: boolean }) {
  return <span className={extra ? "marksix-ball is-extra" : "marksix-ball"}>{number}</span>;
}

export default function MarkSixPage() {
  const { language, t } = useI18n();
  const [status, setStatus] = useState<MarkSixStatus | null>(null);
  const [draws, setDraws] = useState<MarkSixDrawRecord[]>([]);
  const [frequencies, setFrequencies] = useState<MarkSixFrequency[]>([]);
  const [result, setResult] = useState<MarkSixWorldlineResponse | null>(null);
  const [research, setResearch] = useState<MarkSixAstroResearch | null>(null);
  const [researchBody, setResearchBody] = useState("Mercury");
  const [researchCondition, setResearchCondition] = useState<MarkSixMotionCondition>("retrograde");
  const [numberRole, setNumberRole] = useState<"main" | "extra">("main");
  const [researchLoading, setResearchLoading] = useState(false);
  const [horizon, setHorizon] = useState<1 | 3 | 5 | 10>(3);
  const [count, setCount] = useState(1);
  const [worldlineMode, setWorldlineMode] = useState<"uniform_random_demo_v1" | "astro_association_entertainment_v1">("uniform_random_demo_v1");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getMarkSixStatus(), getMarkSixDraws(), getMarkSixFrequencies()])
      .then(([nextStatus, nextDraws, nextFrequencies]) => {
        setStatus(nextStatus);
        setDraws(nextDraws);
        setFrequencies(nextFrequencies);
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)))
      .finally(() => setLoading(false));
  }, []);

  const topFrequencies = useMemo(
    () => [...frequencies].sort((a, b) => b.main_count - a.main_count).slice(0, 8),
    [frequencies],
  );

  async function generate() {
    setGenerating(true);
    setError(null);
    try {
      setResult(await createMarkSixWorldlines({
        horizon_draws: horizon,
        worldline_count: count,
        language,
        generation_mode: worldlineMode,
        astro_body: researchBody as "Mercury" | "Venus" | "Mars" | "Jupiter" | "Saturn",
        astro_condition: researchCondition,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setGenerating(false);
    }
  }

  async function runResearch() {
    setResearchLoading(true);
    setError(null);
    try {
      setResearch(await getMarkSixAstroResearch({
        body: researchBody, condition: researchCondition, numberRole,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setResearchLoading(false);
    }
  }

  return (
    <div className="page stack marksix-page">
      <header className="marksix-hero">
        <p className="pixel-kicker">MARK SIX // ASTRO RESEARCH + ENTERTAINMENT WORLDLINES</p>
        <h1>{t("marksix.title")}</h1>
        <p className="lead">{t("marksix.lead")}</p>
      </header>

      <section className="marksix-responsible" aria-label={t("marksix.safetyTitle")}>
        <strong>{t("marksix.safetyTitle")}</strong>
        <p>{t("marksix.safetyText")}</p>
      </section>

      {error ? <p className="notice">{error}</p> : null}

      <section className="marksix-status-grid">
        <div><span>{t("marksix.drawCount")}</span><strong>{loading ? "..." : status?.total_draws ?? 0}</strong></div>
        <div><span>{t("marksix.coverage")}</span><strong>{status?.history_start_year ?? "-"} → {status?.coverage_end ?? "-"}</strong></div>
        <div><span>{t("marksix.officialVerified")}</span><strong>{status?.official_verified_draws ?? 0}</strong></div>
      </section>
      {status?.coverage_note ? <p className="marksix-coverage-note">{t("marksix.coverageNote")}</p> : null}

      <section className="marksix-research">
        <header>
          <p className="pixel-kicker">ASTRO × DRAW HISTORY</p>
          <h2>{t("marksix.astroResearchTitle")}</h2>
          <p>{t("marksix.astroResearchLead")}</p>
        </header>
        <div className="marksix-research-controls">
          <label>{t("marksix.planet")}
            <select value={researchBody} onChange={(event) => setResearchBody(event.target.value)}>
              {["Mercury", "Venus", "Mars", "Jupiter", "Saturn"].map((body) => <option key={body}>{body}</option>)}
            </select>
          </label>
          <label>{t("marksix.motionCondition")}
            <select value={researchCondition} onChange={(event) => setResearchCondition(event.target.value as MarkSixMotionCondition)}>
              <option value="retrograde">{t("marksix.retrograde")}</option>
              <option value="direct">{t("marksix.direct")}</option>
              <option value="pre_station">{t("marksix.preStation")}</option>
              <option value="retrograde_entry">{t("marksix.retrogradeEntry")}</option>
              <option value="retrograde_core">{t("marksix.retrogradeCore")}</option>
              <option value="retrograde_exit">{t("marksix.retrogradeExit")}</option>
              <option value="post_station">{t("marksix.postStation")}</option>
            </select>
          </label>
          <label>{t("marksix.numberRole")}
            <select value={numberRole} onChange={(event) => setNumberRole(event.target.value as "main" | "extra")}>
              <option value="main">{t("marksix.mainNumber")}</option>
              <option value="extra">{t("marksix.extraNumber")}</option>
            </select>
          </label>
          <button disabled={researchLoading} onClick={runResearch} type="button">
            {researchLoading ? t("marksix.researching") : t("marksix.runResearch")}
          </button>
        </div>
        {research ? <div className="marksix-research-result">
          <p className="marksix-sample-line">
            {research.start_date} → {research.end_date} · {t("marksix.conditionSamples")}: {research.condition_draws} · {t("marksix.baselineSamples")}: {research.baseline_draws}
          </p>
          <div className="marksix-number-heatmap">
            {research.numbers.map((item) => {
              const intensity = Math.max(-1, Math.min(1, item.rate_difference * 12));
              return <button
                className="marksix-number-cell"
                key={item.number}
                style={{ "--difference": intensity } as React.CSSProperties}
                title={`${item.number} · lift ${item.lift?.toFixed(2) ?? "-"} · Δ ${(item.rate_difference * 100).toFixed(1)}pp · q ${item.q_value_fdr.toFixed(3)}`}
                type="button"
              >
                <strong>{item.number}</strong>
                <small>{item.lift?.toFixed(2) ?? "-"}×</small>
              </button>;
            })}
          </div>
          <div className="marksix-research-legend"><span>{t("marksix.lowerAssociation")}</span><i /><span>{t("marksix.higherAssociation")}</span></div>
          <p className="marksix-method-note">{t("marksix.astroResearchCaveat")}</p>
        </div> : null}
      </section>

      <section className="marksix-builder">
        <header>
          <p className="pixel-kicker">WORLDLINE GENERATOR</p>
          <h2>{t("marksix.generateTitle")}</h2>
        </header>
        <div className="marksix-controls">
          <label>{t("marksix.worldlineMode")}
            <select value={worldlineMode} onChange={(event) => setWorldlineMode(event.target.value as typeof worldlineMode)}>
              <option value="uniform_random_demo_v1">{t("marksix.uniformMode")}</option>
              <option value="astro_association_entertainment_v1">{t("marksix.astroMode")}</option>
            </select>
          </label>
          <label>{t("marksix.horizon")}
            <select value={horizon} onChange={(event) => setHorizon(Number(event.target.value) as 1 | 3 | 5 | 10)}>
              {[1, 3, 5, 10].map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label>{t("marksix.worldlineCount")}
            <select value={count} onChange={(event) => setCount(Number(event.target.value))}>
              {[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <button disabled={generating} onClick={generate} type="button">
            {generating ? t("marksix.generating") : t("marksix.generate")}
          </button>
        </div>
      </section>

      {result ? <section className="marksix-worldlines">
        {result.worldlines.map((worldline, index) => <article key={worldline.worldline_id}>
          <header><span>{t("marksix.worldline")} {index + 1}</span><code>{worldline.worldline_id}</code></header>
          <div className="marksix-simulated-draws">
            {worldline.draws.map((draw) => <div className="marksix-simulated-draw" key={draw.date}>
              <time>{draw.date}</time>
              <div>{draw.numbers.map((number) => <Ball key={number} number={number} />)}<span className="marksix-plus">+</span><Ball extra number={draw.extra_number} /></div>
            </div>)}
          </div>
          <p>{worldline.disclaimer}</p>
          {worldline.astro_context ? <p>{t("marksix.astroModeNote")}</p> : null}
        </article>)}
      </section> : null}

      <div className="marksix-history-grid">
        <section className="marksix-history">
          <header><p className="pixel-kicker">LOCAL DATABASE</p><h2>{t("marksix.latestDraws")}</h2></header>
          {draws.map((draw) => <div className="marksix-history-row" key={draw.draw_id}>
            <time>{draw.draw_date}</time>
            <div>{draw.numbers.map((number) => <Ball key={number} number={number} />)}<Ball extra number={draw.extra_number} /></div>
            <small>{draw.source_is_official ? t("marksix.official") : t("marksix.archive")}</small>
          </div>)}
        </section>
        <section className="marksix-frequency">
          <header><p className="pixel-kicker">DESCRIPTIVE ONLY</p><h2>{t("marksix.frequency")}</h2></header>
          <p>{t("marksix.frequencyNote")}</p>
          <div>{topFrequencies.map((item) => <span key={item.number}><Ball number={item.number} /><small>{item.main_count}</small></span>)}</div>
        </section>
      </div>
    </div>
  );
}
