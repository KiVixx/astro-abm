"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  dictionaries,
  LANGUAGE_STORAGE_KEY,
  type Language,
  type TranslationKey,
} from "./dictionary";

interface I18nContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: TranslationKey | string, fallback?: string) => string;
}

export const I18nContext = createContext<I18nContextValue | null>(null);

function isLanguage(value: string | null): value is Language {
  return value === "en" || value === "zh-Hant";
}

function detectBrowserLanguage(): Language {
  if (typeof window === "undefined") {
    return "en";
  }
  const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
  if (isLanguage(stored)) {
    return stored;
  }
  return window.navigator.language.toLowerCase().startsWith("zh") ? "zh-Hant" : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>("en");
  const [hasLoadedPreference, setHasLoadedPreference] = useState(false);

  useEffect(() => {
    setLanguageState(detectBrowserLanguage());
    setHasLoadedPreference(true);
  }, []);

  useEffect(() => {
    document.documentElement.lang = language;
    if (hasLoadedPreference) {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    }
  }, [hasLoadedPreference, language]);

  const setLanguage = useCallback((nextLanguage: Language) => {
    setLanguageState(nextLanguage);
  }, []);

  const t = useCallback(
    (key: TranslationKey | string, fallback?: string) => {
      return (
        dictionaries[language][key] ||
        dictionaries.en[key] ||
        fallback ||
        key
      );
    },
    [language],
  );

  const value = useMemo(
    () => ({
      language,
      setLanguage,
      t,
    }),
    [language, setLanguage, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
