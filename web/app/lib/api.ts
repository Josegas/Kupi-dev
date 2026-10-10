const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function proxyImage(url: string): string {
  if (!url) return "";
  // CDNs públicos — servir directo sin proxy (mucho más rápido)
  if (url.includes("supabase.co/storage/")) return url;
  if (url.includes("images.rappi.com")) return url;
  if (url.includes("tb-static.uber.com")) return url;
  if (url.includes("uber.com/prod/image")) return url;
  if (url.includes("cloudfront.net")) return url;
  // Solo proxear URLs desconocidas que podrían tener restricciones
  return `${API_URL}/proxy/image?url=${encodeURIComponent(url)}`;
}

export interface QuoteResponse {
  platform: string;
  product_price: number;
  delivery_fee: number | null; // null en DiDi (solo disponible en la app)
  service_fee: number | null;  // null en DiDi (solo disponible en la app)
  total: number;
  currency: string;
  eta_minutes: number | null;
  deep_link: string;
  store_name: string;
  store_address: string;
  variant_label: string;
  is_open: boolean;
  opens_at: string;
  is_estimate: boolean;
}

export interface CompareRequest {
  rappi_store_id: string;
  ubereats_store_id: string;
  rappi_product_id: string;
  ubereats_product_id: string;
  lat?: number;
  lng?: number;
  // DiDi es opcional: omitir si la sucursal no está en el catálogo
  didi_store_id?: string | null;
  didi_product_id?: string | null;
}

export interface CombinedProduct {
  name: string;
  description: string;
  price: number;
  real_price?: number;
  price_platform?: "rappi" | "ubereats";  // app con el precio más bajo (price)
  image_url: string;
  rappi_product_id: string;
  ubereats_product_id: string;
  didi_product_id?: string | null;
}

export interface ExclusiveProduct {
  name: string;
  description: string;
  price: number;
  real_price?: number;
  image_url: string;
  platform: "rappi" | "ubereats";
  rappi_product_id?: string;
  ubereats_product_id?: string;
}

export interface CombinedMenuResponse {
  products: CombinedProduct[];
  only_rappi: ExclusiveProduct[];
  only_ubereats: ExclusiveProduct[];
}

function parseDetail(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => (typeof d?.msg === "string" ? d.msg : JSON.stringify(d)));
    return msgs.join(", ");
  }
  if (detail && typeof detail === "object") {
    const obj = detail as Record<string, unknown>;
    if (Array.isArray(obj.errors) && obj.errors.length > 0) {
      return "Este restaurante no está disponible en este momento.";
    }
    return JSON.stringify(detail);
  }
  return `Error ${status}`;
}

export interface DealProduct {
  name: string;
  price: number;          // precio de menú más bajo entre las dos apps (con oferta, si hay)
  real_price?: number;    // precio sin oferta
  price_platform?: "rappi" | "ubereats";
  image_url: string;
  restaurant_name: string;
  category: string;
  rappi_store_id: string;
  ubereats_store_id: string;
  rappi_product_id: string;
  ubereats_product_id: string;
}

export async function fetchDeals(category: string, lat: number, lng: number, maxPrice = 100): Promise<DealProduct[]> {
  const params = new URLSearchParams({ category, lat: String(lat), lng: String(lng), max_price: String(maxPrice) });
  const res = await fetch(`${API_URL}/products/deals?${params}`);
  if (!res.ok) return [];
  return res.json();
}

export async function fetchStoresStatus(
  rappiStoreIds: string[],
  ueStoreIds: string[],
  lat?: number,
  lng?: number,
): Promise<Record<string, { is_open: boolean }>> {
  const params = new URLSearchParams({
    rappi_store_ids: rappiStoreIds.join(","),
    ue_store_ids: ueStoreIds.join(","),
  });
  if (lat !== undefined) params.set("lat", String(lat));
  if (lng !== undefined) params.set("lng", String(lng));
  const res = await fetch(`${API_URL}/stores/status?${params}`);
  if (!res.ok) return {};
  return res.json();
}

