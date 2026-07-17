"use client";

import { useI18n } from "@/i18n/useI18n";

export interface LlmConnectionFeedback {
  message: string;
  reachable: boolean;
  status: string;
  testing?: boolean;
}

export function LlmConnectionTestResult({
  feedback,
}: {
  feedback: LlmConnectionFeedback | null;
}) {
  const { t } = useI18n();
  if (!feedback) return null;
  const tone = feedback.testing || feedback.reachable
    ? "notice"
    : feedback.status === "disabled"
      ? "notice warning"
      : "notice warning";
  const title = feedback.testing
    ? t("llm.connectionTesting")
    : feedback.reachable
      ? t("llm.connectionSucceeded")
      : feedback.status === "disabled"
        ? t("llm.connectionDisabled")
        : t("llm.connectionFailed");
  return (
    <section
      aria-live={feedback.reachable || feedback.testing ? "polite" : "assertive"}
      className={tone}
      role={feedback.reachable || feedback.testing ? "status" : "alert"}
    >
      <strong>{title}</strong>
      {!feedback.testing && feedback.message ? (
        <>
          <p className="muted">{t("llm.connectionRetestNote")}</p>
          <details>
            <summary>{t("llm.connectionTechnicalDetails")}</summary>
            <p className="muted">{feedback.status}: {feedback.message}</p>
          </details>
        </>
      ) : null}
    </section>
  );
}
