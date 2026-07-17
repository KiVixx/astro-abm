"use client";

import type { TranslationKey } from "@/i18n/dictionary";
import { useI18n } from "@/i18n/useI18n";
import {
  RETROGRADE_BODIES,
  type RetrogradeBody,
} from "@/lib/retrograde";

const bodyLabelKeys: Record<RetrogradeBody, TranslationKey> = {
  Mercury: "retrograde.body.mercury",
  Venus: "retrograde.body.venus",
  Mars: "retrograde.body.mars",
  Jupiter: "retrograde.body.jupiter",
  Saturn: "retrograde.body.saturn",
  Uranus: "retrograde.body.uranus",
  Neptune: "retrograde.body.neptune",
  Pluto: "retrograde.body.pluto",
};

interface RetrogradeBodySelectorProps {
  selectedBodies: RetrogradeBody[];
  onChange: (bodies: RetrogradeBody[]) => void;
}

export function retrogradeBodyLabel(
  body: RetrogradeBody,
  t: (key: TranslationKey) => string,
): string {
  return t(bodyLabelKeys[body]);
}

export function RetrogradeBodySelector({
  selectedBodies,
  onChange,
}: RetrogradeBodySelectorProps) {
  const { t } = useI18n();
  const toggleBody = (body: RetrogradeBody) => {
    const next = selectedBodies.includes(body)
      ? selectedBodies.filter((selected) => selected !== body)
      : RETROGRADE_BODIES.filter(
          (candidate) => selectedBodies.includes(candidate) || candidate === body,
        );
    onChange(next);
  };

  return (
    <details className="retrograde-body-menu">
      <summary>
        {t("retrograde.selectBodies")} ({selectedBodies.length}/{RETROGRADE_BODIES.length})
      </summary>
      <div className="retrograde-body-options">
        <p className="muted">{t("retrograde.selectorHelp")}</p>
        <div className="button-row retrograde-body-actions">
          <button
            className="button secondary"
            disabled={selectedBodies.length === RETROGRADE_BODIES.length}
            onClick={() => onChange([...RETROGRADE_BODIES])}
            type="button"
          >
            {t("retrograde.selectAll")}
          </button>
          <button
            className="button secondary"
            disabled={!selectedBodies.length}
            onClick={() => onChange([])}
            type="button"
          >
            {t("retrograde.clearAll")}
          </button>
        </div>
        <div className="retrograde-body-grid">
          {RETROGRADE_BODIES.map((body) => (
            <label className="retrograde-body-option" key={body}>
              <input
                checked={selectedBodies.includes(body)}
                onChange={() => toggleBody(body)}
                type="checkbox"
              />
              <span>{retrogradeBodyLabel(body, t)}</span>
              <small>{body}</small>
            </label>
          ))}
        </div>
        <p className="retrograde-context-disclaimer">
          {t("retrograde.contextDisclaimer")}
        </p>
      </div>
    </details>
  );
}
