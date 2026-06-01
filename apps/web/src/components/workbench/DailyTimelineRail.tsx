"use client";

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
  onSelectDate: (date: string) => void;
}

function monthLabel(dateValue: string): string {
  return dateValue.slice(0, 7);
}

export function DailyTimelineRail({
  timeline,
  selectedDate,
  onSelectDate,
}: DailyTimelineRailProps) {
  const { t } = useI18n();
  const selectedIndex = Math.max(
    0,
    timeline.findIndex((snapshot) => snapshot.date === selectedDate),
  );
  const selectedSnapshot = timeline[selectedIndex] || timeline[0];
  const previousSnapshot = timeline[selectedIndex - 1];
  const nextSnapshot = timeline[selectedIndex + 1];

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
        <div className="button-row">
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
    </section>
  );
}
