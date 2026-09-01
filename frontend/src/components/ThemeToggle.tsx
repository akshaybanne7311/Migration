import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function getInitialTheme(): Theme {
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "light" ? "light" : "dark";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("f5ci-theme", theme);
    } catch {
      // best-effort; theme just won't persist across reloads
    }
  }, [theme]);

  const isLight = theme === "light";

  return (
    <button
      type="button"
      onClick={() => setTheme(isLight ? "dark" : "light")}
      aria-label={isLight ? "Switch to dark theme" : "Switch to light theme"}
      title={isLight ? "Switch to dark theme" : "Switch to light theme"}
      className="neon-btn relative h-8 w-8 shrink-0 rounded-md border border-slate-200 bg-white flex items-center justify-center overflow-hidden transition-colors hover:bg-slate-50"
    >
      <span
        className="text-sm leading-none transition-transform duration-300"
        style={{ transform: isLight ? "rotate(0deg)" : "rotate(180deg)" }}
      >
        {isLight ? "☀️" : "🌙"}
      </span>
    </button>
  );
}
