import { Star } from "lucide-react";
import Link from "next/link";
import { proxyImage } from "../lib/api";

interface Props {
  id: string;
  name: string;
  cuisine: string;
  rating: number;
  fromPrice: number;
  platforms: number;
  imageUrl?: string;
  isOpen?: boolean; // undefined = cargando (no bloquea), false = cerrado
  href?: string; // ruta personalizada (para restaurantes dinámicos)
  hasRappi?: boolean;
  hasUberEats?: boolean;
}

export default function RestaurantCard({ id, name, cuisine, rating, fromPrice, platforms, imageUrl, isOpen, href, hasRappi = true, hasUberEats = true }: Props) {
  const closed = isOpen === false;
  const loading = isOpen === undefined;
  const showRating = rating > 0;

  const platformLabel =
    hasRappi && hasUberEats ? "Rappi · Uber Eats" :
    hasRappi ? "Rappi" :
    hasUberEats ? "Uber Eats" : "";

  const cardBody = (
    <div
      className={`bg-[var(--surface)] border border-[var(--border)] rounded-2xl overflow-hidden shadow-[0_1px_3px_rgba(31,35,35,0.05)] transition-opacity duration-300 ${
        closed   ? "opacity-50 cursor-default" :
        loading  ? "opacity-70 cursor-default animate-pulse" :
                   "kupi-card cursor-pointer"
      }`}
    >
      {/* Imagen */}
      <div className="h-36 bg-[var(--bg)] relative">
        {imageUrl ? (
          <img
            src={proxyImage(imageUrl)}
            alt={name}
            className="w-full h-full object-cover"
            loading="lazy"
            onError={(e) => {
              const img = e.target as HTMLImageElement;
              if (img.src !== imageUrl) img.src = imageUrl;
              else img.style.display = "none";
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-[var(--text-muted)] text-xs">
            Sin imagen
          </div>
        )}
        {closed && (
          <div className="absolute inset-0 flex items-center justify-center bg-[rgba(31,35,35,0.45)]">
            <span className="text-[13px] font-semibold text-white px-3 py-1 rounded-full bg-[rgba(31,35,35,0.7)]">
              Cerrado
            </span>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-4 flex flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="text-[16px] font-bold text-[var(--text-primary)] leading-tight">{name}</h3>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="text-[13px] text-[var(--text-secondary)]">{cuisine}</span>
              {showRating && (
                <>
                  <span className="text-[var(--text-muted)]">·</span>
                  <Star size={12} fill="var(--brand)" stroke="none" />
                  <span className="text-[13px] text-[var(--text-secondary)]">{rating.toFixed(1)}</span>
                </>
              )}
            </div>
          </div>
          {platformLabel && (
            <span className="shrink-0 text-[12px] font-semibold px-2.5 py-1 rounded-full bg-[var(--brand-tint)] text-[var(--brand)]">
              {platformLabel}
            </span>
          )}
        </div>

        {closed ? (
          <p className="text-[13px] text-[var(--text-muted)]">No disponible ahora</p>
        ) : fromPrice > 0 ? (
          <p className="text-[15px] font-bold text-[var(--savings)]">
            Desde ${fromPrice.toFixed(0)}
          </p>
        ) : null}
      </div>
    </div>
  );

  if (closed || loading) return cardBody;

  const linkHref = href || `/compare/${id}`;
  return <Link href={linkHref}>{cardBody}</Link>;
}
