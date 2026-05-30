"use client";

// Theme provider — controls the data-theme attribute on <html>.
//
// Three states:
//   "light" — explicit user opt-in to light mode
//   "dark"  — explicit user opt-in to dark mode (the app default)
//   "system" — follow prefers-color-scheme
//
// Persistence: stored in localStorage under "ocrbills:theme".
// No-flash: the actual data-theme attribute is set by a tiny inline script
// in layout.tsx BEFORE React hydrates, so users don't see a dark→light flash.

import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type ThemeChoice = "light" | "dark" | "system";

type ThemeContextValue = {
  /** The user's stored choice (or "system" if never set). */
  choice: ThemeChoice;
  /** The actual theme being applied right now ("light" | "dark"). */
  resolved: "light" | "dark";
  setChoice: (c: ThemeChoice) => void;
};

const STORAGE_KEY = "ocrbills:theme";

const ThemeContext = createContext<ThemeContextValue | null>(null);

function resolveChoice(choice: ThemeChoice): "light" | "dark" {
  if (choice === "system") {
    if (typeof window === "undefined") return "dark";
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  return choice;
}

function applyTheme(resolved: "light" | "dark") {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", resolved);
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // SSR + first paint: assume dark to match what the inline noflash script writes.
  // After mount, sync to localStorage + system preference.
  const [choice, setChoiceState] = useState<ThemeChoice>("dark");
  const [resolved, setResolved] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const stored = (typeof window !== "undefined"
      ? (window.localStorage.getItem(STORAGE_KEY) as ThemeChoice | null)
      : null) || "system";
    const r = resolveChoice(stored);
    setChoiceState(stored);
    setResolved(r);
    applyTheme(r);

    // If user picked "system", react live to OS changes.
    if (stored === "system" && typeof window !== "undefined") {
      const mq = window.matchMedia("(prefers-color-scheme: light)");
      const onChange = () => {
        const r2 = mq.matches ? "light" : "dark";
        setResolved(r2);
        applyTheme(r2);
      };
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    }
  }, []);

  const setChoice = useCallback((c: ThemeChoice) => {
    setChoiceState(c);
    const r = resolveChoice(c);
    setResolved(r);
    applyTheme(r);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, c);
    }
  }, []);

  return (
    <ThemeContext.Provider value={{ choice, resolved, setChoice }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (ctx === null) {
    // Safe default — used in tests or pre-mount situations.
    return { choice: "dark", resolved: "dark", setChoice: () => {} };
  }
  return ctx;
}

/**
 * Inline script string injected into <head> via dangerouslySetInnerHTML.
 * Runs BEFORE React hydrates, so the data-theme attribute is set on <html>
 * synchronously — eliminates the dark-to-light flash on light-mode users.
 * Keep this string short and dependency-free.
 */
export const THEME_NOFLASH_SCRIPT = `
(function(){
  try {
    var c = localStorage.getItem("${STORAGE_KEY}") || "system";
    var r = c === "system"
      ? (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark")
      : c;
    document.documentElement.setAttribute("data-theme", r);
  } catch (e) {
    document.documentElement.setAttribute("data-theme", "dark");
  }
})();
`.trim();
