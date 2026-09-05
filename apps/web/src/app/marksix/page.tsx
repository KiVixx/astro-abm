"use client";

import { useEffect, useMemo, useState } from "react";
import { useI18n } from "@/i18n/useI18n";
import {
  createMarkSixWorldlines,
  getMarkSixDraws,
  getMarkSixFrequencies,
  getMarkSixStatus,
} from "@/lib/api";
import type {
  MarkSixDrawRecord,
  MarkSixFrequency,
  MarkSixStatus,
  MarkSixWorldlineResponse,
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
  const [horizon, setHorizon] = useState<1 | 3 | 5 | 10>(3);
  const [count, setCount] = useState(1);
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
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="page stack marksix-page">
      <header className="marksix-hero">
        <p className="pixel-kicker">MARK SIX // UNIFORM RANDOM WORLDLINES</p>
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

      <section className="marksix-builder">
        <header>
          <p className="pixel-kicker">WORLDLINE GENERATOR</p>
          <h2>{t("marksix.generateTitle")}</h2>
        </header>
        <div className="marksix-controls">
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
