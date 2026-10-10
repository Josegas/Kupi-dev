"use client";
import { OfferItem, OfferSection, proxyImage } from "../lib/api";

const PLATFORM_LABELS: Record<string, string> = { rappi: "Rappi", ubereats: "Uber Eats" };
const PLATFORM_COLORS: Record<string, string> = { rappi: "#FF441F", ubereats: "#06C167" };

interface Props {
  sections: OfferSection[];
  loading: boolean;
  hrefFor: (item: OfferItem) => string;
}

/** Carruseles de ofertas de Rappi (productos) y Uber Eats (tiendas) en la zona del usuario. */
export default function OfferSections({ sections, loading, hrefFor }: Props) {
  if (loading) {
    return (
      <div className="mb-10">
        <div className="h-5 w-48 rounded bg-[var(--surface)] animate-pulse mb-4" />
        <div className="flex gap-3 overflow-hidden">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="w-40 h-52 shrink-0 rounded-xl bg-[var(--surface)] border border-[var(--border)] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <>
      {sections.map((s) => (
        <section key={`${s.platform}-${s.title}`} className="mb-8">
          <div className="flex items-baseline gap-2 mb-3">
            <h2 className="text-[18px] font-semibold text-[var(--text-primary)]" style={{ fontFamily: "var(--font-display)" }}>
              {s.title}
            </h2>
            <span className="text-[12px] font-semibold" style={{ color: PLATFORM_COLORS[s.platform] }}>
              en {PLATFORM_LABELS[s.platform]}
            </span>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide">
            {s.items.map((item, i) =>
              s.kind === "products" ? (
                <ProductCard key={`${item.rappi_store_id}-${item.name}-${i}`} item={item} href={hrefFor(item)} />
              ) : (
                <StoreCard key={`${item.ubereats_store_id}-${i}`} item={item} href={hrefFor(item)} />
              )
            )}
          </div>
        </section>
      ))}
    </>
  );
}

function ProductCard({ item, href }: { item: OfferItem; href: string }) {
  const price = item.price ?? 0;
  const off = item.real_price && item.real_price > price ? Math.round((1 - price / item.real_price) * 100) : 0;
  return (
    <a href={href} className="kupi-card w-40 shrink-0 bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden hover:border-[var(--brand)]">
      <div className="relative h-28 bg-[var(--bg)] overflow-hidden">
        {off > 0 && (
          <span className="absolute top-1.5 left-1.5 z-10 text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[var(--savings)] text-white">
            -{off}%
          </span>
        )}
        {item.image_url && (
          <img src={proxyImage(item.image_url)} alt={item.name} loading="lazy" className="w-full h-full object-cover" />
        )}
      </div>
      <div className="p-2">
        <p className="text-[12px] font-medium text-[var(--text-primary)] leading-tight line-clamp-2 mb-0.5">{item.name}</p>
        <p className="text-[13px] font-bold text-[var(--savings)]">
          ${price.toFixed(0)}
          {off > 0 && <span className="ml-1 text-[11px] font-medium text-[var(--text-muted)] line-through">${item.real_price!.toFixed(0)}</span>}
        </p>
        <p className="text-[11px] text-[var(--text-muted)] truncate">{item.store_name}</p>
      </div>
    </a>
  );
}

function StoreCard({ item, href }: { item: OfferItem; href: string }) {
  return (
    <a href={href} className="kupi-card w-56 shrink-0 bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden hover:border-[var(--brand)]">
      <div className="h-28 bg-[var(--bg)] overflow-hidden">
        {item.image_url && (
          <img src={proxyImage(item.image_url)} alt={item.store_name} loading="lazy" className="w-full h-full object-cover" />
        )}
      </div>
      <div className="p-2.5">
        <p className="text-[13px] font-semibold text-[var(--text-primary)] truncate">{item.store_name}</p>
        {item.offer && (
          <p className="mt-1 text-[11px] font-semibold text-[var(--savings)] bg-[var(--savings-tint)] rounded-md px-1.5 py-0.5 line-clamp-2">
            {item.offer}
          </p>
        )}
      </div>
    </a>
  );
}
