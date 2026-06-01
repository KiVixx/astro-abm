"use client";

import { languageLabels, type Language } from "./dictionary";
import { useI18n } from "./useI18n";

const languages: Language[] = ["en", "zh-Hant"];

export function LanguageToggle() {
  const { language, setLanguage, t } = useI18n();

  return (
    <div className="language-toggle" aria-label={t("language.label")}>
      {languages.map((candidate) => (
        <button
          aria-pressed={language === candidate}
          className={language === candidate ? "is-active" : ""}
          key={candidate}
          onClick={() => setLanguage(candidate)}
          title={
            candidate === "en" ? t("language.english") : t("language.chinese")
          }
          type="button"
        >
          {languageLabels[candidate]}
        </button>
      ))}
    </div>
  );
}

