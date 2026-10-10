"use client";
import { useState, useMemo, useEffect, useRef } from "react";
import TopNav from "../components/TopNav";
import CategoryChips from "../components/CategoryChips";
import RestaurantCard from "../components/RestaurantCard";
import OfferSections from "../components/OfferSections";
import { fetchStoresStatus, searchRestaurants, fetchPopularRestaurants, fetchOffers, fetchPlatformsStatus, proxyImage, SearchResult, PopularRestaurant, OfferSection, PlatformsStatus } from "../lib/api";
import { useLocation } from "../lib/location";
import { useLang } from "../lib/i18n";

function buildHref(r: { rappi_store_id: string | null; ubereats_store_id: string | null; restaurant_name: string }): string {
  const params = new URLSearchParams();
  if (r.rappi_store_id) params.set("rappi", r.rappi_store_id);
  if (r.ubereats_store_id) params.set("ue", r.ubereats_store_id);
  params.set("name", r.restaurant_name);
  return `/compare/dinamico?${params.toString()}`;
}

export default function Buscar() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("Todo");
  const [platformFilter, setPlatformFilter] = useState<"all" | "rappi" | "ubereats" | "both">("all");
  const { t } = useLang();
  const { location, hasLocation } = useLocation();
  const lastSearchedRef = useRef("");

  // Search results from API
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  // Popular restaurants from DB
  const [popular, setPopular] = useState<PopularRestaurant[]>([]);
  const [loadingPopular, setLoadingPopular] = useState(true);


  // Restore search state from sessionStorage on mount (back navigation)
  useEffect(() => {
    const savedQ = sessionStorage.getItem("kupi-search-q");
    const savedResults = sessionStorage.getItem("kupi-search-results");
    if (savedQ) {
      setSearch(savedQ);
      lastSearchedRef.current = savedQ;
    }
    if (savedResults) {
      try { setSearchResults(JSON.parse(savedResults)); } catch { /* ignore */ }
    }
  }, []);

  // Clave estable de ubicación para dependencias de efectos
  const locationKey = `${location.lat}_${location.lng}`;
  const prevLocationRef = useRef(locationKey);

  // Limpiar resultados previos solo cuando la ubicación CAMBIA (no en mount)
  useEffect(() => {
    if (prevLocationRef.current === locationKey) return;
    prevLocationRef.current = locationKey;
    sessionStorage.removeItem("kupi-search-q");
    sessionStorage.removeItem("kupi-search-results");
    setSearchResults([]);
    setSearch("");
    setCategory("Todo");
    lastSearchedRef.current = "";
  }, [locationKey]);

  // Si una app no responde (sesión vencida, caída), avisarlo en vez de mostrar resultados incompletos
  const [platforms, setPlatforms] = useState<PlatformsStatus | null>(null);
  useEffect(() => {
    if (!hasLocation) return;
    fetchPlatformsStatus().then(setPlatforms);
  }, [locationKey, searchResults]);
  const downPlatforms = [platforms?.rappi.ok === false && "Rappi", platforms?.ubereats.ok === false && "Uber Eats"].filter(Boolean);

  // Ofertas de Rappi y Uber Eats en la zona (el backend las guarda 20 min por zona)
  const [offers, setOffers] = useState<OfferSection[]>([]);
  const [loadingOffers, setLoadingOffers] = useState(false);
  useEffect(() => {
    setOffers([]);
    if (!hasLocation) return;
    setLoadingOffers(true);
    fetchOffers(location.lat, location.lng)
      .then(setOffers)
      .catch(() => {})
      .finally(() => setLoadingOffers(false));
  }, [locationKey]);

  const filteredOffers = offers.filter((s) =>
    platformFilter === "all" || platformFilter === s.platform ||
    (platformFilter === "both" && s.items.some((i) => i.rappi_store_id && i.ubereats_store_id))
  ).map((s) =>
    platformFilter === "both" ? { ...s, items: s.items.filter((i) => i.rappi_store_id && i.ubereats_store_id) } : s
  );

  // Load popular restaurants on mount and when location changes
  useEffect(() => {
    setPopular([]);
    if (!hasLocation) { setLoadingPopular(false); return; }
    setLoadingPopular(true);
    fetchPopularRestaurants(location.lat, location.lng)
      .then(setPopular)
      .catch(() => {})
      .finally(() => setLoadingPopular(false));
  }, [locationKey]);


  // Debounced search with AbortController to cancel stale requests
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const q = search.trim();

    // Cancelar cualquier búsqueda anterior en vuelo
    if (abortRef.current) abortRef.current.abort();

    // Persist to sessionStorage
    if (q) {
      sessionStorage.setItem("kupi-search-q", q);
    } else {
      sessionStorage.removeItem("kupi-search-q");
      sessionStorage.removeItem("kupi-search-results");
      setSearchResults([]);
      setSearching(false);
      return;
    }

    // Skip API call if we already have results for this query (restored from session)
    if (q === lastSearchedRef.current && searchResults.length > 0) return;
    if (!hasLocation) return;

    setSearching(true);
    setSearchResults([]); // Limpiar resultados anteriores inmediatamente
    const controller = new AbortController();
    abortRef.current = controller;
    const timer = setTimeout(() => {
      lastSearchedRef.current = q;
      searchRestaurants(q, location.lat, location.lng)
        .then((results) => {
          if (controller.signal.aborted) return; // Ignorar si ya se canceló
          setSearchResults(results);
          sessionStorage.setItem("kupi-search-results", JSON.stringify(results));
        })
        .catch(() => { if (!controller.signal.aborted) setSearchResults([]); })
        .finally(() => { if (!controller.signal.aborted) setSearching(false); });
    }, 400);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [search, locationKey]);

  // Category click → trigger search
  const handleCategory = (cat: string) => {
    setCategory(cat);
    if (cat === "Todo") {
      setSearch("");
    } else {
      // Use the Spanish name for search (e.g. "Pizza", "Hamburguesas")
      setSearch(cat);
    }
  };

  const handleSearch = (q: string) => {
    setSearch(q);
    // Reset category when typing manually
    if (q.trim()) setCategory("Todo");
  };

  // Filter search results by platform
  const filteredSearch = useMemo(() => {
    return searchResults.filter((r) => {
      if (platformFilter === "both") return r.rappi_store_id && r.ubereats_store_id;
      if (platformFilter === "rappi") return !!r.rappi_store_id;
      if (platformFilter === "ubereats") return !!r.ubereats_store_id;
      return true;
    });
  }, [searchResults, platformFilter]);

  // Filter popular by platform
  const filteredPopular = useMemo(() => {
    return popular.filter((r) => {
      if (platformFilter === "both") return r.rappi_store_id && r.ubereats_store_id;
      if (platformFilter === "rappi") return !!r.rappi_store_id;
      if (platformFilter === "ubereats") return !!r.ubereats_store_id;
      return true;
    });
  }, [popular, platformFilter]);

  const isSearching = search.trim().length > 0;

  return (
    <div className="min-h-screen bg-[var(--bg)] transition-colors duration-300">
      <TopNav search={search} onSearch={handleSearch} />
      <main className="max-w-6xl mx-auto px-12 py-10">
        {/* Hero */}
        <div className="mb-8">
          <h1
            className="hero-title text-[26px] font-bold text-[var(--text-primary)] mb-2"
            style={{ fontFamily: "var(--font-display)" }}
          >
            {t.buscar.title}
          </h1>
          <p className="hero-subtitle text-[15px] text-[var(--text-secondary)]">
            {t.buscar.subtitle}
          </p>
        </div>

        {downPlatforms.length > 0 && (
          <div className="mb-6 p-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] text-[14px] text-[var(--text-primary)]">
            <span className="font-semibold">{downPlatforms.join(" y ")} no está respondiendo en este momento.</span>{" "}
            Mientras se restablece, solo verás resultados de {downPlatforms.length === 2 ? "ninguna app" : (downPlatforms[0] === "Rappi" ? "Uber Eats" : "Rappi")}.
          </div>
        )}

        {/* Banner: elige tu ubicación */}
        {!hasLocation && (
          <div className="mb-6 p-4 rounded-2xl border border-[var(--brand)] bg-[var(--brand-tint)] flex items-center gap-3">
            <span className="text-[20px]">📍</span>
            <p className="text-[14px] text-[var(--text-primary)]">
              <span className="font-semibold">Elige tu ubicación</span> en la barra de arriba para ver restaurantes cerca de ti
            </p>
          </div>
        )}

        {/* Platform filters */}
        <div className="flex gap-2 flex-wrap mb-4">
          {([
            { key: "all", label: "Todas" },
            { key: "both", label: "Rappi + Uber Eats" },
            { key: "rappi", label: "Rappi" },
            { key: "ubereats", label: "Uber Eats" },
          ] as const).map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setPlatformFilter(key)}
              className="text-[12px] font-semibold px-3 py-1.5 rounded-full border transition-colors"
              style={
                platformFilter === key
                  ? { background: "var(--brand)", color: "#fff", borderColor: "var(--brand)" }
                  : { background: "var(--surface)", color: "var(--text-secondary)", borderColor: "var(--border)" }
              }
            >
              {label}
            </button>
          ))}
        </div>

        {/* Categorías */}
        <div className="hero-chips mb-6">
          <CategoryChips selected={category} onSelect={handleCategory} />
        </div>

        {/* Search results / category results */}
        {isSearching ? (
          <>
            {searching ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] animate-pulse h-64"
                  />
                ))}
              </div>
            ) : filteredSearch.length > 0 ? (
              <div className="flex flex-col gap-6">
                {filteredSearch.map((r, i) => {
                  const hasR = !!r.rappi_store_id;
                  const hasUE = !!r.ubereats_store_id;
                  const products = r.matching_products || [];
                  const href = buildHref(r);
                  const closed = r.is_open === false;
                  return (
                    <div key={`${r.rappi_store_id}-${r.ubereats_store_id}-${i}`} className={`stagger-item ${closed ? "opacity-50" : ""}`} style={{ animationDelay: `${100 + i * 40}ms` }}>
                      {/* Restaurant header */}
                      {closed ? (
                        <div className="flex items-center gap-3 mb-3 cursor-default">
                          <div className="w-10 h-10 rounded-full bg-[var(--bg)] overflow-hidden shrink-0 border border-[var(--border)]">
                            {r.image_url ? (
                              <img src={proxyImage(r.image_url)} alt={r.restaurant_name} className="w-full h-full object-cover" />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center text-[10px] text-[var(--text-muted)]">?</div>
                            )}
                          </div>
                          <div className="min-w-0">
                            <h3 className="text-[15px] font-semibold text-[var(--text-primary)] truncate">{r.restaurant_name}</h3>
                            <div className="text-[12px] text-[var(--text-muted)]">No disponible ahora</div>
                          </div>
                        </div>
                      ) : (
                        <a href={href} className="flex items-center gap-3 mb-3 group">
                          <div className="w-10 h-10 rounded-full bg-[var(--bg)] overflow-hidden shrink-0 border border-[var(--border)]">
                            {r.image_url ? (
                              <img src={proxyImage(r.image_url)} alt={r.restaurant_name} className="w-full h-full object-cover" />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center text-[10px] text-[var(--text-muted)]">?</div>
                            )}
                          </div>
                          <div className="min-w-0">
                            <h3 className="text-[15px] font-semibold text-[var(--text-primary)] group-hover:text-[var(--brand)] transition-colors truncate">
                              {r.restaurant_name}
                            </h3>
                            <div className="flex items-center gap-2 text-[12px] text-[var(--text-muted)]">
                              {hasR && hasUE ? (
                                <span className="text-[var(--brand)] font-medium">Rappi · Uber Eats</span>
                              ) : hasR ? (
                                <span style={{ color: "#FF441F" }} className="font-medium">Rappi</span>
                              ) : (
                                <span style={{ color: "#06C167" }} className="font-medium">Uber Eats</span>
                              )}
                              {r.eta_preview && <><span>·</span><span>{r.eta_preview}</span></>}
                              {r.delivery_fee_preview && <><span>·</span><span>Envio {r.delivery_fee_preview}</span></>}
                            </div>
                          </div>
                        </a>
                      )}

                      {/* Matching products */}
                      {products.length > 0 ? (
                        <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide pl-[52px]">
                          {products.slice(0, 6).map((p, j) => {
                            const off = p.real_price && p.real_price > p.price ? Math.round((1 - p.price / p.real_price) * 100) : 0;
                            const cardInner = (
                              <>
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
                                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                                    />
                                  ) : (
                                    <div className="w-full h-full flex items-center justify-center text-[var(--text-muted)] text-[10px]">Sin imagen</div>
                                  )}
                                </div>
                                <div className="p-2">
                                  <p className="text-[12px] font-medium text-[var(--text-primary)] leading-tight line-clamp-2 mb-0.5">{p.name}</p>
                                  <p className="text-[13px] font-bold text-[var(--savings)]">
                                    ${p.price.toFixed(0)}
                                    {off > 0 && (
                                      <span className="ml-1 text-[11px] font-medium text-[var(--text-muted)] line-through">${p.real_price!.toFixed(0)}</span>
                                    )}
                                  </p>
                                </div>
                              </>
                            );
                            return closed ? (
                              <div key={`${p.product_id}-${j}`} className="shrink-0 w-36 bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden cursor-default">
                                {cardInner}
                              </div>
                            ) : (
                              <a key={`${p.product_id}-${j}`} href={href} className="shrink-0 w-36 bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden kupi-card">
                                {cardInner}
                              </a>
                            );
                          })}
                        </div>
                      ) : !closed ? (
                        <a href={href} className="pl-[52px] block">
                          <span className="text-[13px] text-[var(--text-muted)] hover:text-[var(--brand)] transition-colors">
                            Ver menu completo →
                          </span>
                        </a>
                      ) : null}

                      {/* Divider */}
                      {i < filteredSearch.length - 1 && (
                        <div className="border-b border-[var(--border)] mt-4" />
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="py-20 text-center">
                <p className="text-[15px] text-[var(--text-muted)]">
                  {t.buscar.noResults} <span className="text-[var(--text-primary)] font-medium">&quot;{search}&quot;</span>
                </p>
                <button
                  onClick={() => { setSearch(""); setCategory("Todo"); }}
                  className="mt-4 text-[13px] font-semibold text-[var(--brand)] underline"
                >
                  {t.buscar.seeAll}
                </button>
              </div>
            )}
          </>
        ) : (
          <>
            <OfferSections
              sections={filteredOffers}
              loading={loadingOffers}
              hrefFor={(item) => buildHref({ ...item, restaurant_name: item.store_name })}
            />

            {/* Popular restaurants section */}
            {filteredPopular.length > 0 && (
              <div className="mb-10">
                <h2
                  className="text-[18px] font-semibold text-[var(--text-primary)] mb-4"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  Restaurantes disponibles
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {filteredPopular.map((r, i) => {
                    const hasR = !!r.rappi_store_id;
                    const hasUE = !!r.ubereats_store_id;
                    return (
                      <div key={`pop-${r.rappi_store_id}-${r.ubereats_store_id}-${i}`} className="stagger-item" style={{ animationDelay: `${100 + i * 50}ms` }}>
                        <RestaurantCard
                          id={r.rappi_store_id || r.ubereats_store_id || `pop-${i}`}
                          name={r.restaurant_name}
                          cuisine={r.cuisine}
                          rating={0}
                          fromPrice={0}
                          platforms={hasR && hasUE ? 2 : 1}
                          imageUrl={r.image_url}
                          isOpen={r.is_open}
                          href={buildHref(r)}
                          hasRappi={hasR}
                          hasUberEats={hasUE}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {loadingPopular && (
              <div className="mb-10">
                <h2
                  className="text-[18px] font-semibold text-[var(--text-primary)] mb-4"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  Restaurantes disponibles
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div
                      key={i}
                      className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] animate-pulse h-64"
                    />
                  ))}
                </div>
                <p className="text-center text-[13px] text-[var(--text-muted)] mt-4 flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-[var(--brand)] border-t-transparent rounded-full animate-spin" />
                  Cargando restaurantes...
                </p>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
