import { useCallback, useEffect, useState } from "react";

export type Theme = "dark" | "light";

// index.html reads the same key before first paint.
const STORAGE_KEY = "politerate-theme";
const THEME_COLORS: Record<Theme, string> = { dark: "#1b1b1e", light: "#f1ebe1" };
const listeners = new Set<(theme: Theme) => void>();

function currentTheme(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLORS[theme]);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Private mode or blocked storage: the choice lasts for this page only.
  }
  listeners.forEach(listener => listener(theme));
}

/** The site theme (dark by default) and a toggle that remembers the choice. */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(currentTheme);
  useEffect(() => {
    listeners.add(setTheme);
    return () => {
      listeners.delete(setTheme);
    };
  }, []);
  const toggle = useCallback(() => applyTheme(currentTheme() === "dark" ? "light" : "dark"), []);
  return [theme, toggle];
}
