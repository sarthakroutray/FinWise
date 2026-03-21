import React, { createContext, useContext, useState, useEffect } from "react";

type Theme = "dark" | "light";

export type AccentName = "indigo" | "blue" | "emerald" | "rose" | "amber" | "cyan" | "mono";

export interface AccentColors {
  400: string;
  500: string;
  600: string;
  rgb: string;        // for rgba() usage
  name: string;
  label: string;
}

export const accentPresets: Record<AccentName, AccentColors> = {
  indigo: { 400: "#818cf8", 500: "#6366f1", 600: "#4f46e5", rgb: "99,102,241", name: "indigo", label: "Indigo" },
  blue:   { 400: "#60a5fa", 500: "#3b82f6", 600: "#2563eb", rgb: "59,130,246", name: "blue", label: "Blue" },
  cyan:   { 400: "#22d3ee", 500: "#06b6d4", 600: "#0891b2", rgb: "6,182,212", name: "cyan", label: "Cyan" },
  emerald:{ 400: "#34d399", 500: "#10b981", 600: "#059669", rgb: "16,185,129", name: "emerald", label: "Emerald" },
  rose:   { 400: "#fb7185", 500: "#f43f5e", 600: "#e11d48", rgb: "244,63,94", name: "rose", label: "Rose" },
  amber:  { 400: "#fbbf24", 500: "#f59e0b", 600: "#d97706", rgb: "245,158,11", name: "amber", label: "Amber" },
  mono:   { 400: "#a1a1aa", 500: "#71717a", 600: "#52525b", rgb: "113,113,122", name: "mono", label: "Monochrome" },
};

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  accent: AccentName;
  accentColors: AccentColors;
  setAccent: (name: AccentName) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: "dark",
  toggleTheme: () => {},
  accent: "indigo",
  accentColors: accentPresets.indigo,
  setAccent: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("finwise-theme") as Theme) || "dark";
    }
    return "dark";
  });

  const [accent, setAccentState] = useState<AccentName>(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("finwise-accent") as AccentName) || "indigo";
    }
    return "indigo";
  });

  const accentColors = accentPresets[accent] || accentPresets.indigo;

  useEffect(() => {
    localStorage.setItem("finwise-theme", theme);
    document.documentElement.classList.toggle("light-mode", theme === "light");
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("finwise-accent", accent);
    const c = accentPresets[accent];
    const root = document.documentElement;
    root.style.setProperty("--accent-400", c[400]);
    root.style.setProperty("--accent-500", c[500]);
    root.style.setProperty("--accent-600", c[600]);
    root.style.setProperty("--accent-rgb", c.rgb);
  }, [accent]);

  const toggleTheme = () => setTheme(prev => prev === "dark" ? "light" : "dark");
  const setAccent = (name: AccentName) => setAccentState(name);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, accent, accentColors, setAccent }}>
      {children}
    </ThemeContext.Provider>
  );
}
