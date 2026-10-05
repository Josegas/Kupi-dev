"use client";
import { useState, useEffect, useRef } from "react";
import { ArrowLeft, Heart, Trash2, Bell, BellOff, TrendingDown, TrendingUp, ChevronDown, ChevronUp, ExternalLink, LogOut } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import KupiLogo from "../components/KupiLogo";
import ThemeToggle from "../components/ThemeToggle";
import LanguageToggle from "../components/LanguageToggle";
import { useAuth } from "../lib/auth";
import { useLang } from "../lib/i18n";
import { proxyImage } from "../lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Favorite {
  id: number;
  product_name: string;
  restaurant_name: string;
  rappi_product_id: string | null;
  ubereats_product_id: string | null;
  rappi_store_id: string | null;
  ubereats_store_id: string | null;
  image_url: string;
  created_at: string;
}

interface PriceSnapshot {
  platform: string;
  total: number;
  product_price: number;
  delivery_fee: number;
  service_fee: number;
  sampled_at: string;
}

interface Alert {
  id: number;
  favorite_id: number;
  alert_type: string;
  threshold_pct: number;
  is_active: boolean;
}

function buildCompareHref(fav: Favorite): string {
  const params = new URLSearchParams();
  if (fav.rappi_store_id) params.set("rappi", fav.rappi_store_id);
  if (fav.ubereats_store_id) params.set("ue", fav.ubereats_store_id);
  params.set("name", fav.restaurant_name);
  // Pasar IDs del producto para ir directo a la comparación
  if (fav.rappi_product_id) params.set("r", fav.rappi_product_id);
  if (fav.ubereats_product_id) params.set("u", fav.ubereats_product_id);
  params.set("from", "fav");
  return `/compare/dinamico?${params.toString()}`;
}

