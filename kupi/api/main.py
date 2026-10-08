import difflib
import os
import re as _re
import threading
import time as _time
import unicodedata
from urllib.parse import urlparse

import requests as _requests
from cachetools import TTLCache
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from kupi.core.config import DEFAULT_LAT, DEFAULT_LNG
from kupi.core.models import PriceQuote
from kupi.connectors.rappi.connector import RappiConnector, search_stores as rappi_search
from kupi.connectors.ubereats.connector import UberEatsConnector
from kupi.connectors.didi.connector import DidiConnector

from kupi.api.favorites import router as favorites_router
from kupi.api.alerts import router as alerts_router

app = FastAPI(title="Kupi API", version="0.1.0")

app.include_router(favorites_router, prefix="/favorites", tags=["favorites"])
app.include_router(alerts_router, prefix="/alerts", tags=["alerts"])

# CORS: solo origenes permitidos (variable de entorno o localhost en desarrollo)
_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

rappi = RappiConnector()
ubereats = UberEatsConnector()
didi = DidiConnector()

# Nombres de restaurantes conocidos: corregir nombres de sucursal a nombre real
# Mapeo de nombres de sucursal → nombre real del restaurante.
# Muchas franquicias usan nombres de sucursal internos (zona, plaza, etc.)
# que la gente no reconoce. Este mapeo normaliza al nombre de marca.
# Las claves deben ser lowercase; se buscan con `in` (substring match).
_RESTAURANT_NAME_FIX = {
    # Sushi
    "malecon": "Sushi Factory",
    "malecón": "Sushi Factory",
    "sushi factory": "Sushi Factory",
    # Pizza
    "little caesars": "Little Caesars",
    "lc humaya": "Little Caesars",
    "lc forum": "Little Caesars",
    "lc tres": "Little Caesars",
    "pizza hut": "Pizza Hut",
    "domino's": "Domino's Pizza",
    "dominos": "Domino's Pizza",
    # Hamburguesas
    "mcdonald": "McDonald's",
    "mc donald": "McDonald's",
    "burger king": "Burger King",
    "carl's jr": "Carl's Jr.",
    "carls jr": "Carl's Jr.",
    # Pollo
    "kentucky": "KFC",
    "church's": "Church's Chicken",
    "churchs": "Church's Chicken",
    # Café
    "starbucks": "Starbucks",
    "italian coffee": "Italian Coffee",
    # Tacos
    "taqueria san juan": "Taquería San Juan",
    "taquería san juan": "Taquería San Juan",
    # Helados / postres
    "santa clara": "Santa Clara",
    "dairy queen": "Dairy Queen",
    # Conveniencia
    "oxxo": "OXXO",
    "7-eleven": "7-Eleven",
    "7 eleven": "7-Eleven",
}


def _fix_restaurant_name(name: str) -> str:
    """Corrige nombres de sucursal a nombre real del restaurante."""
    key = name.strip().lower()
    for pattern, fixed in _RESTAURANT_NAME_FIX.items():
        if pattern in key:
            return fixed
    # Limpiar direcciones del final del nombre:
    # "Tacos la Roma Boulevard Doctor Mora 1590" → "Tacos la Roma"
    cleaned = _re.sub(
        r'\s+(Avenida|Av\.?|Boulevard|Blvd\.?|Calle|Carretera|Carr\.?|Calz\.?|Calzada)\s+.*$',
        '', name.strip(), flags=_re.IGNORECASE,
    )
    if cleaned and len(cleaned) >= 4 and cleaned != name.strip():
        return cleaned
    return name


# Detecta nombres que son puramente direcciones o zonas genéricas (no restaurantes)
_ADDRESS_PATTERN = _re.compile(
    r'^(Avenida|Av\.?|Boulevard|Blvd\.?|Calle|Carretera|Carr\.?|Calz\.?|Calzada|Plaza)\s+',
    _re.IGNORECASE,
)
# Nombres que son solo una zona/colonia de Culiacán (Rappi los usa como nombre de sucursal)
_ZONE_NAMES = {
    "humaya", "quintas", "las quintas", "montebello", "tres rios", "tres ríos",
    "culiacan", "culiacán", "nuevo culiacán", "nuevo culiacan",
    "universitarios", "chapultepec", "guadalupe", "la primavera",
    "el barrio", "centro", "isla musala", "stanza", "country",
    "las palmas", "san cristobal", "san cristóbal", "perisur",
    "fracc portalegre", "portalegre", "la campiña", "la conquista",
    "lomas del boulevard", "infonavit barrancos", "barrancos",
    "col libertad", "libertad", "sanalona", "alturas del sur",
}


def _is_address_name(name: str) -> bool:
    """Detecta si un nombre de restaurante es en realidad una dirección o zona."""
    s = name.strip()
    if _ADDRESS_PATTERN.match(s):
        return True
    # Tiene número de calle (4+ dígitos)
    if _re.search(r'\b\d{4,}\b', s):
        return True
    # Es una zona conocida
    if s.lower().strip() in _ZONE_NAMES:
        return True
    return False

# ══════════════════════════════════════════════════════════════════════
# Test: enviar email de prueba via Resend
# ══════════════════════════════════════════════════════════════════════

@app.post("/test/email")
def test_email(to: str = Query(..., description="Email destino")):
    """Envía un email de prueba via Resend para verificar la integración."""
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY no configurado")
    resp = _requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
        json={
            "from": "Kupi <onboarding@resend.dev>",
            "to": [to],
            "subject": "Prueba de alerta - Kupi",
            "html": (
                "<h2>Alerta de precio - Kupi</h2>"
                "<p>El precio de <b>Crazy Bread</b> en <b>Little Caesars</b> "
                "bajo de $385 a $350 en Rappi (9% menos)</p>"
                "<p><a href='https://main.d2edvoaz20no1j.amplifyapp.com/favoritos'>"
                "Ver en Kupi</a></p>"
                "<p><small>Este es un email de prueba.</small></p>"
            ),
        },
        timeout=10,
    )
    if resp.status_code == 200:
        return {"status": "ok", "message": f"Email enviado a {to}"}
    raise HTTPException(status_code=resp.status_code, detail=resp.json())


# ══════════════════════════════════════════════════════════════════════
# Capa 1: Cache de resultados — misma búsqueda = 0 requests externos
# ══════════════════════════════════════════════════════════════════════
_search_cache = TTLCache(maxsize=2048, ttl=180)      # búsquedas, 3 min
_status_cache = TTLCache(maxsize=4096, ttl=600)       # status abierto/cerrado, 10 min
_popular_cache_store = TTLCache(maxsize=1, ttl=300)   # populares, 5 min
_featured_cache_store = TTLCache(maxsize=4, ttl=300)  # featured/deals, 5 min
_image_cache = TTLCache(maxsize=512, ttl=3600)         # imágenes proxy, 1h (bytes)
_image_cache_lock = threading.Lock()
_ue_products_cache = TTLCache(maxsize=256, ttl=600)    # productos UE por tienda, 10 min
_cache_lock = threading.Lock()

# ══════════════════════════════════════════════════════════════════════
# Capa 2: Request coalescing — N usuarios buscando lo mismo = 1 request
# ══════════════════════════════════════════════════════════════════════
_inflight: dict[str, threading.Event] = {}
_inflight_results: dict[str, list] = {}
_inflight_lock = threading.Lock()

# ══════════════════════════════════════════════════════════════════════
# Capa 3: Rate limit por IP — máximo 30 búsquedas/min por usuario
# ══════════════════════════════════════════════════════════════════════
_rate_limiter = TTLCache(maxsize=8192, ttl=60)  # ventana de 60s
_rl_lock = threading.Lock()
_SEARCH_RATE_LIMIT = 30  # búsquedas por IP por minuto
_GENERAL_RATE_LIMIT = 60  # requests generales por IP por minuto


