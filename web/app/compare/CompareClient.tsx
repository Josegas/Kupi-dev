"use client";
import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, RefreshCw, MapPin, Search, Heart, Bell, LogOut, Plus, ShoppingCart } from "lucide-react";
import Link from "next/link";
import PlatformCompareCard from "../components/PlatformCompareCard";
import CTAButton from "../components/CTAButton";
import { compareProducts, compareCart, fetchCombinedMenu, proxyImage, QuoteResponse, CartQuoteResponse } from "../lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
import { RestaurantConfig } from "../lib/restaurants";
import { useLocation } from "../lib/location";
import { useLang } from "../lib/i18n";
import KupiLogo from "../components/KupiLogo";
import FavoriteButton from "../components/FavoriteButton";
import ThemeToggle from "../components/ThemeToggle";
import LanguageToggle from "../components/LanguageToggle";
import { useAuth } from "../lib/auth";
import { useCart } from "../lib/cart";
import CartBar from "../components/CartBar";

const _COMPLEMENT_RE = new RegExp(
  [
    "\\b\\d+\\s*ml\\b",
    "\\blat[a]?\\b",
    "\\blitros?\\b",
    "\\blts?\\b",
    "\\b(coca.?cola|pepsi|sprite|fanta|sidral|mundet|fuze|7up|manzanita|mirinda|peñafiel|squirt|boing|fresca)\\b",
    "\\b(refresco|limonada|jugo|bebida|changuirongo)\\b",
    "^\\s*(salsa|aderezo|dip|crazy sauce)\\b",
    "\\bdip\\b",                                     // dip en cualquier posición
    "\\bsalsas?\\s*$",
    "\\b(bbq|ranch|brava|cheesepe[ñn]o|mango.habanero)\\s*$",
    "\\bshot\\b",
    "\\b(kream|big kream)\\b",
    "\\b(sundae|mcflurry|malteada|helado|pay de|dona|donut|cake pop)\\b",
    "\\bbaitz\\b",
    "\\badicionales?\\b",
    "\\b(puré de papa|papas?\\s+(gajo|francesas?|a\\s+la\\s+francesa|fritas?|medianas?|grandes?|pequeñas?))\\b",
    "\\b(ensalada de col|coleslaw)\\b",
    "\\bsobre\\s+(huntrix|saja)\\b",
    "\\bfrijol(es)?\\b",
    "\\b(cheesy\\s*bread|papotas)\\b",
    "\\b(crazy\\s*bread|canela\\s*stix)\\b",
    "\\bté\\s+de\\s+la\\s+casa\\b",
    "extra\\s*$",
    "ingrediente\\s+extra",                          // "Ingrediente Extra para Rollo"
    "\\btogarashi\\b",                               // condimento Sushi City
    "\\bquepapas?\\b",                               // snack Pizza Hut
    "\\b(agua ciel|agua purificada)\\b",
    "^agua\\s",
    "^tortilla[s]?\\s",                              // toda tortilla suelta
    "^guacamole\\b",                                 // guacamole como dip
    "^queso\\s*$",                                   // "Queso" solo = dip, no "Pizza de Queso"
  ].join("|"),
  "i"
);

function isComplement(name: string): boolean {
  return _COMPLEMENT_RE.test(name.trim());
}

interface Props {
  restaurant: RestaurantConfig;
}

type Step = "selecting" | "comparing" | "comparing-cart" | "exclusive";

interface ListProduct {
  name: string;
  description?: string;
  price: number;
  real_price?: number;  // precio sin oferta; si es mayor que price, hay oferta
  price_platform?: "rappi" | "ubereats";  // app con el precio más bajo, en productos de ambas apps
  image_url: string;
  rappi_product_id?: string;
  ubereats_product_id?: string;
  didi_product_id?: string | null;
  exclusivePlatform?: "rappi" | "ubereats";
}

/** Descuento en % (0 si no hay oferta). */
function discountPct(p: { price: number; real_price?: number }): number {
  return p.real_price && p.real_price > p.price ? Math.round((1 - p.price / p.real_price) * 100) : 0;
}

