"use client";
import { useLang } from "../lib/i18n";

export default function LanguageToggle({ dark = false }: { dark?: boolean }) {
  const { lang, toggle } = useLang();
  return (
    <button
      onClick={toggle}
      className="text-[11px] font-semibold tracking-[0.14em] uppercase transition-colors duration-200"
      style={{
        color: dark ? "rgba(245,241,236,0.35)" : "var(--text-muted)",
      }}
      title={lang === "es" ? "Switch to English" : "Cambiar a Español"}
    >
      {lang === "es" ? "EN" : "ES"}
    </button>
  );
}
