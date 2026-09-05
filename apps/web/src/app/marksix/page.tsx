"use client";

import { useEffect, useMemo, useState } from "react";
import { useI18n } from "@/i18n/useI18n";
import {
  createMarkSixWorldlines,
  createMarkSixLlmWorldline,
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
  MarkSixMoonPhaseCondition,
  MarkSixLlmWorldlineResponse,
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
  const [contextType, setContextType] = useState<"planet_motion" | "moon_phase">("planet_motion");
  const [researchCondition, setResearchCondition] = useState<MarkSixMotionCondition>("retrograde");
  const [moonPhase, setMoonPhase] = useState<MarkSixMoonPhaseCondition>("full_moon_zone");
  const [numberRole, setNumberRole] = useState<"main" | "extra">("main");
  const [researchLoading, setResearchLoading] = useState(false);
  const [llmOpen, setLlmOpen] = useState(false);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmBaseUrl, setLlmBaseUrl] = useState("https://api.openai.com/v1");
  const [llmModel, setLlmModel] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmResult, setLlmResult] = useState<MarkSixLlmWorldlineResponse | null>(null);
  const [llmError, setLlmError] = useState<string | null>(null);
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
        astro_context_type: contextType,
        moon_phase_condition: moonPhase,
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
        contextType, body: researchBody,
        condition: contextType === "moon_phase" ? moonPhase : researchCondition, numberRole,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setResearchLoading(false);
    }
  }

  async function generateWithLlm() {
    setLlmLoading(true);
    setLlmError(null);
    try {
      const next = await createMarkSixLlmWorldline({
        base_url: llmBaseUrl, model: llmModel, api_key: llmApiKey || null,
        timeout_seconds: 120, language, astro_context_type: contextType,
        astro_body: researchBody as "Mercury" | "Venus" | "Mars" | "Jupiter" | "Saturn",
        astro_condition: researchCondition, moon_phase_condition: moonPhase,
      });
      setLlmResult(next);
      setLlmOpen(false);
      setLlmApiKey("");
    } catch (reason) {
      setLlmError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLlmLoading(false);
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
          <label>{t("marksix.contextType")}
            <select value={contextType} onChange={(event) => setContextType(event.target.value as typeof contextType)}>
              <option value="planet_motion">{t("marksix.planetMotion")}</option>
              <option value="moon_phase">{t("marksix.moonPhase")}</option>
            </select>
          </label>
          {contextType === "planet_motion" ? <><label>{t("marksix.planet")}
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
          </label></> : <label>{t("marksix.moonPhase")}
            <select value={moonPhase} onChange={(event) => setMoonPhase(event.target.value as MarkSixMoonPhaseCondition)}>
              <option value="new_moon_zone">{t("marksix.newMoon")}</option>
              <option value="first_quarter_zone">{t("marksix.firstQuarter")}</option>
              <option value="full_moon_zone">{t("marksix.fullMoon")}</option>
              <option value="last_quarter_zone">{t("marksix.lastQuarter")}</option>
              <option value="waxing_other">{t("marksix.waxingOther")}</option>
              <option value="waning_other">{t("marksix.waningOther")}</option>
            </select>
          </label>}
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
          <button className="secondary marksix-llm-open" onClick={() => setLlmOpen(true)} type="button">
            {t("marksix.llmButton")}
          </button>
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

      {llmOpen ? <div className="marksix-llm-backdrop" role="presentation" onMouseDown={() => setLlmOpen(false)}>
        <section aria-labelledby="marksix-llm-title" aria-modal="true" className="marksix-llm-dialog" onMouseDown={(event) => event.stopPropagation()} role="dialog">
          <header><div><p className="pixel-kicker">OPENAI-COMPATIBLE</p><h2 id="marksix-llm-title">{t("marksix.llmTitle")}</h2></div>
            <button className="secondary" onClick={() => setLlmOpen(false)} type="button">{t("marksix.close")}</button>
          </header>
          <p>{t("marksix.llmLead")}</p>
          <div className="form-grid">
            <label className="form-field"><span>{t("marksix.llmEndpoint")}</span><input onChange={(event) => setLlmBaseUrl(event.target.value)} placeholder="https://provider.example/v1" value={llmBaseUrl} /></label>
            <label className="form-field"><span>{t("marksix.llmModel")}</span><input onChange={(event) => setLlmModel(event.target.value)} placeholder="model-name" value={llmModel} /></label>
            <label className="form-field"><span>{t("marksix.llmApiKey")}</span><input autoComplete="off" onChange={(event) => setLlmApiKey(event.target.value)} type="password" value={llmApiKey} /></label>
          </div>
          <p className="marksix-method-note">{t("marksix.llmPrivacy")}</p>
          {llmError ? <p className="notice marksix-llm-error" role="alert">{llmError}</p> : null}
          <footer><button disabled={llmLoading || !llmBaseUrl.trim() || !llmModel.trim()} onClick={generateWithLlm} type="button">
              {llmLoading ? t("marksix.llmGenerating") : t("marksix.llmGenerate")}
          </button></footer>
        </section>
      </div> : null}

      {llmResult ? <section className="marksix-llm-result">
        <header><div><p className="pixel-kicker">LLM ASTRO GUESS</p><h2>{t("marksix.llmResult")}</h2></div><small>{llmResult.model}</small></header>
        <div className="marksix-simulated-draw">
          <time>{llmResult.worldline.draws[0].date}</time>
          <div>{llmResult.worldline.draws[0].numbers.map((number) => <Ball key={number} number={number} />)}<span className="marksix-plus">+</span><Ball extra number={llmResult.worldline.draws[0].extra_number} /></div>
        </div>
        <h3>{t("marksix.llmRationale")}</h3><p>{llmResult.rationale}</p>
        <p><strong>{t("marksix.llmConfidence")}:</strong> {llmResult.confidence}</p>
        {llmResult.caveats.length ? <ul>{llmResult.caveats.map((item) => <li key={item}>{item}</li>)}</ul> : null}
        <p className="marksix-method-note">{llmResult.worldline.disclaimer}</p>
      </section> : null}

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
