"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/useI18n";
import { getPublicMarkSixLlmWorldlines } from "@/lib/api";
import type { MarkSixPublicLlmWorldlineSummary } from "@/lib/types";

function Ball({ number, extra = false }: { number: number; extra?: boolean }) {
  return <span className={extra ? "marksix-ball is-extra" : "marksix-ball"}>{number}</span>;
}

export function MarkSixPublicLibrary() {
  const { t } = useI18n();
  const [items, setItems] = useState<MarkSixPublicLlmWorldlineSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPublicMarkSixLlmWorldlines(50, 0)
      .then((rows) => {
        setItems(rows);
        setHasMore(rows.length === 50);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="marksix-overview-state">{t("marksix.publicLibraryLoading")}</p>;
  if (error && !items.length) return <p className="notice">{error}</p>;
  if (!items.length) return <p className="marksix-overview-state">{t("marksix.publicLibraryEmpty")}</p>;

  async function loadMore() {
    setLoadingMore(true);
    setError(null);
    try {
      const rows = await getPublicMarkSixLlmWorldlines(50, items.length);
      setItems((current) => [...current, ...rows]);
      setHasMore(rows.length === 50);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoadingMore(false);
    }
  }

  return <div className="stack">
    <section className="marksix-public-grid">
      {items.map((item) => <article className="marksix-public-card" key={item.library_id}>
      <header>
        <div>
          <p className="pixel-kicker">{item.language === "zh-Hant" ? "繁中" : "EN"} · {item.model}</p>
          <h2>{t("marksix.publicLibraryTargetDraw")} {item.draw_date}</h2>
        </div>
        <time>{item.created_at.slice(0, 16).replace("T", " ")} UTC</time>
      </header>
      <div className="marksix-public-balls">
        {item.numbers.map((number) => <Ball key={number} number={number} />)}
        <span className="marksix-plus">+</span><Ball extra number={item.extra_number} />
      </div>
      <dl className="marksix-public-meta">
        <div><dt>{t("marksix.publicLibraryContext")}</dt><dd>{item.astro_context_type}</dd></div>
        <div><dt>{t("marksix.publicLibraryCondition")}</dt><dd>{item.historical_condition}</dd></div>
        <div><dt>{t("marksix.llmConfidence")}</dt><dd>{item.confidence}</dd></div>
      </dl>
      <Link className="button secondary" href={`/marksix/worldlines/${item.library_id}`}>
        {t("marksix.publicLibraryRead")}
      </Link>
      </article>)}
    </section>
    {error ? <p className="notice">{error}</p> : null}
    {hasMore ? <button className="secondary marksix-public-more" disabled={loadingMore} onClick={() => void loadMore()} type="button">
      {loadingMore ? t("marksix.publicLibraryLoading") : t("marksix.publicLibraryLoadMore")}
    </button> : null}
  </div>;
}
