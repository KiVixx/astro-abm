"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import { AssetStressSentimentChart } from "./AssetStressSentimentChart";
import type { AssetStressSeries } from "@/lib/assetStressSentiment";
import type { DailyScenarioSnapshot } from "@/lib/types";
import {
  getDailyDataCoverage,
  getDailyResearchSignals,
} from "@/lib/workbenchGraph";
import { formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

interface DailyTimelineRailProps {
  timeline: DailyScenarioSnapshot[];
  selectedDate: string;
  assetStressSeries: AssetStressSeries[];
  onSelectDate: (date: string) => void;
}

function monthLabel(dateValue: string): string {
  return dateValue.slice(0, 7);
}

function AssetStressAssetSelector({
  series,
  selectedAssets,
  onSelectAllAssets,
  onToggleAsset,
}: {
  series: AssetStressSeries[];
  selectedAssets: string[];
  onSelectAllAssets: () => void;
  onToggleAsset: (asset: string) => void;
}) {
  const { t } = useI18n();
  if (!series.length) {
    return null;
  }

  return (
    <div className="asset-stress-rail-controls">
      <details className="asset-stress-asset-menu">
        <summary>{t("workbench.assetStressSelectAssets")}</summary>
        <div className="asset-stress-asset-options">
          <button
            className="button secondary"
            onClick={onSelectAllAssets}
            type="button"
          >
            {t("workbench.assetStressShowAll")}
          </button>
          {series.map((assetSeries) => (
            <label className="asset-stress-asset-option" key={assetSeries.asset}>
              <input
                checked={selectedAssets.includes(assetSeries.asset)}
                onChange={() => onToggleAsset(assetSeries.asset)}
                type="checkbox"
              />
              <span
                className="asset-stress-swatch"
                style={{ backgroundColor: assetSeries.color }}
              />
              <strong>{assetSeries.asset}</strong>
            </label>
          ))}
        </div>
      </details>
      <div className="asset-stress-inline-legend" aria-label={t("legend.assetStressSentiment")}>
        {series.map((assetSeries) => (
          <span
            className={`asset-stress-inline-legend-item ${
              selectedAssets.includes(assetSeries.asset) ? "" : "is-muted"
            }`}
            key={assetSeries.asset}
          >
            <span
              className="legend-line"
              style={{ backgroundColor: assetSeries.color }}
            />
            {assetSeries.asset}
          </span>
        ))}
      </div>
    </div>
  );
}

export function DailyTimelineRail({
  timeline,
  selectedDate,
  assetStressSeries,
  onSelectDate,
}: DailyTimelineRailProps) {
  const { t } = useI18n();
  const scrollRef = useRef<HTMLDivElement>(null);
  const selectedChipRef = useRef<HTMLButtonElement | null>(null);
  const dragState = useRef({
    isDragging: false,
    startX: 0,
    startScrollLeft: 0,
  });
  const [isDragging, setIsDragging] = useState(false);
  const [selectedAssets, setSelectedAssets] = useState<string[]>(() =>
    assetStressSeries.map((assetSeries) => assetSeries.asset),
  );
  const selectedIndex = Math.max(
    0,
    timeline.findIndex((snapshot) => snapshot.date === selectedDate),
  );
  const selectedSnapshot = timeline[selectedIndex] || timeline[0];
  const previousSnapshot = timeline[selectedIndex - 1];
  const nextSnapshot = timeline[selectedIndex + 1];

  useEffect(() => {
    setSelectedAssets((currentAssets) => {
      const availableAssets = assetStressSeries.map((assetSeries) => assetSeries.asset);
      const keptAssets = currentAssets.filter((asset) => availableAssets.includes(asset));
      return keptAssets.length ? keptAssets : availableAssets;
    });
  }, [assetStressSeries]);

  useEffect(() => {
    selectedChipRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "center",
    });
  }, [selectedDate]);

  const scrollByDays = (days: number) => {
    scrollRef.current?.scrollBy({
      behavior: "smooth",
      left: days * 152,
    });
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    const target = event.target;
    if (target instanceof HTMLElement && target.closest("button")) {
      return;
    }
    dragState.current = {
      isDragging: true,
      startX: event.clientX,
      startScrollLeft: scrollRef.current?.scrollLeft || 0,
    };
    setIsDragging(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragState.current.isDragging || !scrollRef.current) {
      return;
    }
    const deltaX = event.clientX - dragState.current.startX;
    scrollRef.current.scrollLeft = dragState.current.startScrollLeft - deltaX;
  };

  const stopDragging = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragState.current.isDragging) {
      return;
    }
    dragState.current.isDragging = false;
    setIsDragging(false);
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Pointer capture may already be released by the browser.
    }
  };

  const toggleAsset = (asset: string) => {
    setSelectedAssets((currentAssets) => {
      if (currentAssets.includes(asset)) {
        return currentAssets.filter((currentAsset) => currentAsset !== asset);
      }
      return [...currentAssets, asset];
    });
  };

  return (
    <section className="workbench-card workbench-rail">
      <div className="workbench-rail-header">
        <div>
          <h2>{t("workbench.timelineTitle")}</h2>
          <p className="muted">
            {selectedSnapshot
              ? `${monthLabel(selectedSnapshot.date)} - ${t("common.day")} ${
                  selectedIndex + 1
                } ${t("common.of")} ${timeline.length}`
              : t("workbench.noSnapshots")}
          </p>
        </div>
        <AssetStressAssetSelector
          onSelectAllAssets={() =>
            setSelectedAssets(assetStressSeries.map((assetSeries) => assetSeries.asset))
          }
          onToggleAsset={toggleAsset}
          selectedAssets={selectedAssets}
          series={assetStressSeries}
        />
        <div className="button-row">
          <button
            className="button secondary"
            onClick={() => scrollByDays(-7)}
            type="button"
          >
            {t("workbench.scrollLeft")}
          </button>
          <button
            className="button secondary"
            onClick={() => scrollByDays(7)}
            type="button"
          >
            {t("workbench.scrollRight")}
          </button>
          <button
            className="button secondary"
            disabled={!previousSnapshot}
            onClick={() => previousSnapshot && onSelectDate(previousSnapshot.date)}
            type="button"
          >
            {t("workbench.previous")}
          </button>
          <button
            className="button secondary"
            disabled={!nextSnapshot}
            onClick={() => nextSnapshot && onSelectDate(nextSnapshot.date)}
            type="button"
          >
            {t("workbench.next")}
          </button>
        </div>
      </div>
      <div
        className={`workbench-rail-scroll ${isDragging ? "is-dragging" : ""}`}
        onPointerCancel={stopDragging}
        onPointerDown={onPointerDown}
        onPointerLeave={stopDragging}
        onPointerMove={onPointerMove}
        onPointerUp={stopDragging}
        ref={scrollRef}
      >
        <div className="workbench-rail-track">
          <AssetStressSentimentChart
            onSelectDate={onSelectDate}
            selectedDate={selectedDate}
            selectedAssets={selectedAssets}
            series={assetStressSeries}
          />
          <div className="workbench-day-strip">
            {timeline.map((snapshot) => {
              const coverage = getDailyDataCoverage(snapshot);
              const signals = getDailyResearchSignals(snapshot);
              const isSelected = snapshot.date === selectedDate;
              return (
                <button
                  className={`workbench-day-chip ${isSelected ? "is-selected" : ""}`}
                  key={snapshot.date}
                  onClick={() => onSelectDate(snapshot.date)}
                  ref={isSelected ? selectedChipRef : null}
                  type="button"
                >
                  <span className="workbench-day-month">{monthLabel(snapshot.date)}</span>
                  <strong>{snapshot.date.slice(5)}</strong>
                  <span>{formatEnumLabel(t, "stress_regime", signals.stress_regime)}</span>
                  <span>
                    {signals.data_quality
                      ? formatEnumLabel(t, "data_quality", signals.data_quality)
                      : formatEnumLabel(t, "data_source", coverage.source)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
