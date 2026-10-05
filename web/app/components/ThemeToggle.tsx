"use client";
import { useState, useEffect } from "react";
import { useLang } from "../lib/i18n";

export default function ThemeToggle() {
  const [isNoche, setIsNoche] = useState(false);
  const { t } = useLang();

  // Leer tema guardado al montar
  useEffect(() => {
    const saved = localStorage.getItem("kupi-theme");
    if (saved === null || saved === "noche") {
      setIsNoche(true);
      document.documentElement.setAttribute("data-theme", "noche");
    } else {
      setIsNoche(false);
    }
  }, []);

  const toggle = () => {
    const next = !isNoche;
    setIsNoche(next);
    document.documentElement.setAttribute("data-theme", next ? "noche" : "");
    localStorage.setItem("kupi-theme", next ? "noche" : "");
  };

  return (
    <button
      onClick={toggle}
      className="shrink-0 flex items-center gap-1.5 text-[12px] font-semibold px-3 h-7 rounded-full border border-[var(--border)] text-[var(--text-muted)] transition-colors"
      style={{ fontFamily: "var(--font-body)" }}
    >
      <span>{isNoche ? "☀" : "🌙"}</span>
      {isNoche ? t.nav.themeDay : t.nav.themeNight}
    </button>
  );
}
