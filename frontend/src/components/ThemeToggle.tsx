import { useEffect, useState } from "react";

type Mode = "light" | "dark";
type Palette = "ember" | "ocean" | "violet" | "emerald";

const MODE_KEY = "f5ci-theme";
const PALETTE_KEY = "f5ci-palette";

const PALETTES: { id: Palette; label: string; swatch: string }[] = [
  { id: "ember", label: "Ember", swatch: "#ff5a1f" },
  { id: "ocean", label: "Ocean", swatch: "#22d3ee" },
  { id: "violet", label: "Violet", swatch: "#a78bfa" },
  { id: "emerald", label: "Emerald", swatch: "#34d399" },
];

function getInitialMode(): Mode {
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "light" ? "light" : "dark";
}

function getInitialPalette(): Palette {
  const attr = document.documentElement.getAttribute("data-palette");
  return PALETTES.some((p) => p.id === attr) ? (attr as Palette) : "ember";
}

export function ThemeToggle() {
  const [mode, setMode] = useState<Mode>(getInitialMode);
  const [palette, setPalette] = useState<Palette>(getInitialPalette);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", mode);
    try {
      localStorage.setItem(MODE_KEY, mode);
    } catch {
      // best-effort; theme just won't persist across reloads
    }
  }, [mode]);

  useEffect(() => {
    document.documentElement.setAttribute("data-palette", palette);
    try {
      localStorage.setItem(PALETTE_KEY, palette);
    } catch {
      // best-effort
    }
  }, [palette]);

  useEffect(() => {
    if (!pickerOpen) return;
    function onClickOutside(e: MouseEvent) {
      if (!(e.target instanceof Element) || !e.target.closest("[data-palette-picker]")) {
        setPickerOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [pickerOpen]);

  const isLight = mode === "light";

  return (
    <div className="flex items-center gap-2">
      <div className="relative" data-palette-picker>
        <button
          type="button"
          onClick={() => setPickerOpen((v) => !v)}
          aria-label="Choose color theme"
          title="Choose color theme"
          className="neon-btn h-8 w-8 shrink-0 rounded-md border border-slate-200 bg-white flex items-center justify-center hover:bg-slate-50"
        >
          <span
            className="h-3.5 w-3.5 rounded-full"
            style={{ background: PALETTES.find((p) => p.id === palette)?.swatch, boxShadow: "var(--glow-cyan)" }}
          />
        </button>
        {pickerOpen && (
          <div
            className="animate-page-in absolute right-0 top-[calc(100%+6px)] z-50 flex gap-1.5 rounded-lg border border-slate-200 bg-white p-2 shadow-lg"
            role="menu"
          >
            {PALETTES.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setPalette(p.id);
                  setPickerOpen(false);
                }}
                title={p.label}
                aria-label={`Use ${p.label} theme`}
                className="flex flex-col items-center gap-1 rounded-md px-1.5 py-1 hover:bg-slate-50"
              >
                <span
                  className="h-5 w-5 rounded-full transition-transform"
                  style={{
                    background: p.swatch,
                    boxShadow: p.id === palette ? `0 0 0 2px var(--surface), 0 0 0 4px ${p.swatch}` : "none",
                    transform: p.id === palette ? "scale(1.1)" : "scale(1)",
                  }}
                />
                <span className="text-[9px] uppercase tracking-wide text-slate-500">{p.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => setMode(isLight ? "dark" : "light")}
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
    </div>
  );
}
