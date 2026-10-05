"use client";
import { useLang } from "../lib/i18n";

const CATEGORIES: { key: string; icon: string }[] = [
  { key: "Todo",          icon: "🍽️" },
  { key: "Pizza",         icon: "🍕" },
  { key: "Hamburguesas",  icon: "🍔" },
  { key: "Tacos",         icon: "🌮" },
  { key: "Sushi",         icon: "🍣" },
  { key: "Pollo",         icon: "🍗" },
  { key: "Postres",       icon: "🍰" },
  { key: "Café",          icon: "☕" },
];

interface Props {
  selected: string;
  onSelect: (cat: string) => void;
}

export default function CategoryChips({ selected, onSelect }: Props) {
  const { t } = useLang();

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
      {CATEGORIES.map(({ key, icon }) => (
        <button
          key={key}
          onClick={() => onSelect(key)}
          className={`shrink-0 px-4 h-8 rounded-full text-[13px] font-semibold border active:scale-95 transition-[transform,colors] duration-[160ms] [transition-timing-function:cubic-bezier(0.23,1,0.32,1)] flex items-center gap-1.5 ${
            selected === key
              ? "bg-[var(--brand)] text-white border-[var(--brand)]"
              : "bg-[var(--surface)] text-[var(--text-primary)] border-[var(--border)] hover:border-[var(--brand)] hover:text-[var(--brand)]"
          }`}
        >
          <span className="text-[14px]">{icon}</span>
          {t.buscar.categories[key as keyof typeof t.buscar.categories] ?? key}
        </button>
      ))}
    </div>
  );
}
