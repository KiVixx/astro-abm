"use client";

import { useEffect, useState } from "react";
import type { DailyRetrogradeBodyContext, DailyScenarioSnapshot } from "@/lib/types";
import type { RetrogradeBody } from "@/lib/retrograde";
import { formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";
import { retrogradeBodyLabel } from "./RetrogradeBodySelector";

const DAY_COLUMN_WIDTH = 152;
const X_OFFSET = DAY_COLUMN_WIDTH / 2;
const LANE_HEIGHT = 46;
const TOP_OFFSET = 26;
const BOTTOM_OFFSET = 16;

interface RetrogradeTimelineLanesProps {
  timeline: DailyScenarioSnapshot[];
  selectedBodies: RetrogradeBody[];
  selectedDate: string;
  width: number;
  onSelectDate: (date: string) => void;
}

function bodyContext(
  snapshot: DailyScenarioSnapshot,
  body: RetrogradeBody,
): DailyRetrogradeBodyContext | null {
  return snapshot.retrograde_context?.bodies.find((item) => item.body === body) || null;
}

function phaseClass(phase: string): string {
  if (["retrograde_entry", "retrograde_core", "retrograde_exit", "retrograde"].includes(phase)) {
    return `is-${phase.replaceAll("_", "-")}`;
  }
  if (phase === "pre_station" || phase === "post_station") {
    return `is-${phase.replaceAll("_", "-")}`;
  }
  return "is-direct";
}

function stationLabel(context: DailyRetrogradeBodyContext | null, dateValue: string): string | null {
  if (!context?.nearest_station_ts || context.days_to_station_nearest !== 0) {
    return null;
  }
  if (!context.nearest_station_ts.startsWith(dateValue)) {
    return null;
  }
  if (context.nearest_station_type === "direct_to_retrograde") {
    return "D→R";
  }
  if (context.nearest_station_type === "retrograde_to_direct") {
    return "R→D";
  }
  return null;
}

export function RetrogradeTimelineLanes({
  timeline,
  selectedBodies,
  selectedDate,
  width,
  onSelectDate,
}: RetrogradeTimelineLanesProps) {
  const { t } = useI18n();
  const [activeCell, setActiveCell] = useState<{
    body: RetrogradeBody;
    date: string;
    context: DailyRetrogradeBodyContext | null;
  } | null>(null);
  useEffect(() => {
    setActiveCell(null);
  }, [selectedDate]);
  if (!selectedBodies.length) {
    return (
      <div className="retrograde-lanes-empty">
        {t("retrograde.noBodiesSelected")}
      </div>
    );
  }
  const hasData = timeline.some((snapshot) => snapshot.retrograde_context?.bodies.length);
  if (!hasData) {
    return (
      <div className="retrograde-lanes-empty">
        {t("retrograde.noData")}
      </div>
    );
  }

  const height = TOP_OFFSET + selectedBodies.length * LANE_HEIGHT + BOTTOM_OFFSET;
  const selectedIndex = timeline.findIndex((snapshot) => snapshot.date === selectedDate);
  const selectedSnapshot = selectedIndex >= 0 ? timeline[selectedIndex] : null;
  const displayCell = activeCell || (
    selectedSnapshot && selectedBodies[0]
      ? {
          body: selectedBodies[0],
          date: selectedDate,
          context: bodyContext(selectedSnapshot, selectedBodies[0]),
        }
      : null
  );
  return (
    <section className="retrograde-lanes" aria-label={t("retrograde.chartAria")}>
      <div className="retrograde-lanes-header">
        <div>
          <h3>{t("retrograde.chartTitle")}</h3>
          <p className="muted">{t("retrograde.chartHelp")}</p>
        </div>
        <div className="retrograde-phase-legend" aria-label={t("retrograde.phaseLegend")}>
          <span><i className="is-pre-station" />{t("retrograde.phase.pre")}</span>
          <span><i className="is-retrograde-entry" />{t("retrograde.phase.entry")}</span>
          <span><i className="is-retrograde-core" />{t("retrograde.phase.core")}</span>
          <span><i className="is-retrograde-exit" />{t("retrograde.phase.exit")}</span>
          <span><i className="is-post-station" />{t("retrograde.phase.post")}</span>
          <span><b>D→R</b>{t("retrograde.station.in")}</span>
          <span><b>R→D</b>{t("retrograde.station.out")}</span>
        </div>
      </div>
      {displayCell ? (
        <div className="retrograde-lanes-tooltip" aria-live="polite">
          <strong>{retrogradeBodyLabel(displayCell.body, t)}</strong>
          <span>{displayCell.date}</span>
          <span>
            {formatEnumLabel(t, "retrograde_phase", displayCell.context?.phase || "unknown")}
          </span>
          <span>
            {t("retrograde.longitudeSpeed")}: {displayCell.context?.lon_speed_deg_day === null
              || displayCell.context?.lon_speed_deg_day === undefined
              ? t("value.common.unknown")
              : `${displayCell.context.lon_speed_deg_day.toFixed(6)}°/${t("common.day")}`}
          </span>
          {displayCell.context?.nearest_station_type ? (
            <span>
              {t("retrograde.nearestStation")}: {formatEnumLabel(
                t,
                "station_type",
                displayCell.context.nearest_station_type,
              )} · {displayCell.context.days_to_station_nearest ?? "?"} {t("retrograde.days")}
            </span>
          ) : null}
        </div>
      ) : null}
      <svg
        className="retrograde-lanes-svg"
        role="img"
        viewBox={`0 0 ${width} ${height}`}
      >
        {selectedBodies.map((body, bodyIndex) => {
          const y = TOP_OFFSET + bodyIndex * LANE_HEIGHT;
          return (
            <g key={body}>
              <line className="retrograde-lane-baseline" x1="0" x2={width} y1={y + 26} y2={y + 26} />
              <text className="retrograde-lane-label" x="8" y={y + 10}>
                {retrogradeBodyLabel(body, t)} · {body}
              </text>
              {timeline.map((snapshot, dayIndex) => {
                const context = bodyContext(snapshot, body);
                const phase = context?.phase || "unknown";
                const station = stationLabel(context, snapshot.date);
                const x = dayIndex * DAY_COLUMN_WIDTH;
                const isSelected = snapshot.date === selectedDate;
                const description = context
                  ? `${retrogradeBodyLabel(body, t)} · ${snapshot.date} · ${phase} · ${
                      context.lon_speed_deg_day ?? t("common.unknown")
                    }°/day`
                  : `${retrogradeBodyLabel(body, t)} · ${snapshot.date} · ${t("retrograde.noData")}`;
                return (
                  <g
                    aria-label={description}
                    className={`retrograde-day-cell ${isSelected ? "is-selected" : ""}`}
                    key={`${body}-${snapshot.date}`}
                    onClick={() => onSelectDate(snapshot.date)}
                    onFocus={() => setActiveCell({ body, date: snapshot.date, context })}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onSelectDate(snapshot.date);
                      }
                    }}
                    onMouseEnter={() => setActiveCell({ body, date: snapshot.date, context })}
                    role={isSelected ? "button" : undefined}
                    tabIndex={isSelected ? 0 : -1}
                  >
                    <rect
                      className={`retrograde-phase-cell ${phaseClass(phase)}`}
                      height="20"
                      rx="2"
                      width={DAY_COLUMN_WIDTH - 3}
                      x={x + 1.5}
                      y={y + 15}
                    />
                    {context?.is_retrograde ? (
                      <line
                        className="retrograde-motion-line"
                        x1={x + 8}
                        x2={x + DAY_COLUMN_WIDTH - 8}
                        y1={y + 31}
                        y2={y + 31}
                      />
                    ) : null}
                    {station ? (
                      <g>
                        <line
                          className="retrograde-station-marker"
                          x1={x + X_OFFSET}
                          x2={x + X_OFFSET}
                          y1={y + 12}
                          y2={y + 39}
                        />
                        <text
                          className="retrograde-station-label"
                          x={x + X_OFFSET}
                          y={y + 45}
                        >
                          {station}
                        </text>
                      </g>
                    ) : null}
                    <title>{description}</title>
                  </g>
                );
              })}
            </g>
          );
        })}
        {selectedIndex >= 0 ? (
          <line
            className="retrograde-selected-date"
            x1={X_OFFSET + selectedIndex * DAY_COLUMN_WIDTH}
            x2={X_OFFSET + selectedIndex * DAY_COLUMN_WIDTH}
            y1="0"
            y2={height}
          />
        ) : null}
      </svg>
    </section>
  );
}