def _check_rate_limit(ip: str, limit: int = _SEARCH_RATE_LIMIT, prefix: str = "search") -> None:
    key = f"{prefix}:{ip}"
    with _rl_lock:
        count = _rate_limiter.get(key, 0)
        if count >= limit:
            raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Intenta en un momento.")
        _rate_limiter[key] = count + 1


def _normalize_search_key(q: str, lat: float, lng: float) -> str:
    """Genera una clave de cache normalizada para la búsqueda."""
    # Redondear coords a 3 decimales (~110m) para agrupar ubicaciones cercanas
    return f"{q.strip().lower()}|{lat:.3f}|{lng:.3f}"

# Blacklist: tiendas/farmacias/supermercados que no son restaurantes
_STORE_BLACKLIST = _re.compile(
    r"\b(oxxo|7.?eleven|farmacia|super|soriana|ley|walmart|coppel|bodega|extra|chedraui|"
    r"sam.?s\s*club|costco|office\s*depot|home\s*depot|liverpool|palacio\s*de\s*hierro|"
    r"petco|pet\s*food|veterinari|ferreter|papeler|tlapal|cervecer|licorer|"
    r"conveniencia|minisuper|abarrotes|miscelanea|deposito)\b",
    _re.IGNORECASE,
)


# --- Esquemas de request/response ---

class CompareRequest(BaseModel):
    rappi_store_id: str
    ubereats_store_id: str
    rappi_product_id: str
    ubereats_product_id: str
    lat: float = DEFAULT_LAT
    lng: float = DEFAULT_LNG
    # Toppings de Rappi para simular checkout real (opcional - si no se envían, se usa el precio del menú)
    rappi_toppings: list[dict] | None = None
    # DiDi es opcional: si se omite, la respuesta solo incluye Rappi y Uber Eats
    didi_store_id: str | None = None
    didi_product_id: str | None = None


class QuoteResponse(BaseModel):
    platform: str
    product_price: float
    delivery_fee: float | None   # None en DiDi (solo disponible en la app)
    service_fee: float | None    # None en DiDi (solo disponible en la app)
    total: float
    currency: str
    eta_minutes: int | None
    deep_link: str
    store_name: str
    store_address: str
    variant_label: str = ""
    is_open: bool = True
    opens_at: str = ""
    is_estimate: bool = False


# --- Endpoints ---

def _normalize_name(name: str) -> str:
    name = name.lower()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = "".join(c if c.isalnum() or c.isspace() else " " for c in name)
    return " ".join(name.split())


