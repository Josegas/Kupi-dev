import Link from "next/link";
import { proxyImage } from "../lib/api";

interface Props {
  name: string;
  price: number;
  image_url: string;
  restaurant_id: string;
  restaurant_name: string;
  category: string;
  rappi_product_id?: string;
  ubereats_product_id?: string;
}

export default function FeaturedProductCard({
  name,
  price,
  image_url,
  restaurant_id,
  restaurant_name,
  category,
  rappi_product_id,
  ubereats_product_id,
}: Props) {
  const params = new URLSearchParams();
  if (rappi_product_id) params.set("r", rappi_product_id);
  if (ubereats_product_id) params.set("u", ubereats_product_id);
  const href = `/compare/${restaurant_id}?${params.toString()}`;

  return (
    <Link href={href} className="block shrink-0 w-36">
      <div className="kupi-card h-full bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden">
        {/* Imagen */}
        <div className="h-24 bg-[var(--bg)] overflow-hidden relative">
          {image_url ? (
            <img
              src={proxyImage(image_url)}
              alt={name}
              loading="lazy"
              className="w-full h-full object-cover"
              onError={(e) => {
                const img = e.target as HTMLImageElement;
                if (img.src !== image_url) img.src = image_url;
                else img.style.display = "none";
              }}
            />
          ) : (
            <div className="w-full h-full" />
          )}
        </div>

        {/* Info */}
        <div className="p-2.5 flex flex-col gap-1">
          <p className="text-[12px] font-semibold text-[var(--text-primary)] leading-tight line-clamp-2">
            {name}
          </p>
          <p className="text-[11px] text-[var(--text-muted)] truncate">{restaurant_name}</p>
          <div className="flex items-center justify-between gap-1 mt-0.5">
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-[var(--brand-tint)] text-[var(--brand)] truncate">
              {category}
            </span>
            <span className="text-[13px] font-bold text-[var(--savings)] shrink-0">
              ${price.toFixed(0)}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}