export default function CompareClient({ restaurant }: Props) {
  const { location, hasLocation } = useLocation();
  const { t } = useLang();
  const { user, session, signOut } = useAuth();
  const { items: cartItems, addItem: addToCart, clearCart, canAdd, itemCount: cartCount } = useCart();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const searchParams = useSearchParams();
  const preselectRappi = searchParams.get("r");
  const preselectUE = searchParams.get("u");
  const fromParam = searchParams.get("from"); // "fav" si viene de favoritos
  const hasPreselect = preselectRappi !== null || preselectUE !== null;
  const fromDeals = hasPreselect && fromParam !== "fav";
  const fromFavorites = fromParam === "fav";
  const autoSelectedRef = useRef(false);

  // — Paso 1: selección de producto —
  // Si vienen parámetros de preselección, saltar directo a comparación
  const [step, setStep] = useState<Step>((fromDeals || fromFavorites) ? "comparing" : "selecting");
  const [allProducts, setAllProducts] = useState<ListProduct[]>([]);
  const [loadingMenu, setLoadingMenu] = useState(true);
  const [menuError, setMenuError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [platformFilter, setPlatformFilter] = useState<"all" | "both" | "rappi" | "ubereats">("all");
  const [selectedProduct, setSelectedProduct] = useState<ListProduct | null>(null);

  // — Favoritos del usuario (para resaltar y ordenar) —
  const [favProductIds, setFavProductIds] = useState<Set<string>>(new Set());
  const [showFavOnly, setShowFavOnly] = useState(false);
  const [availablePlatforms, setAvailablePlatforms] = useState<{ rappi: boolean; ubereats: boolean }>({ rappi: !!restaurant.rappi_store_id, ubereats: !!restaurant.ubereats_store_id });

  useEffect(() => {
    if (!user || !session) return;
    fetch(`${API_URL}/favorites`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then((r) => r.ok ? r.json() : [])
      .then((favs: { rappi_product_id?: string; ubereats_product_id?: string }[]) => {
        const ids = new Set<string>();
        for (const f of favs) {
          if (f.rappi_product_id) ids.add(f.rappi_product_id);
          if (f.ubereats_product_id) ids.add(f.ubereats_product_id);
        }
        setFavProductIds(ids);
      })
      .catch(() => {});
  }, [user, session]);

  const isFavorite = (p: ListProduct) =>
    (p.rappi_product_id && favProductIds.has(p.rappi_product_id)) ||
    (p.ubereats_product_id && favProductIds.has(p.ubereats_product_id));

  // — Paso 2: comparación de precios —
  const [quotes, setQuotes] = useState<QuoteResponse[]>([]);
  const [loadingQuotes, setLoadingQuotes] = useState(hasPreselect);
  const [quotesError, setQuotesError] = useState<string | null>(null);
  const [selectedQuote, setSelectedQuote] = useState<QuoteResponse | null>(null);

  // — Carrito multi-producto —
  const [cartQuotes, setCartQuotes] = useState<CartQuoteResponse[]>([]);
  const [loadingCart, setLoadingCart] = useState(false);
  const [cartError, setCartError] = useState<string | null>(null);
  const [selectedCartQuote, setSelectedCartQuote] = useState<CartQuoteResponse | null>(null);

  const loadMenu = () => {
    setLoadingMenu(true);
    setMenuError(null);
    fetchCombinedMenu(
      restaurant.rappi_store_id,
      restaurant.ubereats_store_id,
      location.lat,
      location.lng,
    )
      .then((data) => {
        const matched: ListProduct[] = data.products.map((p) => ({ ...p }));
        const exclusive: ListProduct[] = [
          ...data.only_rappi.map((p) => ({ ...p, exclusivePlatform: "rappi" as const })),
          ...data.only_ubereats.map((p) => ({ ...p, exclusivePlatform: "ubereats" as const })),
        ];
        // Detectar qué plataformas realmente tienen productos
        const hasRappi = matched.some((p) => p.rappi_product_id) || data.only_rappi.length > 0;
        const hasUber = matched.some((p) => p.ubereats_product_id) || data.only_ubereats.length > 0;
        setAvailablePlatforms({ rappi: hasRappi, ubereats: hasUber });
        const merged = [...matched, ...exclusive].sort((a, b) => {
          // 0. Favoritos primero
          const aFav = isFavorite(a) ? 0 : 1;
          const bFav = isFavorite(b) ? 0 : 1;
          if (aFav !== bFav) return aFav - bFav;
          // 1. Ofertas primero, de mayor a menor descuento
          const aOff = discountPct(a);
          const bOff = discountPct(b);
          if (aOff !== bOff) return bOff - aOff;
          // 2. Productos con imagen primero
          const aImg = a.image_url ? 0 : 1;
          const bImg = b.image_url ? 0 : 1;
          if (aImg !== bImg) return aImg - bImg;
          // 3. Complementos al final
          const aComp = isComplement(a.name);
          const bComp = isComplement(b.name);
          if (aComp !== bComp) return aComp ? 1 : -1;
          // 4. Por precio
          return a.price - b.price;
        });
        setAllProducts(merged);
      })
      .catch((e) => setMenuError(e.message))
      .finally(() => setLoadingMenu(false));
  };

  useEffect(() => {
    if (!hasLocation) return;
    loadMenu();
    autoSelectedRef.current = false;
  }, [restaurant, location, hasLocation]);

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

  const handleSelectProduct = (product: ListProduct) => {
    setSelectedProduct(product);
    setStep("comparing");
    setQuotes([]);
    setQuotesError(null);
    setLoadingQuotes(true);
    compareProducts({
      rappi_store_id: restaurant.rappi_store_id,
      ubereats_store_id: restaurant.ubereats_store_id,
      rappi_product_id: product.rappi_product_id ?? "none",
      ubereats_product_id: product.ubereats_product_id ?? "none",
      lat: location.lat,
      lng: location.lng,
    })
      .then((data) => {
        const sorted = [...data].sort((a, b) => a.total - b.total);
        setQuotes(sorted);
        setSelectedQuote(sorted[0] ?? null);
      })
      .catch((e) => setQuotesError(e.message))
      .finally(() => setLoadingQuotes(false));
  };

  const handleCompareCart = () => {
    if (cartItems.length === 0) return;
    setStep("comparing-cart");
    setCartQuotes([]);
    setCartError(null);
    setLoadingCart(true);
    compareCart({
      rappi_store_id: restaurant.rappi_store_id,
      ubereats_store_id: restaurant.ubereats_store_id,
      items: cartItems.map((item) => ({
          rappi_product_id: item.rappi_product_id || undefined,
          ubereats_product_id: item.ubereats_product_id || undefined,
        })),
      lat: location.lat,
      lng: location.lng,
    })
      .then((data) => {
        const sorted = [...data].sort((a, b) => a.total - b.total);
        setCartQuotes(sorted);
        setSelectedCartQuote(sorted[0] ?? null);
      })
      .catch((e) => setCartError(e.message))
      .finally(() => setLoadingCart(false));
  };

  // Auto-seleccionar producto si viene de /deals con ?r=...&u=...
  useEffect(() => {
    if (!preselectRappi && !preselectUE) return;
    if (loadingMenu || autoSelectedRef.current) return;
    if (allProducts.length === 0) return;

    const match = allProducts.find(
      (p) =>
        (preselectRappi && p.rappi_product_id === preselectRappi) ||
        (preselectUE && p.ubereats_product_id === preselectUE),
    );
    if (match) {
      autoSelectedRef.current = true;
      handleSelectProduct(match);
    }
  }, [allProducts, loadingMenu]);

  const filteredProducts = allProducts.filter((p) => {
    const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase());
    const matchesPlatform =
      platformFilter === "all" ||
      (platformFilter === "both" && !p.exclusivePlatform) ||
      (platformFilter === "rappi" && p.exclusivePlatform === "rappi") ||
      (platformFilter === "ubereats" && p.exclusivePlatform === "ubereats");
    const matchesFav = !showFavOnly || isFavorite(p);
    return matchesSearch && matchesPlatform && matchesFav;
  });

  const platformCounts = {
    all: allProducts.length,
    both: allProducts.filter((p) => !p.exclusivePlatform).length,
    rappi: allProducts.filter((p) => p.exclusivePlatform === "rappi").length,
    ubereats: allProducts.filter((p) => p.exclusivePlatform === "ubereats").length,
  };
  const showPlatformFilters = availablePlatforms.rappi && availablePlatforms.ubereats;

  const cheapest = quotes[0] ?? null;

  // ── Header compartido ──────────────────────────────────────────────
  const Header = (
    <div className="bg-[var(--surface)] border-b border-[var(--border)] sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-12 h-16 flex items-center gap-4">
        {/* Flecha atrás */}
        {step === "comparing" ? (
          fromDeals ? (
            <Link href="/deals" className="kupi-link text-[var(--text-secondary)] transition-colors shrink-0">
              <ArrowLeft size={20} />
            </Link>
          ) : (
            <button
              onClick={() => setStep("selecting")}
              className="kupi-link text-[var(--text-secondary)] transition-colors shrink-0"
            >
              <ArrowLeft size={20} />
            </button>
          )
        ) : step === "comparing-cart" ? (
          <button
            onClick={() => setStep("selecting")}
            className="kupi-link text-[var(--text-secondary)] transition-colors shrink-0"
          >
            <ArrowLeft size={20} />
          </button>
        ) : (
          <Link href={fromFavorites ? "/favoritos" : "/buscar"} className="kupi-link text-[var(--text-secondary)] transition-colors shrink-0">
            <ArrowLeft size={20} />
          </Link>
        )}

        {/* Logo — link a inicio */}
        <Link href="/buscar" className="shrink-0">
          <KupiLogo size={110} imageSrc="/Kupilogo6.png" />
        </Link>

        {/* Separador */}
        <div className="w-px h-6 bg-[var(--border)] shrink-0" />

        {/* Restaurante */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className="text-[16px] font-semibold text-[var(--text-primary)] truncate"
              style={{ fontFamily: "var(--font-display)" }}
            >
              {restaurant.name}
            </span>
            <div className="flex items-center gap-1 shrink-0">
              {availablePlatforms.rappi && (
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full" style={{ background: "#FF441F22", color: "#FF441F" }}>Rappi</span>
              )}
              {availablePlatforms.ubereats && (
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full" style={{ background: "#06C16722", color: "#06C167" }}>Uber Eats</span>
              )}
            </div>
          </div>
          <p className="text-[12px] text-[var(--text-muted)] flex items-center gap-1 mt-0.5">
            <MapPin size={11} className="text-[var(--brand)] shrink-0" />
            <span className="truncate">{location.label}</span>
          </p>
        </div>

        {/* Idioma y tema */}
        <LanguageToggle />
        <ThemeToggle />

        {/* Auth */}
        {user ? (
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
                <Link
                  href="/favoritos"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-2 px-4 py-2.5 text-[13px] text-[var(--text-primary)] hover:bg-[var(--bg)] transition-colors"
                >
                  <Heart size={14} />
                  {t.auth.myFavorites}
                </Link>
                <Link
                  href="/favoritos"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-2 px-4 py-2.5 text-[13px] text-[var(--text-primary)] hover:bg-[var(--bg)] transition-colors"
                >
                  <Bell size={14} />
                  {t.auth.myAlerts}
                </Link>
                <button
                  onClick={() => { signOut(); setUserMenuOpen(false); }}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-[13px] text-red-500 hover:bg-[var(--bg)] transition-colors border-t border-[var(--border)]"
                >
                  <LogOut size={14} />
                  {t.auth.signOut}
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link
            href="/login"
            className="shrink-0 text-[13px] font-semibold text-white bg-[var(--brand)] px-4 py-1.5 rounded-full hover:brightness-110 transition-all"
          >
            {t.auth.signIn}
          </Link>
        )}
      </div>
    </div>
  );

  // ── Paso 1: selección de producto ──────────────────────────────────
  if (step === "selecting") {
    return (
      <div className={`min-h-screen bg-[var(--bg)] ${cartCount > 0 ? "pb-24" : ""}`}>
        {Header}
        <div className="compare-step max-w-5xl mx-auto px-6 py-8">

          <h2
            className="text-[18px] font-semibold text-[var(--text-primary)] mb-1"
            style={{ fontFamily: "var(--font-display)" }}
          >
            {t.compare.selectTitle}
          </h2>
          <p className="text-[13px] text-[var(--text-muted)] mb-6">
            {!loadingMenu && availablePlatforms.rappi !== availablePlatforms.ubereats
              ? t.compare.selectSubtitleSingle.replace(
                  "{platform}",
                  availablePlatforms.rappi ? "Rappi" : "Uber Eats",
                )
              : t.compare.selectSubtitle}
          </p>

          {/* Filtros de plataforma */}
          {!loadingMenu && !menuError && allProducts.length > 0 && (showPlatformFilters || (user && favProductIds.size > 0)) && (
            <div className="flex gap-2 flex-wrap mb-4">
              {showPlatformFilters && ([
                { key: "all",      label: "Todo" },
                { key: "both",     label: "Ambas apps" },
                { key: "rappi",    label: "Solo Rappi" },
                { key: "ubereats", label: "Solo Uber Eats" },
              ] as const).filter(({ key }) => platformCounts[key] > 0).map(({ key, label }) => (
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
              {/* Filtro de favoritos */}
              {user && favProductIds.size > 0 && (
                <button
                  onClick={() => setShowFavOnly(!showFavOnly)}
                  className="text-[12px] font-semibold px-3 py-1.5 rounded-full border transition-colors flex items-center gap-1"
                  style={
                    showFavOnly
                      ? { background: "var(--brand)", color: "#fff", borderColor: "var(--brand)" }
                      : { background: "var(--surface)", color: "var(--text-secondary)", borderColor: "var(--border)" }
                  }
                >
                  <Heart size={11} /> Favoritos
                </button>
              )}
            </div>
          )}

          {/* Buscador */}
          {!loadingMenu && !menuError && allProducts.length > 0 && (
            <div className="kupi-input flex items-center gap-2 bg-[var(--surface)] border border-[var(--border)] rounded-xl px-4 py-2.5 mb-5 transition-all">
              <Search size={15} className="text-[var(--text-muted)] shrink-0" />
              <input
                type="text"
                placeholder={t.compare.searchPlaceholder}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 bg-transparent text-[14px] text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none"
              />
            </div>
          )}

          {/* Loading */}
          {loadingMenu && (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="rounded-xl bg-[var(--surface)] border border-[var(--border)] animate-pulse aspect-[3/4]"
                />
              ))}
            </div>
          )}

          {/* Error */}
          {!loadingMenu && menuError && (
            <div className="rounded-2xl border border-red-200 bg-red-50 dark:bg-red-900/10 p-6 text-center">
              <p className="text-[14px] text-red-600 dark:text-red-400 mb-3">{menuError}</p>
              <button
                onClick={loadMenu}
                className="text-[13px] font-semibold text-[var(--brand)] underline"
              >
                {t.compare.retry}
              </button>
            </div>
          )}

          {/* Grid de productos */}
          {!loadingMenu && !menuError && (
            <>
              {filteredProducts.length === 0 && (
                <p className="text-[14px] text-[var(--text-muted)] text-center py-8">
                  {search ? t.compare.noSearchResults : t.compare.noProducts}
                </p>
              )}
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                {filteredProducts.map((p, i) => {
                  const PLATFORM_COLORS: Record<string, string> = { rappi: "#FF441F", ubereats: "#06C167" };
                  const PLATFORM_LABELS: Record<string, string> = { rappi: "Rappi", ubereats: "Uber Eats" };
                  return (
                    <div
                      key={p.rappi_product_id ?? p.ubereats_product_id}
                      role="button"
                      tabIndex={0}
                      onClick={() => handleSelectProduct(p)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") handleSelectProduct(p); }}
                      className={`kupi-card cursor-pointer text-left bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden hover:border-[var(--brand)]${!search ? " stagger-product" : ""}`}
                      style={!search ? { animationDelay: `${Math.min(i * 30, 300)}ms` } : undefined}
                    >
                      {/* Imagen */}
                      <div className="w-full aspect-square bg-[var(--bg)] overflow-hidden">
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
                          <div className="w-full h-full flex items-center justify-center text-[var(--text-muted)] text-xs">Sin imagen</div>
                        )}
                      </div>
                      {/* Info */}
                      <div className="p-3">
                        <p className="text-[13px] font-semibold text-[var(--text-primary)] leading-tight line-clamp-2 mb-1">{p.name}</p>
                        {p.exclusivePlatform && showPlatformFilters && (
                          <span
                            className="inline-block text-[10px] font-bold px-1.5 py-0.5 rounded-full mb-1"
                            style={{ background: PLATFORM_COLORS[p.exclusivePlatform] + "22", color: PLATFORM_COLORS[p.exclusivePlatform] }}
                          >
                            Solo {PLATFORM_LABELS[p.exclusivePlatform]}
                          </span>
                        )}
                        {discountPct(p) > 0 && (
                          <span className="inline-block text-[10px] font-bold px-1.5 py-0.5 rounded-full mb-1 bg-[var(--savings-tint)] text-[var(--savings)]">
                            -{discountPct(p)}%
                            {(p.price_platform ?? p.exclusivePlatform) && ` en ${PLATFORM_LABELS[(p.price_platform ?? p.exclusivePlatform)!]}`}
                          </span>
                        )}
                        <div className="flex items-center justify-between">
                          <p className="text-[14px] font-bold text-[var(--savings)]">
                            ${p.price.toFixed(0)}
                            {discountPct(p) > 0 && (
                              <span className="ml-1.5 text-[12px] font-medium text-[var(--text-muted)] line-through">${p.real_price!.toFixed(0)}</span>
                            )}
                          </p>
                          <div className="flex items-center gap-1">
                            {/* Botón agregar al carrito */}
                            {(() => {
                              const cartItem = {
                                name: p.name,
                                price: p.price,
                                image_url: p.image_url,
                                rappi_product_id: p.rappi_product_id,
                                ubereats_product_id: p.ubereats_product_id,
                              };
                              const allowed = canAdd(cartItem);
                              return (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    addToCart(cartItem);
                                  }}
                                  disabled={!allowed}
                                  className={`w-7 h-7 rounded-full flex items-center justify-center transition-colors ${
                                    allowed
                                      ? "bg-[var(--brand-tint)] hover:bg-[var(--brand)] hover:text-white text-[var(--brand)]"
                                      : "bg-[var(--border)] text-[var(--text-muted)] cursor-not-allowed opacity-50"
                                  }`}
                                  title={allowed ? "Agregar al carrito" : "No compatible con el carrito actual"}
                                >
                                  <Plus size={14} />
                                </button>
                              );
                            })()}
                            <FavoriteButton
                              productName={p.name}
                              restaurantName={restaurant.name}
                              rappiProductId={p.rappi_product_id}
                              ubereatsProductId={p.ubereats_product_id}
                              rappiStoreId={restaurant.rappi_store_id}
                              ubereatsStoreId={restaurant.ubereats_store_id}
                              imageUrl={p.image_url}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* Barra de carrito */}
        <CartBar onCompare={handleCompareCart} loading={loadingCart} />
      </div>
    );
  }

  // ── Paso 3: comparación de carrito multi-producto ──────────────────
  if (step === "comparing-cart") {
    const cartCheapest = cartQuotes[0] ?? null;
    return (
      <div className="min-h-screen bg-[var(--bg)] pb-28">
        {Header}

        <div className="compare-step max-w-6xl mx-auto px-12 py-10">
          <div className="flex flex-col lg:flex-row gap-10">

            {/* Panel izquierdo: resumen del carrito */}
            <div className="lg:w-72 shrink-0">
              <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl overflow-hidden p-5">
                <div className="flex items-center gap-2 mb-4">
                  <ShoppingCart size={18} className="text-[var(--brand)]" />
                  <h2 className="text-[16px] font-bold text-[var(--text-primary)]">
                    {t.cart.title} ({cartItems.length})
                  </h2>
                </div>
                <div className="space-y-2">
                  {cartItems.map((item, i) => (
                    <div key={i} className="flex items-center justify-between text-[13px]">
                      <span className="text-[var(--text-primary)] truncate flex-1 mr-2">{item.name}</span>
                      <span className="text-[var(--text-secondary)] font-medium whitespace-nowrap">${item.price.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t border-[var(--border)] flex justify-between text-[14px] font-bold">
                  <span className="text-[var(--text-primary)]">{t.cart.subtotal}</span>
                  <span className="text-[var(--savings)]">
                    ${cartItems.reduce((s, i) => s + i.price, 0).toFixed(2)}
                  </span>
                </div>
                <p className="text-[11px] text-[var(--text-muted)] mt-2">
                  {t.cart.cartNote}
                </p>
              </div>
            </div>

            {/* Panel derecho: comparación */}
            <div className="flex-1">
              <div className="flex items-center justify-between mb-5">
                <h3
                  className="text-[16px] font-semibold text-[var(--text-secondary)]"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {t.cart.cartTotal}
                </h3>
                {!loadingCart && (
                  <button
                    onClick={handleCompareCart}
                    className="flex items-center gap-1.5 text-[13px] text-[var(--text-muted)] hover:text-[var(--brand)] transition-colors kupi-link"
                  >
                    <RefreshCw size={13} />
                    {t.cart.update}
                  </button>
                )}
              </div>

              {/* Loading */}
              {loadingCart && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[{ name: "Rappi", color: "#FF441F" }, { name: "Uber Eats", color: "#06C167" }].map((p) => (
                    <div
                      key={p.name}
                      className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 flex flex-col gap-4"
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ background: p.color }} />
                        <span className="text-[15px] font-semibold text-[var(--text-primary)]">{p.name}</span>
                      </div>
                      <div className="h-8 w-28 rounded-lg bg-[var(--bg)] animate-pulse" />
                      <div className="flex flex-col gap-2 pt-1 border-t border-[var(--border)]">
                        {[80, 60, 48].map((w, i) => (
                          <div key={i} className="h-3 rounded-full bg-[var(--bg)] animate-pulse" style={{ width: `${w}%` }} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Error */}
              {!loadingCart && cartError && (
                <div className="rounded-2xl border border-red-200 bg-red-50 dark:bg-red-900/10 p-6 text-center">
                  <p className="text-[14px] text-red-600 dark:text-red-400 mb-3">{cartError}</p>
                  <button
                    onClick={handleCompareCart}
                    className="text-[13px] font-semibold text-[var(--brand)] underline"
                  >
                    {t.cart.retry}
                  </button>
                </div>
              )}

              {/* Resultados */}
              {!loadingCart && !cartError && cartQuotes.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {cartQuotes.map((q, i) => (
                    <PlatformCompareCard
                      key={q.platform}
                      platform={q.platform}
                      productPrice={q.product_price}
                      deliveryFee={q.delivery_fee}
                      serviceFee={q.service_fee}
                      total={q.total}
                      storeName={q.store_name}
                      storeAddress={q.store_address}
                      isCheapest={cartQuotes.length > 1 && cartCheapest !== null && q.platform === cartCheapest.platform}
                      cardIndex={i}
                      isOpen={q.is_open}
                      opensAt={q.opens_at || undefined}
                      isEstimate={q.is_estimate}
                      itemCount={cartItems.length}
                      onSelect={() => setSelectedCartQuote(q)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {selectedCartQuote && (
          <CTAButton
            platform={selectedCartQuote.platform}
            total={selectedCartQuote.total}
            href={selectedCartQuote.deep_link}
          />
        )}
      </div>
    );
  }

  // ── Paso 2: comparación de precios ─────────────────────────────────
  return (
    <div className="min-h-screen bg-[var(--bg)] pb-28">
      {Header}

      <div className="compare-step max-w-6xl mx-auto px-12 py-10">
        <div className="flex flex-col lg:flex-row gap-10">

          {/* Panel izquierdo: producto seleccionado */}
          <div className="lg:w-72 shrink-0">
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl overflow-hidden">
              <div className="h-48 bg-[var(--bg)] relative">
                {selectedProduct?.image_url ? (
                  <img
                    src={proxyImage(selectedProduct.image_url)}
                    alt={selectedProduct.name}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      const img = e.target as HTMLImageElement;
                      if (img.src !== selectedProduct.image_url) {
                        img.src = selectedProduct.image_url;
                      } else {
                        img.style.display = "none";
                      }
                    }}
                  />
                ) : restaurant.imageUrl ? (
                  <img
                    src={restaurant.imageUrl}
                    alt={restaurant.name}
                    className="w-full h-full object-cover opacity-30"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-[var(--text-muted)] text-sm">
                    {t.compare.noImage}
                  </div>
                )}
              </div>
              <div className="p-5">
                <h2 className="text-[18px] font-bold text-[var(--text-primary)] mb-1">
                  {selectedProduct?.name}
                </h2>
                {selectedProduct?.description && (
                  <p className="text-[14px] text-[var(--text-secondary)] leading-relaxed">
                    {selectedProduct.description}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Panel derecho: comparación */}
          <div className="flex-1">
            <div className="flex items-center justify-between mb-5">
              <h3
                className="text-[16px] font-semibold text-[var(--text-secondary)]"
                style={{ fontFamily: "var(--font-display)" }}
              >
                {t.compare.priceTitle}
              </h3>
              {!loadingQuotes && (
                <button
                  onClick={() => selectedProduct && handleSelectProduct(selectedProduct)}
                  className="flex items-center gap-1.5 text-[13px] text-[var(--text-muted)] hover:text-[var(--brand)] transition-colors kupi-link"
                >
                  <RefreshCw size={13} />
                  {t.compare.refresh}
                </button>
              )}
            </div>

            {/* Carga */}
            {loadingQuotes && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {(selectedProduct?.exclusivePlatform === "rappi"
                  ? [{ name: "Rappi", color: "#FF441F" }]
                  : selectedProduct?.exclusivePlatform === "ubereats"
                  ? [{ name: "Uber Eats", color: "#06C167" }]
                  : [
                      ...(selectedProduct?.rappi_product_id ? [{ name: "Rappi", color: "#FF441F" }] : []),
                      ...(selectedProduct?.ubereats_product_id ? [{ name: "Uber Eats", color: "#06C167" }] : []),
                      ...(!selectedProduct?.rappi_product_id && !selectedProduct?.ubereats_product_id
                        ? [{ name: "Rappi", color: "#FF441F" }, { name: "Uber Eats", color: "#06C167" }]
                        : []),
                    ]
                ).map((p) => (
                  <div
                    key={p.name}
                    className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 flex flex-col gap-4"
                  >
                    {/* Header visible con branding de la plataforma */}
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2.5 h-2.5 rounded-full animate-pulse"
                        style={{ background: p.color }}
                      />
                      <span className="text-[15px] font-semibold text-[var(--text-primary)]">
                        {p.name}
                      </span>
                    </div>

                    {/* Precio grande en placeholder */}
                    <div className="flex items-end gap-1">
                      <div className="h-8 w-28 rounded-lg bg-[var(--bg)] animate-pulse" />
                    </div>

                    {/* Líneas de desglose */}
                    <div className="flex flex-col gap-2 pt-1 border-t border-[var(--border)]">
                      {[80, 60, 48].map((w, i) => (
                        <div
                          key={i}
                          className="h-3 rounded-full bg-[var(--bg)] animate-pulse"
                          style={{ width: `${w}%`, animationDelay: `${i * 120}ms` }}
                        />
                      ))}
                    </div>

                    {/* Status */}
                    <p className="text-[11px] text-[var(--text-muted)] flex items-center gap-1.5">
                      <span
                        className="inline-block w-1.5 h-1.5 rounded-full animate-pulse"
                        style={{ background: p.color, animationDuration: "1s" }}
                      />
                      {t.compare.checking}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {/* Error */}
            {!loadingQuotes && quotesError && (
              <div className="rounded-2xl border border-red-200 bg-red-50 dark:bg-red-900/10 p-6 text-center">
                <p className="text-[14px] text-red-600 dark:text-red-400 mb-3">{quotesError}</p>
                <button
                  onClick={() => selectedProduct && handleSelectProduct(selectedProduct)}
                  className="text-[13px] font-semibold text-[var(--brand)] underline"
                >
                  {t.compare.retry}
                </button>
              </div>
            )}

            {/* Aviso producto exclusivo */}
            {!loadingQuotes && !quotesError && quotes.length === 1 && selectedProduct?.exclusivePlatform && (
              <div className="mb-4 px-4 py-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] text-[13px] text-[var(--text-secondary)]">
                Este producto solo está disponible en{" "}
                <span className="font-semibold text-[var(--text-primary)]">
                  {{ rappi: "Rappi", ubereats: "Uber Eats" }[selectedProduct.exclusivePlatform]}
                </span>
                , por lo que no se puede comparar con otras plataformas.
              </div>
            )}

            {/* Resultados */}
            {!loadingQuotes && !quotesError && quotes.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {quotes.map((q, i) => (
                  <PlatformCompareCard
                    key={q.platform}
                    platform={q.platform}
                    productPrice={q.product_price}
                    deliveryFee={q.delivery_fee}
                    serviceFee={q.service_fee}
                    total={q.total}
                    etaMinutes={q.eta_minutes ?? undefined}
                    storeName={q.store_name}
                    storeAddress={q.store_address}
                    isCheapest={quotes.length > 1 && cheapest !== null && q.platform === cheapest.platform}
                    approximate={q.platform === "ubereats"}
                    cardIndex={i}
                    variantLabel={q.variant_label || undefined}
                    isOpen={q.is_open}
                    opensAt={q.opens_at || undefined}
                    isEstimate={q.is_estimate}
                    onSelect={() => setSelectedQuote(q)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {selectedQuote && (
        <CTAButton
          platform={selectedQuote.platform}
          total={selectedQuote.total}
          href={selectedQuote.deep_link}
        />
      )}
    </div>
  );
}
