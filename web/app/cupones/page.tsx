"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Tag, ExternalLink } from "lucide-react";
import TopNav from "../components/TopNav";
import { fetchCoupons, Coupon } from "../lib/supabase";

const PLATFORM_COLOR: Record<string, string> = {
  rappi: "#FF441F",
  ubereats: "#06C167",
};
const PLATFORM_LABEL: Record<string, string> = {
  rappi: "Rappi",
  ubereats: "Uber Eats",
};

function CouponCard({ coupon }: { coupon: Coupon }) {
  const color = PLATFORM_COLOR[coupon.platform] ?? "var(--brand)";
  const label = PLATFORM_LABEL[coupon.platform] ?? coupon.platform;

  return (
    <div className="kupi-card bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-4 flex flex-col gap-2">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <span
          className="text-[11px] font-bold px-2 py-0.5 rounded-full shrink-0"
          style={{ background: color + "22", color }}
        >
          {label}
        </span>
        <span className="text-[12px] text-[var(--text-muted)] text-right truncate">
          {coupon.restaurant_name}
        </span>
      </div>

      {/* Descripción */}
      <p className="text-[14px] font-semibold text-[var(--text-primary)] leading-snug">
        {coupon.description}
      </p>

      {/* Deep link si existe */}
      {coupon.deep_link && (
        <a
          href={coupon.deep_link}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 inline-flex items-center gap-1.5 text-[12px] font-semibold self-start"
          style={{ color }}
        >
          <ExternalLink size={12} />
          Ver en {label}
        </a>
      )}
    </div>
  );
}

export default function Cupones() {
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "rappi" | "ubereats">("all");

  useEffect(() => {
    fetchCoupons()
      .then(setCoupons)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = filter === "all" ? coupons : coupons.filter((c) => c.platform === filter);

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
            Cupones activos
          </h1>
          <p className="text-[15px] text-[var(--text-secondary)]">
            Promociones verificadas en Rappi y Uber Eats.
          </p>
        </div>

        {/* Filtro de plataforma */}
        <div className="flex gap-2 mb-8">
          {(["all", "rappi", "ubereats"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setFilter(p)}
              className={`px-4 py-1.5 rounded-full text-[13px] font-semibold border transition-colors ${
                filter === p
                  ? "bg-[var(--brand)] text-white border-[var(--brand)]"
                  : "bg-[var(--surface)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--brand)] hover:text-[var(--brand)]"
              }`}
            >
              {p === "all" ? "Todos" : PLATFORM_LABEL[p]}
            </button>
          ))}
        </div>

        {/* Loading */}
        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-32 rounded-2xl bg-[var(--surface)] border border-[var(--border)] animate-pulse" />
            ))}
          </div>
        )}

        {/* Cupones */}
        {!loading && filtered.length > 0 && (
          <>
            <p className="text-[13px] text-[var(--text-muted)] mb-5">
              {filtered.length} {filtered.length === 1 ? "cupón activo" : "cupones activos"}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map((c) => (
                <CouponCard key={c.id} coupon={c} />
              ))}
            </div>
          </>
        )}

        {/* Sin resultados */}
        {!loading && filtered.length === 0 && (
          <div className="py-20 text-center">
            <Tag size={32} className="mx-auto mb-3 text-[var(--text-muted)]" />
            <p className="text-[15px] text-[var(--text-secondary)]">
              No hay cupones activos en este momento.
            </p>
            <p className="text-[13px] text-[var(--text-muted)] mt-2">
              Los cupones se actualizan periódicamente desde Rappi y Uber Eats.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
