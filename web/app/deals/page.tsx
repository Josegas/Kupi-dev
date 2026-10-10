"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import TopNav from "../components/TopNav";
import { fetchDeals, DealProduct, proxyImage } from "../lib/api";
import { useLocation } from "../lib/location";

const CATEGORIES = ["Pizza", "Pollo", "Sushi", "Hamburguesas", "Tacos", "Café"];

const PLATFORM_COLOR: Record<string, string> = {
  rappi: "#FF441F",
  ubereats: "#06C167",
};
const PLATFORM_LABEL: Record<string, string> = {
  rappi: "Rappi",
  ubereats: "Uber Eats",
};

export default function Deals() {
  const [category, setCategory] = useState<string | null>(null);
  const [products, setProducts] = useState<DealProduct[]>([]);
  const [loading, setLoading] = useState(false);
  const { location, hasLocation } = useLocation();

  useEffect(() => {
    if (!category || !hasLocation) return;
    setProducts([]);
    setLoading(true);
    fetchDeals(category, location.lat, location.lng, 100)
      .then(data => setProducts(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [category, location, hasLocation]);

  return (
    <div className="min-h-screen bg-[var(--bg)] transition-colors duration-300">
      <TopNav />
      <main className="max-w-6xl mx-auto px-12 py-10">

        {/* Header */}
        <div className="mb-8">
          <Link
            href="/buscar"
            className="inline-flex items-center gap-1.5 text-[13px] text-[var(--text-muted)] hover:text-[var(--brand)] kupi-link mb-4"
          >
            <ArrowLeft size={14} />
            Volver
          </Link>
          <h1
            className="text-[26px] font-bold text-[var(--text-primary)] mb-2"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Menos de $100
          </h1>
          <p className="text-[15px] text-[var(--text-secondary)]">
            Productos cerca de ti en Rappi y Uber Eats, con las ofertas primero. Al abrir uno ves el total exacto con envío y cuota.
          </p>
        </div>

        {/* Chips de categoría — requerido seleccionar una */}
        <div className="flex gap-2 overflow-x-auto pb-2 mb-8" style={{ scrollbarWidth: "none" }}>
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              className={`shrink-0 px-4 py-1.5 rounded-full text-[13px] font-semibold border transition-colors ${
                category === cat
                  ? "bg-[var(--brand)] text-white border-[var(--brand)]"
                  : "bg-[var(--surface)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--brand)] hover:text-[var(--brand)]"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Estado: sin categoría seleccionada */}
        {!category && (
          <div className="py-20 text-center">
            <p className="text-[15px] text-[var(--text-secondary)]">
              Selecciona una categoría para ver productos por menos de $100
            </p>
            <p className="text-[13px] text-[var(--text-muted)] mt-2">
              Al abrir un producto ves el total exacto con envío y cuota en ambas apps.
            </p>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <>
            <p className="text-[13px] text-[var(--text-muted)] mb-5">
              Buscando productos en Rappi y Uber Eats cerca de ti...
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="h-[168px] rounded-xl bg-[var(--surface)] border border-[var(--border)] animate-pulse" />
              ))}
            </div>
          </>
        )}

        {/* Resultados */}
        {!loading && category && products.length > 0 && (
          <>
            <p className="text-[13px] text-[var(--text-muted)] mb-5">
              {products.length} {products.length === 1 ? "producto" : "productos"} de {category} por menos de $100
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {products.map((p, i) => {
                const params = new URLSearchParams({
                  rappi: p.rappi_store_id, ue: p.ubereats_store_id, name: p.restaurant_name,
                  r: p.rappi_product_id, u: p.ubereats_product_id,
                });
                const platform = p.price_platform ?? "rappi";
                const platformColor = PLATFORM_COLOR[platform];
                const platformLabel = PLATFORM_LABEL[platform];
                const off = p.real_price && p.real_price > p.price ? Math.round((1 - p.price / p.real_price) * 100) : 0;

                return (
                  <Link
                    key={`${p.rappi_store_id}-${p.rappi_product_id}-${i}`}
                    href={`/compare/dinamico?${params.toString()}`}
                    className="block"
                  >
                    <div className="kupi-card h-full bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden">
                      {/* Imagen */}
                      <div className="relative h-24 bg-[var(--bg)] overflow-hidden">
                        {off > 0 && (
                          <span className="absolute top-1.5 left-1.5 z-10 text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[var(--savings)] text-white">
                            -{off}%
                          </span>
                        )}
                        {p.image_url ? (
                          <img
                            src={proxyImage(p.image_url)}
                            alt={p.name}
                            loading="lazy"
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              const img = e.target as HTMLImageElement;
                              if (img.src !== p.image_url) img.src = p.image_url;
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
                          {p.name}
                        </p>
                        <p className="text-[11px] text-[var(--text-muted)] truncate">{p.restaurant_name}</p>
                        <div className="flex items-center justify-between gap-1 mt-0.5">
                          <span
                            className="text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0"
                            style={{ background: platformColor + "22", color: platformColor }}
                          >
                            {platformLabel}
                          </span>
                          <span className="text-[13px] font-bold text-[var(--savings)] shrink-0">
                            ${p.price.toFixed(0)}
                            {off > 0 && <span className="ml-1 text-[11px] font-medium text-[var(--text-muted)] line-through">${p.real_price!.toFixed(0)}</span>}
                          </span>
                        </div>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </>
        )}

        {/* Sin resultados */}
        {!loading && category && products.length === 0 && (
          <div className="py-20 text-center">
            <p className="text-[15px] text-[var(--text-muted)]">
              No hay productos de <span className="text-[var(--text-primary)] font-medium">{category}</span> por menos de $100 cerca de ti.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
