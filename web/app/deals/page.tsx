"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import TopNav from "../components/TopNav";
import { fetchDeals, DealProduct, proxyImage } from "../lib/api";

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

  useEffect(() => {
    if (!category) return;
    setProducts([]);
    setLoading(true);
    fetchDeals(category, 100)
      .then(data => setProducts(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [category]);

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
            Precio total verificado (producto + envío + cuota) en Rappi y Uber Eats.
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
              El precio incluye envío y cuota de servicio, verificado en tiempo real.
            </p>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <>
            <p className="text-[13px] text-[var(--text-muted)] mb-5">
              Verificando precios con envío en Rappi y Uber Eats...
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
              {products.length} {products.length === 1 ? "producto" : "productos"} de {category} por menos de $100 con envío incluido
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {products.map((p, i) => {
                const params = new URLSearchParams();
                if (p.rappi_product_id) params.set("r", p.rappi_product_id);
                if (p.ubereats_product_id) params.set("u", p.ubereats_product_id);
                const platformColor = PLATFORM_COLOR[p.best_platform] ?? "var(--savings)";
                const platformLabel = PLATFORM_LABEL[p.best_platform] ?? p.best_platform;

                return (
                  <Link
                    key={`${p.restaurant_id}-${p.rappi_product_id || p.ubereats_product_id}-${i}`}
                    href={`/compare/${p.restaurant_id}?${params.toString()}`}
                    className="block"
                  >
                    <div className="kupi-card h-full bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden">
                      {/* Imagen */}
                      <div className="h-24 bg-[var(--bg)] overflow-hidden">
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
                            ${p.total.toFixed(0)}
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
              No hay productos de <span className="text-[var(--text-primary)] font-medium">{category}</span> por menos de $100 con envío incluido.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
