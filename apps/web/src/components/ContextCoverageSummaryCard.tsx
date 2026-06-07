"use client";

import { useState } from "react";
import type { ScenarioCoverageSummary } from "@/lib/types";
import { formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

interface ContextCoverageSummaryCardProps {
  coverageSummary?: ScenarioCoverageSummary | null;
  compact?: boolean;
}

function CountList({
  counts,
  labelGroup,
}: {
  counts: Record<string, number>;
  labelGroup: string;
}) {
  const { t } = useI18n();
  const entries = Object.entries(counts).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  if (!entries.length) {
    return <p className="muted">{t("coverage.noEntries")}</p>;
  }
  return (
    <div className="coverage-count-list">
      {entries.map(([key, count]) => (
        <span className="tag" key={key}>
          {formatEnumLabel(t, labelGroup, key)}: {count}
        </span>
      ))}
    </div>
  );
}

export function ContextCoverageSummaryCard({
  coverageSummary,
  compact = false,
}: ContextCoverageSummaryCardProps) {
  const { t } = useI18n();
  const [isExpanded, setIsExpanded] = useState(false);

  if (!coverageSummary) {
    return (
      <section className="card coverage-summary-card">
        <h2>{t("coverage.title")}</h2>
        <p className="muted">{t("coverage.legacyMissing")}</p>
      </section>
    );
  }

  const assets = compact
    ? coverageSummary.asset_coverage.slice(0, 5)
    : coverageSummary.asset_coverage;
  const hiddenAssetCount = Math.max(
    coverageSummary.asset_coverage.length - assets.length,
    0,
  );

  return (
    <section className="card coverage-summary-card">
      <div className="coverage-summary-header">
        <div>
          <h2>{t("coverage.title")}</h2>
          <p className="muted">
            {t("coverage.dateRangeMode")}:{" "}
            {formatEnumLabel(
              t,
              "date_range_mode",
              coverageSummary.date_range_mode,
            )}
          </p>
        </div>
        <button
          aria-expanded={isExpanded}
          className="button secondary coverage-toggle-button"
          onClick={() => setIsExpanded((current) => !current)}
          type="button"
        >
          {isExpanded ? t("coverage.hideDetails") : t("coverage.showDetails")}
        </button>
      </div>
      <div className="coverage-compact-summary tag-row">
        <span className="tag">
          {t("coverage.totalDays")}: {coverageSummary.total_days}
        </span>
        <span className="tag">
          {t("coverage.localResearchDays")}: {coverageSummary.local_research_days}
        </span>
        <span className="tag">
          {t("coverage.futurePlaceholderDays")}:{" "}
          {coverageSummary.future_placeholder_days}
        </span>
        <span className="tag">
          {t("coverage.dateRangeMode")}:{" "}
          {formatEnumLabel(t, "date_range_mode", coverageSummary.date_range_mode)}
        </span>
      </div>
      {isExpanded ? (
        <>
          <div className="coverage-summary-grid">
            <div>
              <span className="muted">{t("coverage.totalDays")}</span>
              <strong>{coverageSummary.total_days}</strong>
            </div>
            <div>
              <span className="muted">{t("coverage.localResearchDays")}</span>
              <strong>{coverageSummary.local_research_days}</strong>
            </div>
            <div>
              <span className="muted">{t("coverage.placeholderDays")}</span>
              <strong>{coverageSummary.placeholder_days}</strong>
            </div>
            <div>
              <span className="muted">{t("coverage.futurePlaceholderDays")}</span>
              <strong>{coverageSummary.future_placeholder_days}</strong>
            </div>
            <div>
              <span className="muted">{t("coverage.mixedContextDays")}</span>
              <strong>{coverageSummary.mixed_context_days}</strong>
            </div>
          </div>
          <div className="coverage-component-grid">
            <div>
              <span className="muted">{t("coverage.astroAvailable")}</span>
              <strong>{coverageSummary.astro_daily_available_days}</strong>
            </div>
            <div>
              <span className="muted">{t("coverage.financialStressAvailable")}</span>
              <strong>{coverageSummary.financial_stress_available_days}</strong>
            </div>
            <div>
              <span className="muted">{t("coverage.marketAvailable")}</span>
              <strong>{coverageSummary.market_daily_available_days}</strong>
            </div>
            <div>
              <span className="muted">{t("coverage.macroAvailable")}</span>
              <strong>{coverageSummary.macro_daily_available_days}</strong>
            </div>
          </div>
          <div className="grid">
            <div>
              <h3>{t("coverage.dataSources")}</h3>
              <div className="tag-row">
                {coverageSummary.data_sources.length ? (
                  coverageSummary.data_sources.map((source) => (
                    <span className="tag" key={source}>
                      {formatEnumLabel(t, "data_source", source)}
                    </span>
                  ))
                ) : (
                  <span className="muted">{t("coverage.noEntries")}</span>
                )}
              </div>
            </div>
            <div>
              <h3>{t("coverage.dataQuality")}</h3>
              <CountList
                counts={coverageSummary.data_quality_counts}
                labelGroup="data_quality"
              />
            </div>
            <div>
              <h3>{t("coverage.sourceCounts")}</h3>
              <CountList counts={coverageSummary.source_counts} labelGroup="data_source" />
            </div>
          </div>
          <div>
            <h3>{t("coverage.assetCoverage")}</h3>
            <div className="coverage-asset-list">
              {assets.map((asset) => (
                <div className="coverage-asset-row" key={asset.asset}>
                  <strong>{asset.asset}</strong>
                  <span>
                    {formatEnumLabel(t, "coverage_status", asset.coverage_status)}
                  </span>
                  <span>
                    {asset.available_days} {t("coverage.availableDays")}
                  </span>
                  <span>
                    {asset.missing_days} {t("coverage.missingDays")}
                  </span>
                  <span>
                    {asset.future_placeholder_days} {t("coverage.futureDays")}
                  </span>
                </div>
              ))}
              {hiddenAssetCount ? (
                <p className="muted">
                  {t("coverage.moreAssetsPrefix")} {hiddenAssetCount}{" "}
                  {t("coverage.moreAssetsSuffix")}
                </p>
              ) : null}
            </div>
          </div>
          {!compact ? (
            <div>
              <h3>{t("coverage.coverageNotes")}</h3>
              <ul>
                {coverageSummary.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
