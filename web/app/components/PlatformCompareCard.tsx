"use client";
import { ArrowRight } from "lucide-react";
import { useLang } from "../lib/i18n";

interface Props {
  platform: string;
  productPrice: number;
  deliveryFee: number | null; // null en DiDi (no disponible fuera de la app)
  serviceFee: number | null;
  total: number;
  etaMinutes?: number;
  storeName?: string;
  storeAddress?: string;
  isCheapest: boolean;
  approximate?: boolean;
  isEstimate?: boolean;
  cardIndex?: number;
  variantLabel?: string;
  isOpen?: boolean;
  opensAt?: string;
  itemCount?: number;
  onSelect: () => void;
}

const PLATFORM_LABELS: Record<string, string> = {
  rappi: "Rappi",
  ubereats: "Uber Eats",
  didi: "DiDi Food",
};

const PLATFORM_COLORS: Record<string, string> = {
  rappi: "#FF441F",
  ubereats: "#06C167",
  didi: "#FF6600",
};

export default function PlatformCompareCard({
  platform,
  productPrice,
  deliveryFee,
  serviceFee,
  total,
  etaMinutes,
  storeName,
  storeAddress,
  isCheapest,
  approximate,
  cardIndex = 0,
  variantLabel,
  isOpen = true,
  opensAt,
  isEstimate,
  itemCount,
  onSelect,
}: Props) {
  const { t } = useLang();
  const badgeDelay = cardIndex * 80 + 80 + 360 + 60;
  return (
    <div
      onClick={onSelect}
      className={`compare-card kupi-card cursor-pointer rounded-2xl border p-5 flex flex-col gap-4 transition-colors duration-300 ${
        isCheapest
          ? "bg-[var(--savings-tint)] border-[var(--savings)] border-[1.5px]"
          : "bg-[var(--surface)] border-[var(--border)]"
      }`}
    >
      {/* Header plataforma */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <div
            className="w-2.5 h-2.5 rounded-full shrink-0"
            style={{ background: PLATFORM_COLORS[platform] }}
          />
          <span className="text-[15px] font-semibold text-[var(--text-primary)]">
            {PLATFORM_LABELS[platform]}
          </span>
          {etaMinutes && isOpen && (
            <span className="text-[12px] text-[var(--text-muted)]">{etaMinutes} min</span>
          )}
          {!isOpen && (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[var(--border)] text-[var(--text-secondary)]">
              Cerrado
            </span>
          )}
        </div>
        {isCheapest && (
          <span
            className="badge-cheapest text-[11px] font-bold px-2.5 py-1 rounded-full bg-[var(--savings)] text-white"
            style={{ animationDelay: `${badgeDelay}ms` }}
          >
            {t.compare.cheapest}
          </span>
        )}
      </div>

      {/* Sucursal */}
      {storeName && (
        <div className="flex flex-col gap-0.5 -mt-1">
          <span className="text-[12px] font-medium text-[var(--text-secondary)] leading-tight">{storeName}</span>
          {storeAddress && (
            <span className="text-[11px] text-[var(--text-muted)] leading-tight">{storeAddress}</span>
          )}
          {!isOpen && opensAt && (
            <span className="text-[11px] text-[var(--text-muted)] leading-tight">{opensAt}</span>
          )}
        </div>
      )}

      {/* Precio total */}
      <div className="flex items-baseline gap-1">
        {platform === "didi" && (
          <span className="text-[12px] text-[var(--text-muted)]">desde</span>
        )}
        <p
          className="text-[20px] font-bold"
          style={{ color: isCheapest ? "var(--savings)" : "var(--text-primary)" }}
        >
          ${total.toFixed(2)}
        </p>
      </div>

      {/* Desglose */}
      <div className="flex flex-col gap-1.5 text-[13px]">
        <div className="flex justify-between text-[var(--text-secondary)]">
          <span>
            {itemCount && itemCount > 1 ? `Productos (${itemCount})` : t.compare.product}
            {variantLabel && (
              <span className="ml-1.5 text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-[var(--brand-tint)] text-[var(--brand)]">
                {variantLabel}
              </span>
            )}
          </span>
          <span>${productPrice.toFixed(2)}</span>
        </div>
        <div className="flex justify-between text-[var(--text-secondary)]">
          <span>{t.compare.delivery}</span>
          {deliveryFee === null
            ? <span className="text-[var(--text-muted)] italic text-[12px]">ver en app</span>
            : <span>${deliveryFee.toFixed(2)}</span>
          }
        </div>
        {serviceFee !== null && serviceFee > 0 && (
          <div className="flex justify-between text-[var(--text-secondary)]">
            <span>{t.compare.serviceFee}</span>
            <span>${serviceFee.toFixed(2)}</span>
          </div>
        )}
        <div className="border-t border-[var(--border)] pt-1.5 flex justify-between font-semibold text-[var(--text-primary)]">
          <span>{t.compare.total}</span>
          <span>${total.toFixed(2)}</span>
        </div>
      </div>


      {isEstimate && (
        <p className="text-[11px] text-amber-500 leading-snug -mt-1 font-medium">
          Precio estimado. El envío y tarifa de servicio pueden variar.
        </p>
      )}

      {platform === "didi" && (
        <p className="text-[11px] text-[var(--text-muted)] leading-snug -mt-1">
          Precio de menú. El envío y total final solo aparecen dentro de la app de DiDi.
        </p>
      )}

      <button className="flex items-center justify-center gap-2 text-[13px] font-semibold text-[var(--brand)] mt-auto">
        {t.compare.viewOn} {PLATFORM_LABELS[platform]} <ArrowRight size={14} />
      </button>
    </div>
  );
}