def _match_products(rappi_products: list, ue_products: list) -> dict:
    ue_norm = [(p, _normalize_name(p.name)) for p in ue_products]
    matched = []
    matched_rappi_ids: set[str] = set()
    seen_ue_ids: set[str] = set()

    for rp in rappi_products:
        rp_norm = _normalize_name(rp.name)
        best_match = None
        best_ratio = 0.0
        for up, up_norm in ue_norm:
            if up.product_id in seen_ue_ids:
                continue
            ratio = difflib.SequenceMatcher(None, rp_norm, up_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = up
        if best_ratio >= 0.72 and best_match:
            # Rechazar si los precios difieren más del 25% — evita falsos positivos por nombre similar
            if best_match.price > 0 and rp.price > 0:
                price_ratio = min(rp.price, best_match.price) / max(rp.price, best_match.price)
                if price_ratio < 0.75:
                    continue
            matched_rappi_ids.add(rp.product_id)
            seen_ue_ids.add(best_match.product_id)
            matched.append({
                "name": rp.name,
                "description": rp.description,
                "price": rp.price,
                "image_url": rp.image_url or best_match.image_url or "",
                "rappi_product_id": rp.product_id,
                "ubereats_product_id": best_match.product_id,
            })

    only_rappi = [
        {"name": p.name, "description": p.description, "price": p.price,
         "image_url": p.image_url or "", "rappi_product_id": p.product_id, "platform": "rappi"}
        for p in rappi_products if p.product_id not in matched_rappi_ids
    ]

    # Deduplicar UberEats por product_id (el mismo producto puede aparecer en varias secciones)
    seen_ue_exclusive: set[str] = set()
    only_ubereats = []
    for p in ue_products:
        if p.product_id not in seen_ue_ids and p.product_id not in seen_ue_exclusive:
            seen_ue_exclusive.add(p.product_id)
            only_ubereats.append({
                "name": p.name, "description": p.description, "price": p.price,
                "image_url": p.image_url or "", "ubereats_product_id": p.product_id, "platform": "ubereats"
            })

    # Priorizar productos con imagen (primero), luego por precio
    _sort_key = lambda x: (0 if x.get("image_url") else 1, x["price"])
    return {
        "matched": sorted(matched, key=_sort_key),
        "only_rappi": sorted(only_rappi, key=_sort_key),
        "only_ubereats": sorted(only_ubereats, key=_sort_key),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/connectors")
def health_connectors():
    """Verifica que las cookies/tokens de Rappi y UE sigan funcionando.
    Envía alerta por email si alguno falla."""
    from kupi.jobs.health_check import run
    return run()


@app.get("/stores/status")
def get_stores_status(
    rappi_store_ids: str,
    ue_store_ids: str = "",
    lat: float = DEFAULT_LAT,
    lng: float = DEFAULT_LNG,
):
    """
    Verifica si cada restaurante está abierto.
    UberEats es la fuente de verdad (Rappi reporta falsamente "OPEN" en restaurantes cerrados).
    Rappi solo como fallback si no hay UE store ID.
    Resultados cacheados 10 min por store.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from kupi.connectors.ubereats.connector import _call_ubereats, _build_headers, _BASE_URL

    rappi_ids = [sid.strip() for sid in rappi_store_ids.split(",") if sid.strip()]
    ue_ids = [sid.strip() for sid in ue_store_ids.split(",") if sid.strip()]
    ue_map = {rappi_ids[i]: ue_ids[i] for i in range(min(len(rappi_ids), len(ue_ids)))}

    result: dict[str, dict] = {}
    to_check: list[str] = []

    # Revisar cache primero (TTLCache maneja expiración automáticamente)
    with _cache_lock:
        for rappi_id in rappi_ids:
            cached = _status_cache.get(rappi_id)
            if cached is not None:
                result[rappi_id] = {"is_open": cached}
            else:
                to_check.append(rappi_id)

    if not to_check:
        return result

    def check_ue(ue_store_id: str) -> bool:
        try:
            headers = _build_headers(lat, lng)
            body = {"storeUuid": ue_store_id, "diningMode": "DELIVERY", "time": {"asap": True}, "cbType": "EATER_ENDORSED"}
            data = _call_ubereats(f"{_BASE_URL}/getStoreV1?localeCode=mx", headers, body).get("data", {})
            return not data.get("closedMessage", "")
        except Exception:
            return False

    def check_rappi_fallback(store_id: str) -> bool:
        try:
            data = rappi._fetch_store(store_id, lat, lng)
            status = data.get("status", "")
            if status == "OUT_OF_COVERAGE":
                return False
            return status == "OPEN"
        except Exception:
            return False

    def check_one(rappi_id: str) -> tuple[str, bool]:
        ue_id = ue_map.get(rappi_id)
        if ue_id:
            # UberEats como fuente de verdad
            is_open = check_ue(ue_id)
        else:
            # Sin UE ID, usar Rappi como fallback
            is_open = check_rappi_fallback(rappi_id)
        return rappi_id, is_open

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(check_one, sid): sid for sid in to_check}
        for future in as_completed(futures):
            store_id, is_open = future.result()
            with _cache_lock:
                _status_cache[store_id] = is_open
            result[store_id] = {"is_open": is_open}

    return result


# Palabras/patrones que indican que un producto NO es un alimento que llena
_NON_FOOD_RE = _re.compile(
    r"\b\d+\s*ml\b"                                          # volumen: 600 ml, 237ml…
    r"|\blat[a]?\b"                                          # lata, latas
    r"|\blitros?\b|\blts?\b"                                 # litro/litros, lts
    r"|\b(coca.?cola|pepsi|sprite|fanta|sidral|mundet|fuze|7up|manzanita|mirinda|peñafiel|squirt|boing|fresca)\b"
    r"|\b(refresco|limonada|jugo|bebida|changuirongo)\b"     # bebidas
    r"|^\s*(salsa|aderezo|dip|crazy sauce)\b"                # salsas/aderezos al inicio
    r"|\bdip\b"                                             # dip en cualquier posición
    r"|\bsalsas?\s*$"                                        # "2 Salsas"
    r"|\b(bbq|ranch|brava|cheesepe[ñn]o|mango.habanero)\s*$"  # nombres de salsas solos
    r"|\bshot\b"                                             # salsas en formato shot (KFC)
    r"|\b(kream|big kream)\b"                                # bebidas KFC
    r"|\b(sundae|mcflurry|malteada|helado|pay de|dona|donut|cake pop)\b"  # postres
    r"|\bbaitz\b"                                            # Domino's dessert bites
    r"|\badicionales?\b"                                     # "2 Adicionales"
    r"|\b(puré de papa|papas?\s+(gajo|francesas?|a\s+la\s+francesa|fritas?|medianas?|grandes?|pequeñas?))\b"
    r"|\b(ensalada de col|coleslaw)\b"
    r"|\bsobre\s+(huntrix|saja)\b"                           # sobres de salsa McDonald's
    r"|\bfrijol(es)?\b"                                      # frijoles como guarnición
    r"|\b(cheesy\s*bread|papotas)\b"                         # Domino's sides
    r"|\b(crazy\s*bread|canela\s*stix)\b"                    # Little Caesars sides
    r"|\bté\s+de\s+la\s+casa\b"                             # té como bebida
    r"|extra\s*$"
    r"|ingrediente\s+extra"                                  # "Ingrediente Extra para Rollo"
    r"|\btogarashi\b"                                        # condimento Sushi City
    r"|\bquepapas?\b"                                        # snack Pizza Hut                                            # "Soya Extra", "Sriracha Extra"
    r"|\b(agua ciel|agua purificada)\b"
    r"|^agua\s"
    r"|^tortilla[s]?\s"                              # toda tortilla suelta
    r"|^guacamole\b"                                 # guacamole como dip
    r"|^queso\s*$",                                  # "Queso" solo = dip
    _re.IGNORECASE,
)


def _is_non_food(name: str) -> bool:
    return bool(_NON_FOOD_RE.search(name.strip()))


def _get_featured_restaurants() -> list[dict]:
    """Carga restaurantes desde Supabase (con ambas plataformas) para featured/deals."""
    try:
        from kupi.catalog.restaurants import get_all
        all_r = get_all()
        # Solo restaurantes con ambas plataformas (para poder comparar precios)
        return [
            {
                "restaurant_id": f"{r.get('rappi_store_id', '')}-{r.get('ubereats_store_id', '')}",
                "rappi_store_id": r["rappi_store_id"],
                "ubereats_store_id": r["ubereats_store_id"],
                "cuisine": r.get("cuisine", ""),
                "restaurant_name": _fix_restaurant_name(r.get("name", "")),
            }
            for r in all_r
            if r.get("rappi_store_id") and r.get("ubereats_store_id")
        ]
    except Exception as e:
        print(f"[featured] error cargando restaurantes de BD: {e}")
        return []

@app.get("/products/featured")
def get_featured_products(
    max_price: float = 100.0,
    lat: float = DEFAULT_LAT,
    lng: float = DEFAULT_LNG,
):
    """
    Productos bajo cierto precio, verificados en Rappi y Uber Eats.
    Corre en paralelo y cachea el resultado 5 minutos.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with _cache_lock:
        cached = _featured_cache_store.get("featured")
    if cached is not None:
        return [p for p in cached if p["price"] <= max_price]

    def fetch_one(r: dict) -> list[dict]:
        try:
            rappi_products = rappi.fetch_menu(r["rappi_store_id"], lat, lng)
        except Exception:
            rappi_products = []
        try:
            ue_products = ubereats.fetch_menu(r["ubereats_store_id"], lat, lng)
        except Exception:
            ue_products = []

        matched = _match_products(rappi_products, ue_products)
        results = []
        for p in matched["matched"]:
            # Filtrar extras, bebidas, salsas y postres
            if p["price"] < 45:
                continue
            if not p.get("image_url"):
                continue
            if _is_non_food(p["name"]):
                continue
            results.append({
                "name": p["name"],
                "price": p["price"],
                "image_url": p.get("image_url", ""),
                "restaurant_id": r["restaurant_id"],
                "restaurant_name": r["restaurant_name"],
                "category": r["cuisine"],
                "rappi_product_id": p.get("rappi_product_id", ""),
                "ubereats_product_id": p.get("ubereats_product_id", ""),
                "rappi_store_id": r["rappi_store_id"],
                "ubereats_store_id": r["ubereats_store_id"],
            })
        return results

    all_products: list[dict] = []
    with ThreadPoolExecutor(max_workers=9) as executor:
        featured = _get_featured_restaurants()
        futures = [executor.submit(fetch_one, r) for r in featured]
        for future in as_completed(futures):
            all_products.extend(future.result())

    all_products.sort(key=lambda x: x["price"])
    with _cache_lock:
        _featured_cache_store["featured"] = all_products
    return [p for p in all_products if p["price"] <= max_price]


@app.get("/products/deals")
def get_deals(
    category: str,
    max_price: float = 100.0,
    lat: float = DEFAULT_LAT,
    lng: float = DEFAULT_LNG,
):
    """
    Productos bajo el precio TOTAL real (producto + envío + cuota de servicio)
    verificado en Rappi y Uber Eats con checkout completo.
    Requiere categoría. Cache 5 min por categoría.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cache_key = f"deals_{category.lower()}_{int(max_price)}"
    with _cache_lock:
        cached = _featured_cache_store.get(cache_key)
    if cached is not None:
        return cached

    restaurants = [r for r in _get_featured_restaurants() if r["cuisine"].lower() == category.lower()]
    if not restaurants:
        return []

    # Paso 1: obtener menús en paralelo, conservando los objetos Product originales
    def fetch_menus(r: dict):
        try:
            rappi_prods = rappi.fetch_menu(r["rappi_store_id"], lat, lng)
        except Exception:
            rappi_prods = []
        try:
            ue_prods = ubereats.fetch_menu(r["ubereats_store_id"], lat, lng)
        except Exception:
            ue_prods = []
        rappi_map = {p.product_id: p for p in rappi_prods}
        ue_map = {p.product_id: p for p in ue_prods}
        matched = _match_products(rappi_prods, ue_prods)
        return r, rappi_map, ue_map, matched

    restaurant_data = []
    with ThreadPoolExecutor(max_workers=len(restaurants)) as ex:
        for result in as_completed([ex.submit(fetch_menus, r) for r in restaurants]):
            restaurant_data.append(result.result())

    # Paso 2: armar candidatos (filtro básico antes del checkout costoso)
    candidates = []
    for r, rappi_map, ue_map, matched in restaurant_data:
        for p in matched["matched"]:
            if p["price"] < 45 or p["price"] > max_price or not p.get("image_url"):
                continue
            if _is_non_food(p["name"]):
                continue
            rp = rappi_map.get(p.get("rappi_product_id", ""))
            up = ue_map.get(p.get("ubereats_product_id", ""))
            if not rp and not up:
                continue
            candidates.append((r, rp, up, p))

    # Paso 3: checkout completo en paralelo (limitado para no saturar UberEats)
    def full_compare(r, rp, up, p_info):
        quotes = []
        try:
            if rp:
                quotes.append(rappi.fetch_price(r["rappi_store_id"], rp, lat, lng))
        except Exception:
            pass
        try:
            if up:
                quotes.append(ubereats.fetch_price(r["ubereats_store_id"], up, lat, lng))
        except Exception:
            pass
        if not quotes:
            return None
        min_total = min(q.total for q in quotes)
        if min_total > max_price:
            return None
        best = min(quotes, key=lambda q: q.total)
        return {
            "name": p_info["name"],
            "price": p_info["price"],
            "total": round(min_total, 2),
            "best_platform": best.platform,
            "image_url": p_info.get("image_url", ""),
            "restaurant_id": r["restaurant_id"],
            "restaurant_name": r["restaurant_name"],
            "category": r["cuisine"],
            "rappi_product_id": p_info.get("rappi_product_id", ""),
            "ubereats_product_id": p_info.get("ubereats_product_id", ""),
            "quotes": [
                {"platform": q.platform, "total": round(q.total, 2), "delivery_fee": q.delivery_fee}
                for q in quotes
            ],
        }

    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(full_compare, r, rp, up, p) for r, rp, up, p in candidates]
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    results.sort(key=lambda x: x["total"])
    with _cache_lock:
        _featured_cache_store[cache_key] = results
    return results


# Dominios permitidos para proxy de imagenes (anti-SSRF)
_PROXY_ALLOWED_HOSTS = {
    "images.rappi.com.mx", "images.rappi.com",
    "cn-geo1.uber.com", "tb-static.uber.com", "www.ubereats.com",
    "d1ralsognjng37.cloudfront.net", "duyt4h9nfnj50.cloudfront.net",
    "d3i4yxtzktqr9n.cloudfront.net",
    "img.uber.com",
}


@app.get("/proxy/image")
def proxy_image(request: Request, url: str = Query(..., max_length=2048)):
    """Proxy para imágenes con hotlink protection + cache en memoria."""
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip, 120, "proxy")
    # Validar dominio (anti-SSRF)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL no valida")
    if parsed.hostname not in _PROXY_ALLOWED_HOSTS:
        raise HTTPException(status_code=400, detail="Dominio no permitido")

    # Cache en memoria: si ya descargamos esta imagen, servirla directo
    with _image_cache_lock:
        cached = _image_cache.get(url)
    if cached:
        return Response(
            content=cached["bytes"],
            media_type=cached["type"],
            headers={"Cache-Control": "public, max-age=86400", "X-Cache": "HIT"},
        )

    if "ubereats.com" in url or "cloudfront.net" in url or "uber.com" in url:
        referer = "https://www.ubereats.com/"
    else:
        referer = "https://www.rappi.com.mx/"
    try:
        resp = _requests.get(
            url,
            headers={
                "Referer": referer,
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except Exception:
        raise HTTPException(status_code=502, detail="No se pudo cargar la imagen")

    content_type = resp.headers.get("content-type", "image/png")
    img_bytes = resp.content
    # Solo cachear imágenes < 500KB para no saturar memoria
    if len(img_bytes) < 512_000:
        with _image_cache_lock:
            _image_cache[url] = {"bytes": img_bytes, "type": content_type}

    return Response(
        content=img_bytes,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400", "X-Cache": "MISS"},
    )


@app.get("/menu/rappi/{store_id}")
def get_rappi_menu(store_id: str, lat: float = DEFAULT_LAT, lng: float = DEFAULT_LNG):
    try:
        products = rappi.fetch_menu(store_id, lat, lng)
    except Exception as e:
        print(f"[menu/rappi] error: {e}")
        raise HTTPException(status_code=502, detail="Error al cargar menu de Rappi")
    return {"store_id": store_id, "products": [p.__dict__ for p in products]}


@app.get("/menu/ubereats/{store_id}")
def get_ubereats_menu(store_id: str, lat: float = DEFAULT_LAT, lng: float = DEFAULT_LNG):
    try:
        products = ubereats.fetch_menu(store_id, lat, lng)
    except Exception as e:
        print(f"[menu/ubereats] error: {e}")
        raise HTTPException(status_code=502, detail="Error al cargar menu de Uber Eats")
    return {"store_id": store_id, "products": [p.__dict__ for p in products]}


@app.get("/menu/didi/{store_id}")
def get_didi_menu(store_id: str):
    """
    Menú de una sucursal de DiDi Food por su ID numérico.
    El ID debe estar registrado en connectors/didi/stores.json.
    lat/lng no aplican (DiDi usa ciudad fija en la URL).
    """
    try:
        products = didi.fetch_menu(store_id, lat=0, lng=0)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tienda DiDi no encontrada")
    except Exception as e:
        print(f"[menu/didi] error: {e}")
        raise HTTPException(status_code=502, detail="Error al cargar menu de DiDi")
    return {"store_id": store_id, "products": [p.__dict__ for p in products]}


@app.get("/didi/stores")
def list_didi_stores():
    """Lista todas las sucursales de DiDi disponibles."""
    from kupi.connectors.didi.connector import _STORES
    return {
        "count": len(_STORES),
        "stores": [
            {"store_id": sid, "name": info["name"], "url": info["url"]}
            for sid, info in _STORES.items()
        ],
    }


@app.get("/menu/combined")
def get_combined_menu(
    rappi_store_id: str,
    ubereats_store_id: str,
    lat: float = DEFAULT_LAT,
    lng: float = DEFAULT_LNG,
    didi_store_id: str | None = None,
):
    """
    Jala el menú de Rappi y Uber Eats, hace matching por nombre normalizado,
    y opcionalmente también cruza con DiDi (si se pasa didi_store_id).
    Cada producto en 'matched' incluye didi_product_id si hay coincidencia.
    """
    errors: list[str] = []
    rappi_products = []
    ue_products = []
    didi_products = []

    try:
        rappi_products = rappi.fetch_menu(rappi_store_id, lat, lng)
    except Exception as e:
        errors.append(f"Rappi: {e}")

    try:
        ue_products = ubereats.fetch_menu(ubereats_store_id, lat, lng)
    except Exception as e:
        errors.append(f"UberEats: {e}")

    if didi_store_id:
        try:
            didi_products = didi.fetch_menu(didi_store_id, lat=0, lng=0)
        except Exception as e:
            errors.append(f"DiDi: {e}")

    if not rappi_products and not ue_products:
        raise HTTPException(status_code=404, detail="Este restaurante no está disponible en este momento. Puede estar cerrado o fuera de tu zona de cobertura.")

    result = _match_products(rappi_products, ue_products)

    # Cruzar productos matched con DiDi por nombre normalizado
    if didi_products:
        didi_norm = [(_normalize_name(p.name), p) for p in didi_products]
        for product in result["matched"]:
            rp_norm = _normalize_name(product["name"])
            best_id: str | None = None
            best_ratio = 0.0
            for dn, dp in didi_norm:
                ratio = difflib.SequenceMatcher(None, rp_norm, dn).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_id = dp.product_id
            # Umbral más bajo que Rappi↔UberEats porque los nombres difieren más entre plataformas
            if best_ratio >= 0.55 and best_id:
                product["didi_product_id"] = best_id
            else:
                product["didi_product_id"] = None

    return {
        "products": result["matched"],
        "only_rappi": result["only_rappi"],
        "only_ubereats": result["only_ubereats"],
        "errors": errors,
    }


@app.post("/compare", response_model=list[QuoteResponse])
def compare(request: Request, req: CompareRequest):
    """
    Cotiza el precio final de un producto en Rappi y Uber Eats en paralelo.
    Devuelve la lista de quotes ordenada de más barato a más caro (total).
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip, _GENERAL_RATE_LIMIT, "compare")
    quotes: list[PriceQuote] = []
    errors: list[str] = []

    # Rappi
    try:
        rappi_products = rappi.fetch_menu(req.rappi_store_id, req.lat, req.lng)
        rappi_product = next((p for p in rappi_products if p.product_id == req.rappi_product_id), None)
        if rappi_product:
            quotes.append(rappi.fetch_price(
                req.rappi_store_id, rappi_product, req.lat, req.lng,
                toppings=req.rappi_toppings,
            ))
        else:
            errors.append(f"Producto {req.rappi_product_id} no encontrado en Rappi")
    except Exception as e:
        errors.append(f"Rappi: {e}")

    # Uber Eats
    try:
        ue_products = ubereats.fetch_menu(req.ubereats_store_id, req.lat, req.lng)
        ue_product = next((p for p in ue_products if p.product_id == req.ubereats_product_id), None)
        if ue_product:
            quotes.append(ubereats.fetch_price(req.ubereats_store_id, ue_product, req.lat, req.lng))
        else:
            errors.append(f"Producto {req.ubereats_product_id} no encontrado en Uber Eats")
    except Exception as e:
        errors.append(f"Uber Eats: {e}")

    # DiDi (opcional — solo si se envían didi_store_id y didi_product_id)
    if req.didi_store_id and req.didi_product_id:
        try:
            didi_products = didi.fetch_menu(req.didi_store_id, req.lat, req.lng)
            didi_product = next(
                (p for p in didi_products if p.product_id == req.didi_product_id), None
            )
            if didi_product:
                quotes.append(didi.fetch_price(req.didi_store_id, didi_product, req.lat, req.lng))
            else:
                errors.append(f"Producto {req.didi_product_id} no encontrado en DiDi")
        except Exception as e:
            errors.append(f"DiDi: {e}")

    if not quotes:
        raise HTTPException(status_code=404, detail="No se pudo obtener el precio. El restaurante puede estar cerrado en este momento.")

    # Filtrar plataformas cerradas/no disponibles si hay al menos una abierta
    open_quotes = [q for q in quotes if q.is_open]
    if open_quotes:
        quotes = open_quotes

    # Ordenar por total; DiDi va al final si su total es parcial (sin envío)
    quotes.sort(key=lambda q: q.total)
    return [QuoteResponse(**q.__dict__) for q in quotes]


# ══════════════════════════════════════════════════════════════════════
# Carrito multi-producto
# ══════════════════════════════════════════════════════════════════════

class CartItemRequest(BaseModel):
    rappi_product_id: str | None = None
    ubereats_product_id: str | None = None

class CompareCartRequest(BaseModel):
    rappi_store_id: str
    ubereats_store_id: str
    items: list[CartItemRequest] = Field(..., min_length=1, max_length=10)
    lat: float = DEFAULT_LAT
    lng: float = DEFAULT_LNG

class CartItemResponse(BaseModel):
    product_id: str
    name: str
    price: float

class CartQuoteResponse(BaseModel):
    platform: str
    product_price: float
    delivery_fee: float | None
    service_fee: float | None
    total: float
    currency: str
    deep_link: str
    store_name: str
    store_address: str
    is_open: bool = True
    opens_at: str = ""
    is_estimate: bool = False
    items: list[CartItemResponse] = []

@app.post("/compare-cart", response_model=list[CartQuoteResponse])
def compare_cart(request: Request, req: CompareCartRequest):
    """
    Cotiza un carrito de múltiples productos en Rappi y Uber Eats.
    El envío y cuota de servicio se calculan una sola vez por plataforma.
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip, _GENERAL_RATE_LIMIT, "compare-cart")

    quotes: list[PriceQuote] = []
    errors: list[str] = []

    # Solo cotizar en plataformas donde TODOS los items del carrito tienen ID
    all_have_rappi = all(item.rappi_product_id for item in req.items)
    all_have_ue = all(item.ubereats_product_id for item in req.items)

    # Rappi
    if all_have_rappi:
        try:
            rappi_menu = rappi.fetch_menu(req.rappi_store_id, req.lat, req.lng)
            rappi_cart = []
            for item in req.items:
                p = next((x for x in rappi_menu if x.product_id == item.rappi_product_id), None)
                if p:
                    rappi_cart.append(p)
            if rappi_cart:
                quotes.append(rappi.fetch_cart_price(req.rappi_store_id, rappi_cart, req.lat, req.lng))
            else:
                errors.append("Ningún producto del carrito encontrado en Rappi")
        except Exception as e:
            errors.append(f"Rappi: {e}")

    # Uber Eats
    if all_have_ue:
        try:
            ue_menu = ubereats.fetch_menu(req.ubereats_store_id, req.lat, req.lng)
            ue_cart = []
            for item in req.items:
                p = next((x for x in ue_menu if x.product_id == item.ubereats_product_id), None)
                if p:
                    ue_cart.append(p)
            if ue_cart:
                quotes.append(ubereats.fetch_cart_price(req.ubereats_store_id, ue_cart, req.lat, req.lng))
            else:
                errors.append("Ningún producto del carrito encontrado en Uber Eats")
        except Exception as e:
            errors.append(f"Uber Eats: {e}")

    if not quotes:
        raise HTTPException(status_code=404, detail="No se pudo obtener el precio. El restaurante puede estar cerrado en este momento.")

    open_quotes = [q for q in quotes if q.is_open]
    if open_quotes:
        quotes = open_quotes

    quotes.sort(key=lambda q: q.total)

    result = []
    for q in quotes:
        items_detail = []
        if hasattr(q, '_items_detail'):
            items_detail = q._items_detail
        result.append(CartQuoteResponse(
            platform=q.platform,
            product_price=q.product_price,
            delivery_fee=q.delivery_fee,
            service_fee=q.service_fee,
            total=q.total,
            currency=q.currency,
            deep_link=q.deep_link,
            store_name=q.store_name,
            store_address=q.store_address,
            is_open=q.is_open,
            opens_at=q.opens_at,
            is_estimate=q.is_estimate,
            items=[CartItemResponse(product_id=p.product_id, name=p.name, price=p.price)
                   for p in (rappi_cart if q.platform == "rappi" else ue_cart)],
        ))
    return result


@app.get("/search")
def search_restaurants(
    request: Request,
    q: str = Query(..., max_length=200),
    lat: float = Query(DEFAULT_LAT, ge=-90, le=90),
    lng: float = Query(DEFAULT_LNG, ge=-180, le=180),
):
    """
    Búsqueda bidireccional: busca en Rappi y UberEats, cruza resultados por nombre.
    Auto-guarda restaurantes nuevos en Supabase.
    3 capas de protección: rate limit → cache → request coalescing.
    """
    # Capa 3: Rate limit por IP
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # Capa 1: Cache — misma búsqueda reciente = 0 requests externos
    cache_key = _normalize_search_key(q, lat, lng)
    with _cache_lock:
        cached = _search_cache.get(cache_key)
    if cached is not None:
        return cached

    # Capa 2: Request coalescing — si otra request ya busca lo mismo, esperar su resultado
    with _inflight_lock:
        if cache_key in _inflight:
            event = _inflight[cache_key]
        else:
            event = None
            _inflight[cache_key] = threading.Event()

    if event is not None:
        # Otra request ya está buscando esto — esperar hasta 15s
        event.wait(timeout=15)
        with _cache_lock:
            result = _search_cache.get(cache_key)
        if result is not None:
            return result
        # Si no hay resultado en cache, continuar con búsqueda propia (fallback)

    try:
        merged = _do_search(q, lat, lng)
    finally:
        # Señalizar a requests que esperaban y limpiar
        with _inflight_lock:
            evt = _inflight.pop(cache_key, None)
        if evt:
            evt.set()

    # Guardar en cache
    with _cache_lock:
        _search_cache[cache_key] = merged

    return merged


def _fetch_ue_products_cached(store_id: str, lat: float, lng: float) -> list[dict]:
    """Obtiene todos los productos de una tienda UE con cache de 10 min."""
    cache_key = f"ue_menu_{store_id}"
    with _cache_lock:
        cached = _ue_products_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        ue_products = ubereats.fetch_menu(store_id, lat, lng)
        all_prods = [
            {"name": p.name, "price": p.price, "image_url": p.image_url or "", "product_id": p.product_id}
            for p in ue_products if p.price > 0
        ]
        with _cache_lock:
            _ue_products_cache[cache_key] = all_prods
        return all_prods
    except Exception as e:
        print(f"[UE products] {store_id}: {e}")
        return []


def _fetch_ue_products_for_search(store_id: str, query: str, lat: float, lng: float) -> list[dict]:
    """Busca productos en una tienda UberEats que matcheen con la query de búsqueda."""
    all_prods = _fetch_ue_products_cached(store_id, lat, lng)
    q_lower = query.lower()
    q_words = q_lower.split()
    matching = []
    for p in all_prods:
        name_lower = p["name"].lower()
        if any(w in name_lower for w in q_words) or q_lower in name_lower:
            matching.append(p)
    # Si no hay match directo, tomar los primeros productos con imagen
    if not matching:
        for p in all_prods[:8]:
            if p["price"] >= 45 and p["image_url"] and not _is_non_food(p["name"]):
                matching.append(p)
    return matching[:6]


def _do_search(q: str, lat: float, lng: float) -> list[dict]:
    """Ejecuta la búsqueda real contra Rappi y UberEats."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from kupi.connectors.ubereats.connector import _call_ubereats, _build_headers, _BASE_URL

    def search_ue() -> list[dict]:
        try:
            headers = _build_headers(lat, lng)
            body = {
                "userQuery": q,
                "date": "",
                "startTime": 0,
                "endTime": 0,
                "sortAndFilters": [],
                "vertical": "ALL",
                "searchSource": "SEARCH_BAR",
                "displayType": "SEARCH_RESULTS",
                "searchType": "GLOBAL_SEARCH",
                "keyName": "",
                "cacheKey": "",
                "recaptchaToken": "",
            }
            data = _call_ubereats(f"{_BASE_URL}/getSearchFeedV1?localeCode=mx", headers, body)
            feed_items = data.get("data", {}).get("feedItems", [])
            if not isinstance(feed_items, list):
                return []
            results = []
            for item in feed_items:
                if not isinstance(item, dict) or item.get("type") != "REGULAR_STORE":
                    continue
                store = item.get("store", {}) or {}
                store_uuid = store.get("storeUuid", "")
                if not store_uuid:
                    continue
                title_obj = store.get("title", {})
                title = title_obj.get("text", "") if isinstance(title_obj, dict) else str(title_obj)
                # Imagen: tomar la de mayor resolución
                image_items = (store.get("image", {}) or {}).get("items", [])
                image = image_items[0]["url"] if image_items else ""
                # Parsear meta badges: envío, ETA, rating
                shipping_cost = 0.0
                eta = ""
                for meta in (store.get("meta", []) or []):
                    badge = meta.get("badgeType", "")
                    if badge == "FARE":
                        fare_data = (meta.get("badgeData", {}) or {}).get("fare", {})
                        fee_text = fare_data.get("deliveryFee", "") or meta.get("text", "")
                        # Extraer número de "Costo de envío: $12"
                        m = _re.search(r"\$(\d+(?:\.\d+)?)", fee_text)
                        if m:
                            shipping_cost = float(m.group(1))
                    elif badge == "ETD":
                        eta = meta.get("text", "")
                rating_obj = store.get("rating", {}) or {}
                rating = rating_obj.get("text", "") if isinstance(rating_obj, dict) else ""
                results.append({
                    "store_id": store_uuid,
                    "brand_name": title,
                    "image_url": image,
                    "eta": eta,
                    "shipping_cost": shipping_cost,
                    "rating": rating,
                })
            return results
        except Exception as e:
            print(f"[UE search] error: {e}")
            return []

    def search_rappi_fn() -> list[dict]:
        try:
            return rappi_search(q, lat, lng)
        except Exception as e:
            print(f"[Rappi search] error: {e}")
            return []

    with ThreadPoolExecutor(max_workers=2) as ex:
        rappi_future = ex.submit(search_rappi_fn)
        ue_future = ex.submit(search_ue)
        rappi_results = rappi_future.result()
        ue_results = ue_future.result()

    # Enriquecer UberEats con productos del menú (paralelo, con cache por tienda)
    ue_products_map: dict[str, list[dict]] = {}
    ue_to_enrich = [ue for ue in ue_results[:10]]
    if ue_to_enrich:
        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {
                ex.submit(_fetch_ue_products_for_search, ue["store_id"], q, lat, lng): ue["store_id"]
                for ue in ue_to_enrich
            }
            for f in as_completed(futures):
                store_id = futures[f]
                try:
                    ue_products_map[store_id] = f.result()
                except Exception:
                    pass

    # Cross-match por nombre: encontrar pares Rappi<->UE
    # Pre-computar nombres normalizados (evita re-normalizar en cada iteración)
    ue_norms = {ue["store_id"]: _normalize_name(ue["brand_name"]) for ue in ue_results}

    matched_results: list[dict] = []
    rappi_only: list[dict] = []
    ue_only: list[dict] = []
    used_ue: set[str] = set()
    used_rappi: set[str] = set()

    for rr in rappi_results:
        rappi_fixed = _fix_restaurant_name(rr["brand_name"])
        # Si el nombre de Rappi es una zona/dirección, no intentar cross-match
        # (evita juntar "Humaya" de Rappi con "Humaya Restaurante" de UE que son negocios distintos)
        if _is_address_name(rappi_fixed):
            continue
        rr_norm = _normalize_name(rr["brand_name"])
        best_ue = None
        best_ratio = 0.0
        for ue in ue_results:
            if ue["store_id"] in used_ue:
                continue
            ue_norm = ue_norms[ue["store_id"]]
            # Containment check rápido antes del SequenceMatcher costoso
            if rr_norm in ue_norm or ue_norm in rr_norm:
                ratio = 0.95
            elif abs(len(rr_norm) - len(ue_norm)) > max(len(rr_norm), len(ue_norm)) * 0.5:
                # Si la diferencia de longitud es > 50%, imposible que matchee a 0.85
                continue
            else:
                ratio = difflib.SequenceMatcher(None, rr_norm, ue_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_ue = ue
        if best_ratio >= 0.85 and best_ue:
            used_ue.add(best_ue["store_id"])
            used_rappi.add(rr["store_id"])
            # Combinar productos de ambas plataformas
            rappi_prods = rr.get("matching_products", [])
            ue_prods = ue_products_map.get(best_ue["store_id"], [])
            # Mezclar: si Rappi tiene productos y UE también, combinar sin duplicados
            combined_prods = list(rappi_prods)
            rappi_names = {p["name"].lower() for p in rappi_prods}
            for up in ue_prods:
                if up["name"].lower() not in rappi_names:
                    combined_prods.append(up)
            # Preferir nombre de UE si Rappi tiene una dirección/zona como nombre
            rappi_name = _fix_restaurant_name(rr["brand_name"])
            ue_name = _fix_restaurant_name(best_ue["brand_name"])
            final_name = ue_name if _is_address_name(rappi_name) else rappi_name
            matched_results.append({
                "restaurant_name": final_name,
                "rappi_store_id": rr["store_id"],
                "ubereats_store_id": best_ue["store_id"],
                "image_url": best_ue["image_url"] or rr["image_url"],
                "delivery_fee_preview": f"${rr['shipping_cost']:.0f}" if rr["shipping_cost"] else (f"${best_ue['shipping_cost']:.0f}" if best_ue.get("shipping_cost") else ""),
                "eta_preview": rr.get("eta", "") or best_ue.get("eta", ""),
                "rating": str(rr.get("rating", "") or best_ue.get("rating", "")),
                "matching_products": combined_prods[:6],
            })

    # Rappi sin match (excluir nombres que son solo dirección/zona o sin productos)
    for rr in rappi_results:
        if rr["store_id"] not in used_rappi and not _STORE_BLACKLIST.search(rr["brand_name"]):
            rappi_name = _fix_restaurant_name(rr["brand_name"])
            if _is_address_name(rappi_name):
                continue
            rappi_prods = rr.get("matching_products", [])
            if not rappi_prods:
                continue  # sin productos relevantes → no mostrar
            rappi_only.append({
                "restaurant_name": rappi_name,
                "rappi_store_id": rr["store_id"],
                "ubereats_store_id": None,
                "image_url": rr["image_url"],
                "delivery_fee_preview": f"${rr['shipping_cost']:.0f}" if rr["shipping_cost"] else "",
                "eta_preview": rr.get("eta", ""),
                "rating": str(rr.get("rating", "")),
                "matching_products": rappi_prods,
            })

    # UE sin match — solo si tiene productos relevantes (evita ruido de restaurantes irrelevantes)
    for ue in ue_results:
        if ue["store_id"] not in used_ue and not _STORE_BLACKLIST.search(ue["brand_name"]):
            ue_prods = ue_products_map.get(ue["store_id"], [])
            if not ue_prods:
                continue  # sin productos relevantes → no mostrar
            ue_name = _fix_restaurant_name(ue["brand_name"])
            if _is_address_name(ue_name):
                continue
            ue_only.append({
                "restaurant_name": ue_name,
                "rappi_store_id": None,
                "ubereats_store_id": ue["store_id"],
                "image_url": ue["image_url"],
                "delivery_fee_preview": f"${ue['shipping_cost']:.0f}" if ue.get("shipping_cost") else "",
                "eta_preview": ue.get("eta", ""),
                "rating": str(ue.get("rating", "")),
                "matching_products": ue_prods,
            })

    # Intercalar: primero los que tienen ambas plataformas, luego alternar Rappi/UE
    merged: list[dict] = list(matched_results)
    ri, ui = 0, 0
    while ri < len(rappi_only) or ui < len(ue_only):
        if ri < len(rappi_only):
            merged.append(rappi_only[ri])
            ri += 1
        if ui < len(ue_only):
            merged.append(ue_only[ui])
            ui += 1

    # Guardar URLs originales antes de sustituir (para el thread de upload)
    original_images: dict[str, str] = {}  # store_key -> original_url
    for r in merged:
        key = r.get("rappi_store_id") or r.get("ubereats_store_id") or ""
        original_images[key] = r.get("image_url", "")

    # Sustituir imágenes por URLs de Supabase CDN si ya están en la BD
    try:
        from kupi.catalog.restaurants import lookup_by_rappi_ids, lookup_by_ue_ids
        m_rappi = [r["rappi_store_id"] for r in merged if r.get("rappi_store_id")]
        m_ue = [r["ubereats_store_id"] for r in merged if r.get("ubereats_store_id")]
        db_by_rappi = lookup_by_rappi_ids(m_rappi) if m_rappi else {}
        db_by_ue = lookup_by_ue_ids(m_ue) if m_ue else {}
        for r in merged:
            db_row = db_by_rappi.get(r.get("rappi_store_id")) or db_by_ue.get(r.get("ubereats_store_id"))
            if db_row:
                db_img = db_row.get("image_url", "")
                if db_img and "supabase" in db_img:
                    r["image_url"] = db_img
    except Exception:
        pass  # Si falla, seguir con las URLs originales

    # Auto-guardar en Supabase en background (batch optimizado + subir imágenes)
    def _save_to_db():
        try:
            import os
            from supabase import create_client
            from kupi.catalog.image_store import upload_image
            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_SECRET_KEY", "")
            if not url or not key:
                return
            sb = create_client(url, key)

            # 1. Recopilar todos los IDs para buscar en batch (2 queries en vez de N*2)
            all_rappi_ids = [r["rappi_store_id"] for r in merged if r.get("rappi_store_id")]
            all_ue_ids = [r["ubereats_store_id"] for r in merged if r.get("ubereats_store_id")]
            existing_by_rappi: dict[str, dict] = {}
            existing_by_ue: dict[str, dict] = {}
            if all_rappi_ids:
                resp = sb.table("restaurants").select("id,rappi_store_id,ubereats_store_id,image_url").in_("rappi_store_id", all_rappi_ids).execute()
                existing_by_rappi = {r["rappi_store_id"]: r for r in (resp.data or [])}
            if all_ue_ids:
                resp = sb.table("restaurants").select("id,rappi_store_id,ubereats_store_id,image_url").in_("ubereats_store_id", all_ue_ids).execute()
                existing_by_ue = {r["ubereats_store_id"]: r for r in (resp.data or [])}

            # 2. Identificar qué imágenes necesitan subirse a Supabase Storage
            from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
            needs_upload: list[tuple[str, str]] = []  # (original_url, restaurant_key)
            for r in merged:
                rappi_id = r.get("rappi_store_id")
                ue_id = r.get("ubereats_store_id")
                key = rappi_id or ue_id or ""
                original_img = original_images.get(key, r.get("image_url", ""))
                if not original_img or "supabase" in original_img:
                    continue
                existing = existing_by_rappi.get(rappi_id) if rappi_id else None
                if not existing and ue_id:
                    existing = existing_by_ue.get(ue_id)
                if existing and "supabase" in (existing.get("image_url") or ""):
                    continue  # Ya tiene imagen en CDN
                needs_upload.append((original_img, rappi_id or ue_id or ""))

            # Subir en paralelo (máx 3 para no saturar Supabase free tier)
            uploaded: dict[str, str] = {}  # original_url -> cdn_url
            if needs_upload:
                with ThreadPoolExecutor(max_workers=3) as img_ex:
                    img_futures = {
                        img_ex.submit(upload_image, orig_url, key): orig_url
                        for orig_url, key in needs_upload[:20]  # Limitar a 20 por búsqueda
                    }
                    for f in _as_completed(img_futures):
                        orig_url = img_futures[f]
                        try:
                            cdn_url = f.result()
                            if cdn_url:
                                uploaded[orig_url] = cdn_url
                        except Exception:
                            pass

            # 3. Guardar en BD
            to_insert = []
            for r in merged:
                name = r["restaurant_name"]
                rappi_id = r.get("rappi_store_id")
                ue_id = r.get("ubereats_store_id")
                key = rappi_id or ue_id or ""
                orig_img = original_images.get(key, r.get("image_url", ""))
                cdn_img = uploaded.get(orig_img)  # None si no se subió

                existing = existing_by_rappi.get(rappi_id) if rappi_id else None
                if not existing and ue_id:
                    existing = existing_by_ue.get(ue_id)

                # Decidir qué imagen guardar:
                # 1. Si se acaba de subir al CDN, usar esa
                # 2. Si ya tiene CDN en la BD, NO pisar con la URL original
                # 3. Si no tiene CDN, guardar la original
                if cdn_img:
                    final_img = cdn_img
                elif existing and "supabase" in (existing.get("image_url") or ""):
                    final_img = existing["image_url"]  # Preservar CDN existente
                else:
                    final_img = orig_img

                row = {"name": name, "image_url": final_img, "match_confidence": "auto"}
                if rappi_id:
                    row["rappi_store_id"] = rappi_id
                if ue_id:
                    row["ubereats_store_id"] = ue_id
                if existing:
                    needs_update = False
                    update = {}
                    if cdn_img:  # Nueva imagen CDN
                        update["image_url"] = cdn_img
                        needs_update = True
                    if rappi_id and not existing.get("rappi_store_id"):
                        update["rappi_store_id"] = rappi_id
                        needs_update = True
                    if ue_id and not existing.get("ubereats_store_id"):
                        update["ubereats_store_id"] = ue_id
                        needs_update = True
                    if needs_update:
                        sb.table("restaurants").update(update).eq("id", existing["id"]).execute()
                else:
                    to_insert.append(row)

            # 4. Insertar nuevos en batch
            if to_insert:
                sb.table("restaurants").insert(to_insert).execute()
        except Exception as e:
            print(f"[auto-save] error: {e}")

    threading.Thread(target=_save_to_db, daemon=True).start()

    # Disponibilidad: marcar is_open por resultado (con ambas apps, requiere ambas).
    # Evita que el usuario entre a un restaurante que luego falla al comparar.
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {
            ex.submit(_store_available, r.get("rappi_store_id"), r.get("ubereats_store_id"), lat, lng): r
            for r in merged
        }
        for f in futs:
            try:
                futs[f]["is_open"] = f.result()
            except Exception:
                futs[f]["is_open"] = True  # optimista si falla el chequeo

    return merged


def _store_ue_open(ue_id: str, lat: float, lng: float) -> bool:
    """UberEats disponible en esta zona. Optimista ante errores de red. Cacheado."""
    from kupi.connectors.ubereats.connector import _call_ubereats, _build_headers, _BASE_URL
    k = f"ue_open_{ue_id}_{round(lat,2)}_{round(lng,2)}"
    with _cache_lock:
        c = _status_cache.get(k)
    if c is not None:
        return c
    v = True
    try:
        body = {"storeUuid": ue_id, "diningMode": "DELIVERY", "time": {"asap": True}, "cbType": "EATER_ENDORSED"}
        data = _call_ubereats(f"{_BASE_URL}/getStoreV1?localeCode=mx", _build_headers(lat, lng), body).get("data", {})
        v = not data.get("closedMessage", "")
        with _cache_lock:
            _status_cache[k] = v
    except Exception:
        pass
    return v


def _store_rappi_open(rappi_id: str, lat: float, lng: float) -> bool:
    """Rappi disponible/en cobertura en esta zona. OUT_OF_COVERAGE/CLOSED y errores
    4xx (p.ej. 404: la tienda no se puede servir) marcan NO disponible. Solo los
    errores transitorios (timeout, 5xx) quedan optimistas para no ocultar de más. Cacheado."""
    k = f"rp_open_{rappi_id}_{round(lat,2)}_{round(lng,2)}"
    with _cache_lock:
        c = _status_cache.get(k)
    if c is not None:
        return c
    v = True
    try:
        data = rappi._fetch_store(rappi_id, lat, lng)
        v = data.get("status") == "OPEN"
        with _cache_lock:
            _status_cache[k] = v
    except _requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if 400 <= status < 500:
            v = False  # error permanente de la tienda → no disponible
            with _cache_lock:
                _status_cache[k] = v
        # 5xx: transitorio, no cachear, quedar optimista
    except Exception:
        pass  # red/timeout: optimista, sin cachear
    return v


def _store_available(rappi_id, ue_id, lat: float, lng: float) -> bool:
    """Disponible para comparar. Con ambas apps, requiere que AMBAS lo estén
    (evita mostrar como clickeable un restaurante que luego falla al comparar)."""
    if ue_id and rappi_id:
        return _store_ue_open(ue_id, lat, lng) and _store_rappi_open(rappi_id, lat, lng)
    if ue_id:
        return _store_ue_open(ue_id, lat, lng)
    if rappi_id:
        return _store_rappi_open(rappi_id, lat, lng)
    return True


@app.get("/restaurants/popular")
def get_popular_restaurants(
    lat: float = DEFAULT_LAT,
    lng: float = DEFAULT_LNG,
):
    """
    Restaurantes populares desde Supabase con status abierto/cerrado en tiempo real.
    Prioriza restaurantes con ambas plataformas e imagen.
    Con ambas apps, solo se marca disponible si AMBAS lo están. Cache de 5 min.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Cache por ubicación (redondeada a 1 decimal ~11km) para no servir Culiacán a alguien en Veracruz
    cache_key = f"popular_{round(lat,1)}_{round(lng,1)}"
    with _cache_lock:
        cached = _popular_cache_store.get(cache_key)
    if cached is not None:
        return cached

    try:
        from kupi.catalog.restaurants import get_all
        all_restaurants = get_all()
    except Exception as e:
        print(f"[popular] error cargando BD: {e}")
        all_restaurants = []

    if not all_restaurants:
        return []

    # Filtrar blacklist y priorizar: ambas plataformas + imagen primero
    filtered = [r for r in all_restaurants if not _STORE_BLACKLIST.search(r.get("name", ""))]
    filtered.sort(key=lambda r: (
        0 if (r.get("rappi_store_id") and r.get("ubereats_store_id") and r.get("image_url")) else 1,
        0 if (r.get("rappi_store_id") and r.get("ubereats_store_id")) else 1,
    ))
    candidates = filtered[:50]  # Limitar para no saturar APIs

    def check_status(r: dict) -> dict:
        is_open = _store_available(r.get("rappi_store_id"), r.get("ubereats_store_id"), lat, lng)
        return {
            "restaurant_name": _fix_restaurant_name(r.get("name", "")),
            "rappi_store_id": r.get("rappi_store_id"),
            "ubereats_store_id": r.get("ubereats_store_id"),
            "image_url": r.get("image_url", ""),
            "cuisine": r.get("cuisine", ""),
            "is_open": is_open,
        }

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_status, r) for r in candidates]
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except Exception:
                pass

    # Abiertos primero, luego cerrados
    results.sort(key=lambda r: (0 if r["is_open"] else 1, r["restaurant_name"]))
    with _cache_lock:
        _popular_cache_store[cache_key] = results
    return results


@app.get("/coupons")
def get_coupons_endpoint(restaurant_id: str | None = None):
    """
    Devuelve cupones activos desde Supabase.
    Opcionalmente filtra por restaurant_id.
    """
    try:
        from kupi.catalog.coupons import get_coupons
        return get_coupons(restaurant_id)
    except Exception as e:
        print(f"[coupons] error: {e}")
        raise HTTPException(status_code=502, detail="Error al cargar cupones")


@app.post("/coupons/refresh")
def refresh_coupons_endpoint(
    request: Request,
    lat: float = DEFAULT_LAT,
    lng: float = DEFAULT_LNG,
):
    """
    Escanea Rappi y UberEats en tiempo real y actualiza la tabla de cupones en Supabase.
    Operación costosa (~10-30s) - protegido con API key o rate limit estricto.
    """
    # Proteger con API key si esta configurada, si no, rate limit estricto
    api_key = os.environ.get("KUPI_ADMIN_KEY", "")
    req_key = request.headers.get("x-api-key", "")
    if api_key and req_key != api_key:
        raise HTTPException(status_code=403, detail="No autorizado")
    if not api_key:
        # Sin API key configurada: rate limit muy estricto (3/min)
        client_ip = request.client.host if request.client else "unknown"
        _check_rate_limit(client_ip, 3, "refresh")

    try:
        from kupi.catalog.coupons import refresh_coupons
        count = refresh_coupons(lat, lng)
        return {"saved": count}
    except Exception:
        raise HTTPException(status_code=502, detail="Error al refrescar cupones")