export async function fetchCombinedMenu(
  rappi_store_id: string,
  ubereats_store_id: string,
  lat?: number,
  lng?: number,
  didi_store_id?: string | null,
): Promise<CombinedMenuResponse> {
  const params = new URLSearchParams({ rappi_store_id, ubereats_store_id });
  if (lat !== undefined) params.set("lat", String(lat));
  if (lng !== undefined) params.set("lng", String(lng));
  if (didi_store_id) params.set("didi_store_id", didi_store_id);
  const res = await fetch(`${API_URL}/menu/combined?${params}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(parseDetail(body?.detail, res.status));
  }
  return res.json() as Promise<CombinedMenuResponse>;
}

export interface MatchingProduct {
  name: string;
  price: number;
  real_price?: number;  // precio sin oferta; si es mayor que price, hay oferta
  image_url: string;
  product_id: string;
}

export interface SearchResult {
  restaurant_name: string;
  rappi_store_id: string | null;
  ubereats_store_id: string | null;
  image_url: string;
  delivery_fee_preview: string;
  eta_preview: string;
  rating: string;
  matching_products: MatchingProduct[];
  is_open?: boolean; // false = no disponible (cerrado o fuera de cobertura)
}

export async function searchRestaurants(q: string, lat: number, lng: number): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q, lat: String(lat), lng: String(lng) });
  const res = await fetch(`${API_URL}/search?${params}`);
  if (!res.ok) return [];
  return res.json();
}

export interface PopularRestaurant {
  restaurant_name: string;
  rappi_store_id: string | null;
  ubereats_store_id: string | null;
  image_url: string;
  cuisine: string;
  is_open: boolean;
}

export interface OfferItem {
  rappi_store_id: string | null;
  ubereats_store_id: string | null;
  store_name: string;
  image_url: string;
  // Productos (Rappi)
  name?: string;
  price?: number;
  real_price?: number;
  eta?: string;
  // Tiendas (Uber Eats)
  offer?: string;
  rating?: string;
}

export interface OfferSection {
  title: string;
  platform: "rappi" | "ubereats";
  kind: "products" | "stores";
  items: OfferItem[];
}

export async function fetchOffers(lat: number, lng: number): Promise<OfferSection[]> {
  const params = new URLSearchParams({ lat: String(lat), lng: String(lng) });
  const res = await fetch(`${API_URL}/offers?${params}`);
  if (!res.ok) return [];
  return (await res.json()).sections ?? [];
}

export interface PlatformsStatus {
  rappi: { ok: boolean; since: number };
  ubereats: { ok: boolean; since: number };
}

export async function fetchPlatformsStatus(): Promise<PlatformsStatus | null> {
  const res = await fetch(`${API_URL}/status`).catch(() => null);
  return res?.ok ? res.json() : null;
}

export async function fetchPopularRestaurants(lat: number, lng: number): Promise<PopularRestaurant[]> {
  const params = new URLSearchParams({ lat: String(lat), lng: String(lng) });
  const res = await fetch(`${API_URL}/restaurants/popular?${params}`);
  if (!res.ok) return [];
  return res.json();
}

export async function compareProducts(req: CompareRequest): Promise<QuoteResponse[]> {
  const res = await fetch(`${API_URL}/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(parseDetail(body?.detail, res.status));
  }
  return res.json();
}

// --- Carrito multi-producto ---

export interface CompareCartRequest {
  rappi_store_id: string;
  ubereats_store_id: string;
  items: Array<{
    rappi_product_id?: string;
    ubereats_product_id?: string;
  }>;
  lat?: number;
  lng?: number;
}

export interface CartItemResponse {
  product_id: string;
  name: string;
  price: number;
}

export interface CartQuoteResponse {
  platform: string;
  product_price: number;
  delivery_fee: number | null;
  service_fee: number | null;
  total: number;
  currency: string;
  deep_link: string;
  store_name: string;
  store_address: string;
  is_open: boolean;
  opens_at: string;
  is_estimate: boolean;
  items: CartItemResponse[];
}

export async function compareCart(req: CompareCartRequest): Promise<CartQuoteResponse[]> {
  const res = await fetch(`${API_URL}/compare-cart`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(parseDetail(body?.detail, res.status));
  }
  return res.json();
}