/** Agrupa snapshots por fecha de muestreo (redondeando a la hora más cercana) */
function groupByTime(snapshots: PriceSnapshot[]): { time: string; rappi: PriceSnapshot | null; ubereats: PriceSnapshot | null }[] {
  const groups: Record<string, { rappi: PriceSnapshot | null; ubereats: PriceSnapshot | null }> = {};

  for (const s of snapshots) {
    // Redondear al bloque de hora (agrupa snapshots del mismo muestreo)
    const d = new Date(s.sampled_at);
    const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}-${d.getHours()}`;
    if (!groups[key]) groups[key] = { rappi: null, ubereats: null };
    if (s.platform === "rappi") groups[key].rappi = s;
    else groups[key].ubereats = s;
  }

  return Object.entries(groups)
    .map(([, g]) => ({
      time: (g.rappi || g.ubereats)!.sampled_at,
      rappi: g.rappi,
      ubereats: g.ubereats,
    }))
    .sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime()); // más reciente primero
}

export default function FavoritosPage() {
  const { user, session, signOut, loading: authLoading } = useAuth();
  const { lang, t } = useLang();
  const router = useRouter();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  const formatDate = (iso: string): string => {
    const locale = lang === "en" ? "en-US" : "es-MX";
    const d = new Date(iso);
    return d.toLocaleDateString(locale, { day: "numeric", month: "short" }) +
      ", " + d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  };

  // Cerrar menú de usuario al hacer click fuera
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFav, setSelectedFav] = useState<number | null>(null);
  const [history, setHistory] = useState<PriceSnapshot[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/login");
      return;
    }
    loadData();
  }, [user, authLoading]);

  const headers = () => ({
    Authorization: `Bearer ${session!.access_token}`,
    "Content-Type": "application/json",
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [favsRes, alertsRes] = await Promise.allSettled([
        fetch(`${API_URL}/favorites`, { headers: headers() }),
        fetch(`${API_URL}/alerts`, { headers: headers() }),
      ]);
      if (favsRes.status === "fulfilled" && favsRes.value.ok) {
        setFavorites(await favsRes.value.json());
      }
      if (alertsRes.status === "fulfilled" && alertsRes.value.ok) {
        setAlerts(await alertsRes.value.json());
      }
    } catch { /* silencioso */ }
    setLoading(false);
  };

  const removeFavorite = async (id: number) => {
    await fetch(`${API_URL}/favorites/${id}`, { method: "DELETE", headers: headers() });
    setFavorites((prev) => prev.filter((f) => f.id !== id));
    setAlerts((prev) => prev.filter((a) => a.favorite_id !== id));
    if (selectedFav === id) {
      setSelectedFav(null);
      setHistory([]);
    }
  };

  const toggleAlert = async (favId: number) => {
    const existing = alerts.find((a) => a.favorite_id === favId);
    if (existing) {
      const resp = await fetch(`${API_URL}/alerts/${existing.id}`, {
        method: "PATCH",
        headers: headers(),
        body: JSON.stringify({ is_active: !existing.is_active }),
      });
      if (resp.ok) {
        const updated = await resp.json();
        setAlerts((prev) => prev.map((a) => (a.id === existing.id ? updated : a)));
      }
    } else {
      const resp = await fetch(`${API_URL}/alerts`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ favorite_id: favId, alert_type: "price_drop", threshold_pct: 5 }),
      });
      if (resp.ok) {
        const created = await resp.json();
        setAlerts((prev) => [...prev, created]);
      }
    }
  };

  const loadHistory = async (favId: number) => {
    if (selectedFav === favId) {
      setSelectedFav(null);
      setHistory([]);
      return;
    }
    setSelectedFav(favId);
    setLoadingHistory(true);
    try {
      const resp = await fetch(`${API_URL}/favorites/${favId}/history?days=7`, { headers: headers() });
      setHistory(await resp.json());
    } catch {
      setHistory([]);
    }
    setLoadingHistory(false);
  };

  if (authLoading || (!user && !authLoading)) {
    return <div className="min-h-screen bg-[var(--bg)]" />;
  }

  return (
    <div className="min-h-screen bg-[var(--bg)]">
      {/* Header */}
      <div className="bg-[var(--surface)] border-b border-[var(--border)] sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 h-16 flex items-center gap-4">
          <Link href="/buscar" className="kupi-link text-[var(--text-secondary)]">
            <ArrowLeft size={20} />
          </Link>
          <Link href="/buscar" className="shrink-0">
            <KupiLogo size={110} imageSrc="/Kupilogo6.png" />
          </Link>
          <div className="w-px h-6 bg-[var(--border)]" />
          <h1 className="text-[16px] font-semibold text-[var(--text-primary)] flex-1" style={{ fontFamily: "var(--font-display)" }}>
            {t.favoritos.title}
          </h1>

          <LanguageToggle />
          <ThemeToggle />

          {user && (
            <div className="relative shrink-0" ref={userMenuRef}>
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="w-8 h-8 rounded-full bg-[var(--brand-tint)] flex items-center justify-center"
              >
                <span className="text-xs font-semibold text-[var(--brand)]">
                  {(user.email?.[0] ?? "U").toUpperCase()}
                </span>
              </button>
              {userMenuOpen && (
                <div className="absolute right-0 top-full mt-2 w-48 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-lg overflow-hidden z-50">
                  <p className="px-4 py-2 text-[11px] text-[var(--text-muted)] truncate border-b border-[var(--border)]">
                    {user.email}
                  </p>
                  <button
                    onClick={() => { signOut(); setUserMenuOpen(false); }}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-[13px] text-red-500 hover:bg-[var(--bg)] transition-colors"
                  >
                    <LogOut size={14} />
                    {lang === "en" ? "Sign out" : "Cerrar sesión"}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-xl bg-[var(--surface)] border border-[var(--border)] animate-pulse h-28" />
            ))}
          </div>
        ) : favorites.length === 0 ? (
          <div className="text-center py-20">
            <Heart size={40} className="text-[var(--text-muted)] mx-auto mb-4" />
            <h2 className="text-[18px] font-semibold text-[var(--text-primary)] mb-2">{t.favoritos.empty}</h2>
            <p className="text-[14px] text-[var(--text-muted)] mb-6">
              {t.favoritos.emptyHint}
            </p>
            <Link
              href="/buscar"
              className="kupi-btn inline-block bg-[var(--brand)] text-white font-semibold text-[14px] rounded-xl px-6 py-3"
            >
              {t.favoritos.searchButton}
            </Link>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {favorites.map((fav) => {
              const alert = alerts.find((a) => a.favorite_id === fav.id);
              const isExpanded = selectedFav === fav.id;
              const compareHref = buildCompareHref(fav);
              const grouped = isExpanded ? groupByTime(history) : [];

              return (
                <div key={fav.id} className="bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden">
                  {/* Card principal */}
                  <div className="flex items-center gap-4 p-4">
                    {/* Imagen + link al producto */}
                    <a href={compareHref} className="w-16 h-16 rounded-lg bg-[var(--bg)] overflow-hidden shrink-0 block">
                      {fav.image_url ? (
                        <img src={proxyImage(fav.image_url)} alt={fav.product_name} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-[var(--text-muted)] text-[10px]">{t.favoritos.noImage}</div>
                      )}
                    </a>

                    {/* Info + link al producto */}
                    <a href={compareHref} className="flex-1 min-w-0 group">
                      <p className="text-[14px] font-semibold text-[var(--text-primary)] truncate group-hover:text-[var(--brand)] transition-colors">
                        {fav.product_name}
                      </p>
                      <p className="text-[12px] text-[var(--text-muted)] truncate">{fav.restaurant_name}</p>
                      <div className="flex items-center gap-1.5 mt-1">
                        {fav.rappi_store_id && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style={{ background: "#FF441F22", color: "#FF441F" }}>Rappi</span>
                        )}
                        {fav.ubereats_store_id && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style={{ background: "#06C16722", color: "#06C167" }}>Uber Eats</span>
                        )}
                        <span className="text-[10px] text-[var(--brand)] flex items-center gap-0.5 ml-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          {t.favoritos.compare} <ExternalLink size={10} />
                        </span>
                      </div>
                    </a>

                    {/* Acciones */}
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => loadHistory(fav.id)}
                        className={`p-2 rounded-lg transition-colors ${isExpanded ? "bg-[var(--brand)] text-white" : "text-[var(--text-muted)] hover:bg-[var(--bg)]"}`}
                        title={t.favoritos.historyTitle2}
                      >
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                      <button
                        onClick={() => toggleAlert(fav.id)}
                        className={`p-2 rounded-lg transition-colors ${
                          alert?.is_active ? "bg-[var(--savings)] text-white" : "text-[var(--text-muted)] hover:bg-[var(--bg)]"
                        }`}
                        title={alert?.is_active
                          ? t.favoritos.alertActiveShort
                          : t.favoritos.alertActivate
                        }
                      >
                        {alert?.is_active ? <Bell size={16} /> : <BellOff size={16} />}
                      </button>
                      <button
                        onClick={() => removeFavorite(fav.id)}
                        className="p-2 rounded-lg text-[var(--text-muted)] hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/10 transition-colors"
                        title={t.favoritos.removeTitle}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>

                  {/* Alerta info inline */}
                  {alert?.is_active && (
                    <div className="px-4 pb-2 -mt-1">
                      <p className="text-[11px] text-[var(--savings)] flex items-center gap-1">
                        <Bell size={10} />
                        {t.favoritos.alertActive}
                      </p>
                    </div>
                  )}

                  {/* Historial expandido */}
                  {isExpanded && (
                    <div className="border-t border-[var(--border)] p-4 bg-[var(--bg)]">
                      {loadingHistory ? (
                        <div className="flex items-center gap-2 text-[13px] text-[var(--text-muted)]">
                          <div className="w-4 h-4 border-2 border-[var(--brand)] border-t-transparent rounded-full animate-spin" />
                          {t.favoritos.loadingHistory}
                        </div>
                      ) : history.length === 0 ? (
                        <p className="text-[13px] text-[var(--text-muted)]">
                          {t.favoritos.historyEmpty}
                        </p>
                      ) : (
                        <div>
                          <p className="text-[12px] font-semibold text-[var(--text-secondary)] mb-3">
                            {t.favoritos.historyTitle}
                          </p>

                          {/* Tabla de historial */}
                          <div className="overflow-x-auto">
                            <table className="w-full text-[12px]">
                              <thead>
                                <tr className="text-[var(--text-muted)] text-left border-b border-[var(--border)]">
                                  <th className="pb-2 font-medium">{t.favoritos.date}</th>
                                  <th className="pb-2 font-medium text-right" style={{ color: "#FF441F" }}>Rappi</th>
                                  <th className="pb-2 font-medium text-right" style={{ color: "#06C167" }}>Uber Eats</th>
                                  <th className="pb-2 font-medium text-right">{t.favoritos.cheaper}</th>
                                </tr>
                              </thead>
                              <tbody>
                                {grouped.slice(0, 14).map((g, i) => {
                                  const rappiTotal = g.rappi?.total ?? null;
                                  const ueTotal = g.ubereats?.total ?? null;
                                  let cheaper: string | null = null;
                                  if (rappiTotal !== null && ueTotal !== null) {
                                    if (rappiTotal < ueTotal) cheaper = "rappi";
                                    else if (ueTotal < rappiTotal) cheaper = "ubereats";
                                    else cheaper = "igual";
                                  }

                                  return (
                                    <tr key={i} className="border-b border-[var(--border)] last:border-0">
                                      <td className="py-2 text-[var(--text-muted)] whitespace-nowrap">
                                        {formatDate(g.time)}
                                      </td>
                                      <td className="py-2 text-right">
                                        {g.rappi ? (
                                          <div>
                                            <span className={`font-semibold ${cheaper === "rappi" ? "text-[var(--savings)]" : "text-[var(--text-primary)]"}`}>
                                              ${g.rappi.total.toFixed(0)}
                                            </span>
                                            <div className="text-[10px] text-[var(--text-muted)]">
                                              {t.favoritos.product} ${g.rappi.product_price.toFixed(0)} + {t.favoritos.delivery} ${(g.rappi.delivery_fee ?? 0).toFixed(0)}
                                            </div>
                                          </div>
                                        ) : (
                                          <span className="text-[var(--text-muted)]">-</span>
                                        )}
                                      </td>
                                      <td className="py-2 text-right">
                                        {g.ubereats ? (
                                          <div>
                                            <span className={`font-semibold ${cheaper === "ubereats" ? "text-[var(--savings)]" : "text-[var(--text-primary)]"}`}>
                                              ${g.ubereats.total.toFixed(0)}
                                            </span>
                                            <div className="text-[10px] text-[var(--text-muted)]">
                                              {t.favoritos.product} ${g.ubereats.product_price.toFixed(0)} + {t.favoritos.delivery} ${(g.ubereats.delivery_fee ?? 0).toFixed(0)}
                                            </div>
                                          </div>
                                        ) : (
                                          <span className="text-[var(--text-muted)]">-</span>
                                        )}
                                      </td>
                                      <td className="py-2 text-right">
                                        {cheaper === "rappi" && (
                                          <span className="text-[11px] font-bold px-1.5 py-0.5 rounded-full" style={{ background: "#FF441F22", color: "#FF441F" }}>
                                            Rappi -${((ueTotal ?? 0) - (rappiTotal ?? 0)).toFixed(0)}
                                          </span>
                                        )}
                                        {cheaper === "ubereats" && (
                                          <span className="text-[11px] font-bold px-1.5 py-0.5 rounded-full" style={{ background: "#06C16722", color: "#06C167" }}>
                                            Uber -${((rappiTotal ?? 0) - (ueTotal ?? 0)).toFixed(0)}
                                          </span>
                                        )}
                                        {cheaper === "igual" && (
                                          <span className="text-[11px] text-[var(--text-muted)]">{t.favoritos.equal}</span>
                                        )}
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>

                          {grouped.length > 14 && (
                            <p className="text-[11px] text-[var(--text-muted)] mt-2 text-center">
                              {t.favoritos.showing} 14 {t.favoritos.of} {grouped.length}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
