"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  AssetStressPoint,
  AssetStressSeries,
} from "@/lib/assetStressSentiment";
import { useI18n } from "@/i18n/useI18n";

interface AssetStressSentimentChartProps {
  series: AssetStressSeries[];
  selectedDate: string;
  selectedAssets: string[];
  onSelectDate: (date: string) => void;
}

interface ChartPoint extends AssetStressPoint {
  x: number;
  y: number;
  displayValue: string;
}

const DAY_COLUMN_WIDTH = 152;
const CHART_HEIGHT = 210;
const CHART_TOP = 22;
const CHART_BOTTOM = 158;
const X_OFFSET = DAY_COLUMN_WIDTH / 2;

function yForValue(value: number, series: AssetStressSeries): number {
  if (series.max === series.min) {
    return (CHART_TOP + CHART_BOTTOM) / 2;
  }
  const normalized = (value - series.min) / (series.max - series.min);
  return CHART_BOTTOM - normalized * (CHART_BOTTOM - CHART_TOP);
}

function pathFor(points: ChartPoint[]): string {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
}

function sourceLabelKey(source: AssetStressPoint["source"]): string {
  if (source === "llm_scenario_metric") {
    return "workbench.llmMetric";
  }
  if (source === "timeline_metric") {
    return "workbench.timelineMetric";
  }
  return "workbench.mockMetric";
}

function pointElementId(asset: string, date: string): string {
  return `asset-stress-${encodeURIComponent(asset)}-${date}`;
}

export function AssetStressSentimentChart({
  series,
  selectedAssets,
  selectedDate,
  onSelectDate,
}: AssetStressSentimentChartProps) {
  const { t } = useI18n();
  const [activePoint, setActivePoint] = useState<ChartPoint | null>(null);
  const effectiveWidth = Math.max(680, (series[0]?.points.length || 1) * DAY_COLUMN_WIDTH);
  const visibleSeries = useMemo(
    () => series.filter((assetSeries) => selectedAssets.includes(assetSeries.asset)),
    [selectedAssets, series],
  );

  const chartSeries = useMemo(
    () =>
      visibleSeries.map((assetSeries) => ({
        ...assetSeries,
        points: assetSeries.points.map((point, index) => ({
          ...point,
          x: X_OFFSET + index * DAY_COLUMN_WIDTH,
          y: yForValue(point.value, assetSeries),
          displayValue: point.value.toFixed(1),
        })),
      })),
    [visibleSeries],
  );

  useEffect(() => {
    setActivePoint((current) =>
      current?.date === selectedDate ? current : null,
    );
  }, [selectedDate]);

  if (!series.length) {
    return null;
  }

  const tooltipPoint =
    activePoint ||
    chartSeries
      .flatMap((assetSeries) => assetSeries.points)
      .find((point) => point.date === selectedDate) ||
    null;

  return (
    <div className="asset-stress-chart" style={{ width: effectiveWidth }}>
      <div className="asset-stress-chart-header">
        <div>
          <h3>{t("workbench.assetStressSentiment")}</h3>
          <p className="muted">{t("workbench.assetStressCurveHelp")}</p>
        </div>
        {tooltipPoint ? (
          <div className="asset-stress-tooltip" aria-live="polite">
            <span
              className="asset-stress-swatch"
              style={{ backgroundColor: tooltipPoint.color }}
            />
            <strong>{tooltipPoint.asset}</strong>
            <span>{tooltipPoint.date}</span>
            <span>
              {t("workbench.assetStressValue")}: {tooltipPoint.displayValue}
            </span>
            <span>
              {t(sourceLabelKey(tooltipPoint.source))}
            </span>
          </div>
        ) : null}
      </div>
      <svg
        className="asset-stress-svg"
        role="img"
        viewBox={`0 0 ${effectiveWidth} ${CHART_HEIGHT}`}
        aria-label={t("workbench.assetStressChartAria")}
      >
        {[
          { label: t("workbench.assetStressHigh"), y: CHART_TOP },
          { label: t("workbench.assetStressMid"), y: (CHART_TOP + CHART_BOTTOM) / 2 },
          { label: t("workbench.assetStressLow"), y: CHART_BOTTOM },
        ].map((tick) => (
          <g key={tick.label}>
            <line
              className="asset-stress-grid-line"
              x1="0"
              x2={effectiveWidth}
              y1={tick.y}
              y2={tick.y}
            />
            <text className="asset-stress-axis-label" x="8" y={tick.y - 5}>
              {tick.label}
            </text>
          </g>
        ))}
        {chartSeries[0]?.points.map((point, index) => {
          if (index % Math.ceil(chartSeries[0].points.length / 8 || 1) !== 0) {
            return null;
          }
          return (
            <text
              className="asset-stress-date-label"
              key={point.date}
              x={point.x}
              y={CHART_HEIGHT - 18}
            >
              {point.date.slice(5)}
            </text>
          );
        })}
        {chartSeries.length ? null : (
          <text className="asset-stress-empty" x="20" y="92">
            {t("workbench.assetStressNoAssetsSelected")}
          </text>
        )}
        {chartSeries.map((assetSeries) => (
          <path
            className="asset-stress-line"
            d={pathFor(assetSeries.points)}
            key={assetSeries.asset}
            stroke={assetSeries.color}
          />
        ))}
        {chartSeries.flatMap((assetSeries) =>
          assetSeries.points.map((point, pointIndex) => (
            <g
              aria-hidden={point.date === selectedDate ? undefined : true}
              aria-label={`${t("legend.asset")}: ${point.asset}, ${t(
                "workbench.assetStressValue",
              )}: ${point.displayValue}, ${point.date}`}
              className={`asset-stress-point ${
                point.date === selectedDate ? "is-selected" : ""
              }`}
              id={pointElementId(point.asset, point.date)}
              key={`${point.asset}-${point.date}`}
              onClick={() => {
                setActivePoint(point);
                onSelectDate(point.date);
              }}
              onFocus={() => setActivePoint(point)}
              onMouseEnter={() => setActivePoint(point)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setActivePoint(point);
                  onSelectDate(point.date);
                  return;
                }
                if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
                  event.preventDefault();
                  const offset = event.key === "ArrowLeft" ? -1 : 1;
                  const nextPoint = assetSeries.points[pointIndex + offset];
                  if (!nextPoint) {
                    return;
                  }
                  setActivePoint(nextPoint);
                  onSelectDate(nextPoint.date);
                  requestAnimationFrame(() => {
                    document
                      .getElementById(pointElementId(nextPoint.asset, nextPoint.date))
                      ?.focus();
                  });
                }
              }}
              role={point.date === selectedDate ? "button" : undefined}
              tabIndex={point.date === selectedDate ? 0 : -1}
            >
              <circle
                cx={point.x}
                cy={point.y}
                fill={point.color}
                r={point.date === selectedDate ? 5 : 3.5}
              />
              <title>
                {`${t("legend.asset")}: ${point.asset}, ${t(
                  "workbench.assetStressValue",
                )}: ${point.displayValue}, ${point.date}`}
              </title>
            </g>
          )),
        )}
        {chartSeries[0]?.points.map((point) =>
          point.date === selectedDate ? (
            <line
              className="asset-stress-selected-date"
              key={`selected-${point.date}`}
              x1={point.x}
              x2={point.x}
              y1={CHART_TOP}
              y2={CHART_BOTTOM}
            />
          ) : null,
        )}
      </svg>
    </div>
  );
}
