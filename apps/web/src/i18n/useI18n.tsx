"use client";

import { useContext } from "react";
import { I18nContext } from "./I18nProvider";
import type { TranslationKey } from "./dictionary";

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used inside I18nProvider");
  }
  return context;
}

export function I18nText({
  tKey,
  fallback,
}: {
  tKey: TranslationKey | string;
  fallback?: string;
}) {
  const { t } = useI18n();
  return <>{t(tKey, fallback)}</>;
}

export function interpolate(template: string, values: Record<string, string | number>) {
  return Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, String(value)),
    template,
  );
}
