import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { locales, Locale, Messages } from "../i18n";

const LOCALE_KEY = "doc-agent-locale";

function getStoredLocale(): Locale {
  const stored = localStorage.getItem(LOCALE_KEY);
  if (stored === "zh" || stored === "en") return stored;
  // 浏览器语言自动检测
  const browserLang = navigator.language.startsWith("zh") ? "zh" : "en";
  return browserLang;
}

// Deeply get value by dot-separated path
function getByPath(obj: unknown, path: string): string {
  const keys = path.split(".");
  let current: unknown = obj;
  for (const key of keys) {
    if (current == null || typeof current !== "object") return path;
    current = (current as Record<string, unknown>)[key];
  }
  return typeof current === "string" ? current : path;
}

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(getStoredLocale);

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem(LOCALE_KEY, newLocale);
  }, []);

  const t = useCallback(
    (key: string): string => {
      const messages: Messages = locales[locale];
      return getByPath(messages, key);
    },
    [locale]
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return context;
}
