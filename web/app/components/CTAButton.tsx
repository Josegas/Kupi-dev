"use client";
import { ArrowRight } from "lucide-react";
import { useLang } from "../lib/i18n";

interface Props {
  platform: string;
  total: number;
  href: string;
}

const PLATFORM_LABELS: Record<string, string> = {
  rappi: "Rappi",
  ubereats: "Uber Eats",
  didi: "DiDi Food",
};

const PLATFORM_COLORS: Record<string, { bg: string; shadow: string }> = {
  rappi: { bg: "#FF441F", shadow: "rgba(255,68,31,0.25)" },
  ubereats: { bg: "#06C167", shadow: "rgba(6,193,103,0.25)" },
  didi: { bg: "#FF6600", shadow: "rgba(255,102,0,0.25)" },
};

export default function CTAButton({ platform, total, href }: Props) {
  const { t } = useLang();
  const colors = PLATFORM_COLORS[platform];
  return (
    <div className="kupi-cta-bar fixed bottom-0 left-0 right-0 bg-[var(--surface)] border-t border-[var(--border)] px-6 py-4">
      <div className="max-w-6xl mx-auto">
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="kupi-btn flex items-center justify-center gap-2 w-full h-13 rounded-2xl text-white text-[15px] font-bold select-none"
          style={
            colors
              ? { backgroundColor: colors.bg, boxShadow: `0 4px 12px ${colors.shadow}` }
              : { backgroundColor: "var(--savings)", boxShadow: "0 4px 12px rgba(21,128,61,0.25)" }
          }
        >
          {t.compare.goTo} {PLATFORM_LABELS[platform] ?? platform} · ${total.toFixed(2)}
          <ArrowRight size={16} />
        </a>
      </div>
    </div>
  );
}
