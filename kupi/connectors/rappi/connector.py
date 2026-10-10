import json
import re
import logging
import threading
import time
import requests

logger = logging.getLogger(__name__)
from kupi.connectors.base import BaseConnector
from kupi.core.cache import PlatformHealth, Throttle, TTLStore, loc_key, zone_center
from kupi.core.config import RAPPI_TOKEN, RAPPI_DEVICE_ID, RAPPI_REFRESH_TOKEN, persist_env
from kupi.core.models import Product, PriceQuote

# Todas las peticiones a Rappi van espaciadas, para no parecer un bot ni arriesgar la cuenta
_throttle = Throttle(0.35)
health = PlatformHealth("Rappi")  # lectura (menús, búsqueda, feed) con sesión de invitado
account_health = PlatformHealth("Rappi (cuenta de Kupi)")  # checkout con la cuenta de Kupi (solo para el envío)


# Dos sesiones, para que los precios no dependan de la cuenta:
# - Invitado: menús, ofertas, búsqueda y feed (lo que ve cualquier persona); Kupi saca la
#   sesión solo, como rappi.com.mx sin login. Si la cuenta cae, todo esto sigue saliendo.
# - Cuenta de Kupi: el checkout, porque el envío solo se calcula con una dirección guardada
#   (un invitado no puede crear direcciones). Su precio se valida contra el menú (ver
#   _checkout_summary) para no mostrar promos que solo tenga la cuenta.
_REFRESH_URL = "https://services.mxgrability.rappi.com/api/rocket/refresh-token"
_GUEST_PASSPORT_URL = "https://services.mxgrability.rappi.com/api/rocket/v2/guest/passport/"
_GUEST_URL = "https://services.mxgrability.rappi.com/api/rocket/v2/guest"
_refresh_token = RAPPI_REFRESH_TOKEN
_auth_lock = threading.Lock()
_refresh_failed_at = 0.0  # si renovar falla, no reintentar en cada petición
_guest_expires_at = 0.0
_guest_failed_at = 0.0


def _refresh_session(stale_auth: str) -> bool:
    """
    Renueva la sesión de la cuenta con el refresh token (lo mismo que hace rappi.com.mx cuando
    el token vence). Rappi devuelve un token y un refresh token nuevos, así que la sesión no
    caduca mientras Kupi la use. True si hay un token vigente para reintentar.
    """
    global _refresh_token, _refresh_failed_at
    with _auth_lock:
        if _ACCOUNT_HEADERS["authorization"] != stale_auth:
            return True  # otra petición ya lo renovó
        if time.time() - _refresh_failed_at < 300:
            return False
        if not _refresh_token:
            _refresh_failed_at = time.time()
            logger.error("Rappi: sesión vencida y sin RAPPI_REFRESH_TOKEN (correr rotate.py --rappi)")
            return False
        r = requests.post(_REFRESH_URL, json={"refresh_token": _refresh_token},
                          headers={"content-type": "application/json"}, timeout=15)
        access = r.json().get("access_token") if r.ok else None
        if not access:
            _refresh_failed_at = time.time()
            logger.error("Rappi: no se pudo renovar la sesión de la cuenta (HTTP %s)", r.status_code)
            return False
        _refresh_token = r.json().get("refresh_token") or _refresh_token
        _ACCOUNT_HEADERS["authorization"] = f"Bearer {access}"
        persist_env({"RAPPI_TOKEN": access, "RAPPI_REFRESH_TOKEN": _refresh_token})
        logger.info("Rappi: sesión de la cuenta renovada")
        return True


def _renew_guest(stale_auth: str | None = None) -> bool:
    """
    Pide una sesión de invitado nueva (passport → guest, igual que rappi.com.mx sin login).
    Dura 7 días; se pide de nuevo un poco antes de vencer o si Rappi la rechaza.
    """
    global _guest_expires_at, _guest_failed_at
    with _auth_lock:
        if stale_auth is not None and _HEADERS["authorization"] != stale_auth:
            return True  # otra petición ya la renovó
        if stale_auth is None and time.time() < _guest_expires_at:
            return True
        if time.time() - _guest_failed_at < 60:
            return False
        base = {
            "deviceId": RAPPI_DEVICE_ID, "content-type": "application/json",
            "user-agent": _HEADERS["user-agent"], "origin": _HEADERS["origin"], "referer": _HEADERS["referer"],
        }
        try:
            r = requests.get(_GUEST_PASSPORT_URL, headers=base, timeout=15)
            r.raise_for_status()
            r = requests.post(_GUEST_URL, headers={**base, "x-guest-api-key": r.json()["token"]}, timeout=15)
            r.raise_for_status()
            data = r.json()
            access = data["access_token"]
        except Exception as e:
            _guest_failed_at = time.time()
            logger.error("Rappi: no se pudo obtener sesión de invitado (%s)", e)
            return False
        for headers in _READ_HEADERS:
            headers["authorization"] = f"Bearer {access}"
        _guest_expires_at = time.time() + float(data.get("expires_in") or 86400) - 3600
        logger.info("Rappi: sesión de invitado nueva")
        return True


class _ThrottledRequests:
    def __getattr__(self, method: str):
        fn = getattr(requests, method)

        def call(*args, **kwargs):
            headers = kwargs.get("headers")
            is_account = headers is _ACCOUNT_HEADERS
            platform = account_health if is_account else health
            if not platform.allow():
                raise RuntimeError("La sesión de Rappi de Kupi no está activa" if is_account
                                   else "Rappi no está respondiendo por ahora")
            if not is_account and time.time() >= _guest_expires_at:
                _renew_guest()
            if headers is not None and not is_account:
                headers["authorization"] = _HEADERS["authorization"]  # copias de los headers
            _throttle.wait()
            resp = fn(*args, **kwargs)
            if resp.status_code == 401 and headers is not None:
                stale = headers.get("authorization", "")
                if _refresh_session(stale) if is_account else _renew_guest(stale):
                    headers["authorization"] = (_ACCOUNT_HEADERS if is_account else _HEADERS)["authorization"]
                    _throttle.wait()
                    resp = fn(*args, **kwargs)
            platform.record(resp.status_code)
            return resp
        return call


_http = _ThrottledRequests()

_store_cache = TTLStore(maxsize=512, ttl=300)   # menú/estado de tienda, 5 min
_quote_cache = TTLStore(maxsize=1024, ttl=300)  # cotizaciones (checkout real), 5 min

_HEADERS = {
    "authorization": "",  # sesión de invitado, se llena en la primera petición
    "app-version": "1.162.2",
    "deviceid": RAPPI_DEVICE_ID,
    "content-type": "application/json; charset=UTF-8",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "accept": "application/json",
    "accept-language": "es-MX",
    "origin": "https://www.rappi.com.mx",
    "referer": "https://www.rappi.com.mx/",
}
_ACCOUNT_HEADERS = {**_HEADERS, "authorization": f"Bearer {RAPPI_TOKEN}"}

_STORE_URL = "https://services.mxgrability.rappi.com/api/web-gateway/web/restaurants-bus/store/id"
_CART_BASE = "https://services.mxgrability.rappi.com/api/ms/shopping-cart"
_ADDRESS_URL = "https://services.mxgrability.rappi.com/api/ms/consumer-address/v2/user-addresses"
_IMAGE_CDN = "https://images.rappi.com.mx/products/"
_LOGO_CDN = "https://images.rappi.com.mx/restaurants_logo/"
_BG_CDN = "https://images.rappi.com.mx/restaurants_background/"

_SEARCH_URL_PRIMARY = "https://services.mxgrability.rappi.com/api/pns-global-search-api/v1/unified-search"
_SEARCH_URL_FALLBACK = "https://services.mxgrability.rappi.com/api/pns-global-search-api/v1/unified-suggestions"
_SEARCH_IMG_CDN = "https://images.rappi.com.mx/web_theme/logos/"

_HEADERS_SEARCH = {
    **{k: v for k, v in _HEADERS.items()},
    "app-version": "e1de6be43aa29091011474615d7ac0810051c36a",
    "needappsflyerid": "false",
    "vendor": "rappi",
    "x-application-id": "rappi-microfront-web/e1de6be43aa29091011474615d7ac0810051c36a",
}


def _rappi_image(raw: str) -> str:
    if not raw:
        return ""
    if raw.startswith("http"):
        return raw
    return f"{_IMAGE_CDN}{raw}"


def _rappi_store_image(store_data: dict) -> str:
    """Devuelve la imagen de fondo del restaurante, o su logo como fallback."""
    bg = store_data.get("background", "")
    if bg:
        return f"{_BG_CDN}{bg}"
    logo = store_data.get("logo", "")
    if logo:
        return f"{_LOGO_CDN}{logo}"
    return ""


# Cada sesión tiene un solo carrito: dos cotizaciones a la vez se pisarían
_guest_cart_lock = threading.Lock()
_checkout_lock = threading.Lock()


def _checkout_summary(store_id: str, vendor_id: str, cart_products: list[dict], lat: float, lng: float,
                      store_data: dict, menu_total: float | None) -> dict:
    """
    Desglose exacto de un carrito en Rappi para un usuario normal. Devuelve
    {"product_price", "delivery_fee", "service_fee"}.

    El checkout con dirección solo existe con la cuenta (por el envío). Como Rappi puede darle
    o quitarle ofertas a una cuenta, el precio de referencia es el del menú (ofertas para todos,
    sin Pro): si la cuenta cobra otro precio por los productos, se usa el del menú y la cuota
    de servicio de un carrito de invitado.
    """
    key = (store_id, json.dumps(cart_products, sort_keys=True), loc_key(lat, lng))

    def fetch() -> dict:
        account = _summary_lines(_run_account_checkout(store_id, vendor_id, cart_products, lat, lng))
        guest = None
        if menu_total is not None and account["product_total"] is not None \
                and abs(account["product_total"] - menu_total) > 0.009:
            logger.warning("Rappi: la cuenta cobra %s por productos que en el menú cuestan %s",
                           account["product_total"], menu_total)
            guest = _summary_lines(_run_guest_cart(store_id, vendor_id, cart_products))
        return _combine(account, guest, store_data, menu_total)
    return _quote_cache.get_or_fetch(key, fetch)


def _put_cart(headers: dict, store_id: str, vendor_id: str, cart_products: list[dict]) -> None:
    """PUT del carrito (reintenta una vez si hay 409 por un carrito previo activo)."""
    body = [{"id": int(store_id), "products": cart_products,
             "vendor": {"id": vendor_id, "type": "rappi", "flow_type": "rappi-web"}}]
    r = _http.put(f"{_CART_BASE}/v2/restaurant/store", headers=headers, json=body, timeout=10)
    if r.status_code == 409:
        _clear_cart(headers, store_id, vendor_id)
        time.sleep(0.3)
        r = _http.put(f"{_CART_BASE}/v2/restaurant/store", headers=headers, json=body, timeout=10)
    r.raise_for_status()


def _read_summary(headers: dict) -> dict:
    _http.post(f"{_CART_BASE}/v1/restaurant/recalculate", headers=headers, json={}, timeout=10).raise_for_status()
    r = _http.get(f"{_CART_BASE}/v1/restaurant/summary-v2", headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def _run_guest_cart(store_id: str, vendor_id: str, cart_products: list[dict]) -> dict:
    """Carrito de invitado: Rappi calcula producto y cuota de servicio sin dirección (sin envío)."""
    if not _guest_cart_lock.acquire(timeout=30):
        raise RuntimeError("Rappi está ocupado cotizando otros pedidos; intenta de nuevo en unos segundos")
    try:
        _put_cart(_HEADERS, store_id, vendor_id, cart_products)
        return _read_summary(_HEADERS)
    finally:
        try:
            _clear_cart(_HEADERS, store_id, vendor_id)
        finally:
            _guest_cart_lock.release()


def _run_account_checkout(store_id: str, vendor_id: str, cart_products: list[dict], lat: float, lng: float) -> dict:
    """
    Checkout con la cuenta para el envío. Rappi cotiza con las coordenadas de una dirección
    guardada (change-address exige su id e ignora otras coordenadas): se crea una dirección
    inactiva temporal en la ubicación del usuario y se borra al terminar, junto con el carrito.
    """
    # Con mucha demanda, esperar turno sin límite congelaría el servidor: mejor avisar
    if not _checkout_lock.acquire(timeout=30):
        raise RuntimeError("Rappi está ocupado cotizando otros pedidos; intenta de nuevo en unos segundos")
    address_id = None
    try:
        _put_cart(_ACCOUNT_HEADERS, store_id, vendor_id, cart_products)
        ra = _http.post(_ADDRESS_URL, headers=_ACCOUNT_HEADERS, json={
            "address": "Kupi", "tag": "Casa", "description": "", "active": False,
            "lat": lat, "lng": lng, "country": "mx", "zip_code": "", "micro_zone_id": "0",
            "instructions": "", "title": "", "subtitle": "",
            "delivery_option": "HAND_TO_ME_AT_DOOR", "address_type": "HOUSE", "url_image": "",
            "extra_fields": [{"field": "ADDITIONAL_DETAILS", "value": "Kupi"}],
        }, timeout=10)
        ra.raise_for_status()
        address_id = ra.json()["id"]
        _http.post(
            f"{_CART_BASE}/v1/restaurant/change-address",
            headers=_ACCOUNT_HEADERS,
            json={"id": address_id, "lat": lat, "lng": lng},
            timeout=10,
        ).raise_for_status()
        return _read_summary(_ACCOUNT_HEADERS)
    finally:
        try:
            _clear_cart(_ACCOUNT_HEADERS, store_id, vendor_id)
            if address_id:
                try:
                    _http.delete(f"{_ADDRESS_URL}/{address_id}", headers=_ACCOUNT_HEADERS, timeout=10).raise_for_status()
                except Exception as e:
                    logger.warning("Rappi: no se pudo borrar la dirección temporal %s (%s)", address_id, e)
        finally:
            _checkout_lock.release()


_STRUCK_PRICE = re.compile(r"<s>.*?\$\s*([\d,]+(?:\.\d+)?)", re.S)


def _summary_lines(summary: dict) -> dict:
    """
    Renglones de summary-v2 (los sub_value del Total):
      product_total → productos con ofertas; shipping → envío (con el precio tachado si hay
      promo de envío); service_fee → cuota de servicio; tip → propina (opcional, se excluye).
    Otros renglones: cargos (positivos, ej. entrega extendida) o descuentos (negativos).
    """
    lines = {"product_total": None, "shipping": 0.0, "shipping_before_promo": None,
             "service_fee": 0.0, "charges": 0.0, "discounts": 0.0}
    for section in summary.get("summary", []):
        for sub in (section.get("sub_value") or []):
            t = sub.get("type")
            val = float(sub.get("raw_value") or 0)
            if t == "product_total":
                lines["product_total"] = val
            elif t == "shipping":
                lines["shipping"] = val
                m = _STRUCK_PRICE.search(sub.get("value") or "")
                if m:
                    lines["shipping_before_promo"] = float(m.group(1).replace(",", ""))
            elif t == "service_fee":
                lines["service_fee"] = val
            elif t == "tip" or t is None:
                pass
            elif val >= 0:
                lines["charges"] += val
            else:
                logger.info("rappi summary: descuento %s = %s", t, val)
                lines["discounts"] += val
    return lines


def _combine(account: dict, guest: dict | None, store_data: dict, menu_total: float | None) -> dict:
    """
    Total de un usuario normal a partir del checkout de la cuenta, sin las promos propias de
    la cuenta: si el envío viene rebajado (ej. envío gratis en la primera orden) y la tienda no
    tiene envío gratis para todos, se toma la tarifa tachada; los descuentos del carrito se
    ignoran (pueden ser de bienvenida). Si la cuenta cobra otro precio por los productos que el
    menú, se usan el precio del menú y la cuota del carrito de invitado (solo si la cuota es fija,
    porque si es porcentaje depende del precio).
    """
    if account["product_total"] is None:
        raise RuntimeError("Rappi no devolvió el costo de los productos")
    shipping = account["shipping"]
    free_for_all = bool((store_data.get("metadata") or {}).get("free_shipping_available"))
    if account["shipping_before_promo"] is not None and not free_for_all:
        shipping = account["shipping_before_promo"]
    product, service = account["product_total"], account["service_fee"]
    if guest is not None:
        if float(store_data.get("percentage_service_fee") or 0) > 0:
            raise RuntimeError("Rappi no confirmó el precio de oferta para este pedido")
        product, service = menu_total, guest["service_fee"]
    return {
        "product_price": round(product, 2),
        "delivery_fee": round(shipping + account["charges"], 2),
        "service_fee": round(service, 2),
    }


def _quote(breakdown: dict, store_id: str, store_name: str, store_address: str, eta_minutes: int | None,
           deep_link: str, variant_label: str = "", is_open: bool = True) -> PriceQuote:
    return PriceQuote(
        platform="rappi",
        product_price=breakdown["product_price"],
        delivery_fee=breakdown["delivery_fee"],
        service_fee=breakdown["service_fee"],
        total=round(breakdown["product_price"] + breakdown["delivery_fee"] + breakdown["service_fee"], 2),
        eta_minutes=eta_minutes,
        deep_link=deep_link,
        store_name=store_name,
        store_address=store_address,
        variant_label=variant_label,
        is_open=is_open,
    )


def _offer_price(p: dict) -> float | None:
    """
    Precio con oferta del producto, o None si no tiene una que aplique.
    Rappi deja `price` en el precio normal y manda la rebaja en `discounts[]`.
    Las ofertas exclusivas de Rappi Pro no se aplican a un usuario normal (confirmado
    en checkout), así que se ignoran.
    """
    base = float(p["price"])
    best = None
    for d in p.get("discounts") or []:
        if d.get("is_prime_exclusive") or not d.get("apply_to_user", True):
            continue
        price = d.get("price")
        if price is None:
            continue
        price = float(price)
        if 0 < price < base and (best is None or price < best):
            best = price
    return best


class RappiConnector(BaseConnector):

    def _fetch_store(self, store_id: str, lat: float, lng: float) -> dict:
        def fetch() -> dict:
            body = {
                "lat": lat,
                "lng": lng,
                "store_type": "restaurant",
                "is_prime": False,
                "prime_config": {"unlimited_shipping": False},
            }
            resp = _http.post(f"{_STORE_URL}/{store_id}/", headers=_HEADERS, json=body, timeout=10)
            resp.raise_for_status()
            return resp.json()
        return _store_cache.get_or_fetch((store_id, loc_key(lat, lng, 2)), fetch)

    def fetch_menu(self, store_id: str, lat: float, lng: float) -> list[Product]:
        data = self._fetch_store(store_id, lat, lng)
        # Si la tienda no está disponible para delivery, no devolver productos
        if data.get("status") != "OPEN":
            logger.info("Rappi store %s no disponible (status=%s)", store_id, data.get("status"))
            return []
        products = []
        seen: set[str] = set()
        for corridor in data.get("corridors", []):
            for p in corridor.get("products", []):
                # El mismo producto aparece en varios pasillos (ej. "Promos" y "Postres")
                if str(p["product_id"]) in seen:
                    continue
                seen.add(str(p["product_id"]))
                offer = _offer_price(p)
                products.append(Product(
                    product_id=str(p["product_id"]),
                    name=p["name"],
                    price=offer if offer is not None else float(p["price"]),
                    real_price=float(p["price"]) if offer is not None else float(p.get("real_price", p["price"])),
                    description=p.get("description", ""),
                    image_url=_rappi_image(p.get("image", "")),
                    has_variants=bool(p.get("need_topping")),
                ))
        return products

    def fetch_price(
        self,
        store_id: str,
        product: Product,
        lat: float,
        lng: float,
        toppings: list[dict] | None = None,
    ) -> PriceQuote:
        data = self._fetch_store(store_id, lat, lng)
        eta = data.get("eta")
        eta_minutes = int("".join(filter(str.isdigit, str(eta)))) if eta else None
        # Solo totales exactos: si el checkout falla (ej. producto con personalización
        # obligatoria, Rappi ocupado), el error sube y Rappi no aparece en esa comparación
        return self._fetch_checkout(
            store_id=store_id,
            product=product,
            lat=lat,
            lng=lng,
            toppings=toppings or [],
            store_data=data,
            eta_minutes=eta_minutes,
            is_open=data.get("status") == "OPEN",
        )

    def _fetch_checkout(
        self,
        store_id: str,
        product: Product,
        lat: float,
        lng: float,
        toppings: list[dict],
        store_data: dict,
        eta_minutes: int | None,
        is_open: bool = True,
    ) -> PriceQuote:
        """Checkout real de Rappi para un producto (ver _checkout_summary)."""
        raw_name = store_data.get("name", "")
        store_name = raw_name.split(" - ", 1)[-1] if " - " in raw_name else raw_name
        store_address = store_data.get("address", "")

        # Extraer partner_id del store si está disponible, sino usar el store_id
        partner_id = str(store_data.get("partner_id") or store_data.get("brand_id") or store_id)
        vendor_id = f"{partner_id}_{int(time.time() * 1000)}"

        summary = _checkout_summary(store_id, vendor_id, [{
            "id": f"{store_id}_{product.product_id}",
            "units": 1,
            "sale_type": "Unit",
            "nodeId": product.product_id,
            "toppings": toppings,
        }], lat, lng, store_data, None if toppings else product.price)

        return _quote(summary, store_id, store_name, store_address, eta_minutes,
                      deep_link=f"https://www.rappi.com.mx/restaurantes/{store_id}?product={product.product_id}",
                      variant_label="Precio base" if product.has_variants else "",
                      is_open=is_open)


    def fetch_cart_price(
        self,
        store_id: str,
        products: list[Product],
        lat: float,
        lng: float,
    ) -> PriceQuote:
        """
        Cotiza múltiples productos en un solo carrito de Rappi.
        Mismo checkout que _fetch_checkout (ver _checkout_summary) pero con N productos.
        """
        data = self._fetch_store(store_id, lat, lng)
        raw_name = data.get("name", "")
        store_name = raw_name.split(" - ", 1)[-1] if " - " in raw_name else raw_name
        store_address = data.get("address", "")
        eta = data.get("eta")
        eta_minutes = int("".join(filter(str.isdigit, str(eta)))) if eta else None
        is_open = data.get("status") == "OPEN"

        partner_id = str(data.get("partner_id") or data.get("brand_id") or store_id)
        vendor_id = f"{partner_id}_{int(time.time() * 1000)}"

        summary = _checkout_summary(store_id, vendor_id, [
            {
                "id": f"{store_id}_{p.product_id}",
                "units": 1,
                "sale_type": "Unit",
                "nodeId": p.product_id,
                "toppings": [],
            }
            for p in products
        ], lat, lng, data, sum(p.price for p in products))

        return _quote(summary, store_id, store_name, store_address, eta_minutes,
                      deep_link=f"https://www.rappi.com.mx/restaurantes/{store_id}", is_open=is_open)


def _clear_cart(headers: dict, store_id: str, vendor_id: str) -> None:
    """Vacía el carrito tras cotizar, para no dejar productos en el carrito de la app."""
    try:
        _http.put(
            f"{_CART_BASE}/v2/restaurant/store",
            headers=headers,
            json=[{"id": int(store_id), "products": [], "vendor": {"id": vendor_id, "type": "rappi", "flow_type": "rappi-web"}}],
            timeout=10,
        )
    except Exception as e:
        print(f"[Rappi] no se pudo vaciar el carrito ({e})")


_TURBO_SUFFIX = re.compile(r"\s*-?\s*\bturbo\b\s*$", re.IGNORECASE)


def _store_display_name(store: dict) -> str:
    """
    Nombre del restaurante: la marca ("McDonald's") y no la sucursal ("Sears Insurgentes",
    "Cibeles"), que es lo que Rappi pone en store_name en muchas ciudades.
    """
    name = store.get("brand_name") or store.get("store_name") or ""
    if not store.get("brand_name") and " - " in name:
        name = name.split(" - ", 1)[-1]  # store_name viene como "41230063 - Little Caesars..."
    return _TURBO_SUFFIX.sub("", name).strip()


def search_stores(query: str, lat: float, lng: float) -> list[dict]:
    """
    Busca restaurantes en Rappi usando unified-search (primario, ~19+ resultados)
    con fallback a unified-suggestions (~4 resultados).
    Retorna lista de dicts con store_id, brand_name, image_url, eta, shipping_cost, rating, matching_products.
    matching_products: lista de productos que coinciden con la búsqueda (nombre, precio, imagen).
    """
    params = {
        "is_prime": "false",
        "unlimited_shipping": "false",
    }
    body = {
        "lat": lat,
        "lng": lng,
        "query": query,
        "options": {},
    }

    headers = _HEADERS_SEARCH

    results = []

    # Intento 1: unified-search (más resultados)
    try:
        resp = _http.post(
            _SEARCH_URL_PRIMARY,
            params=params,
            headers=headers,
            json=body,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        stores = data.get("stores", [])
        for store in stores:
            store_id = str(store.get("store_id", ""))
            if not store_id:
                continue
            name = _store_display_name(store)
            logo = store.get("logo", "")
            image_url = f"{_LOGO_CDN}{logo}" if logo and not logo.startswith("http") else logo
            # Parsear productos que matchean la búsqueda
            matching_products = []
            for p in store.get("products") or []:
                p_name = p.get("name", "")
                p_price = float(p.get("price", 0) or 0)
                p_img = p.get("image", "")
                if p_img and not p_img.startswith("http"):
                    p_img = f"{_IMAGE_CDN}{p_img}"
                if p_name and p_price > 0:
                    matching_products.append({
                        "name": p_name,
                        "price": p_price,
                        "real_price": max(p_price, float(p.get("real_price") or 0)),
                        "image_url": p_img,
                        "product_id": str(p.get("product_id", "")),
                    })
            results.append({
                "store_id": store_id,
                "brand_name": name,
                "image_url": image_url,
                "eta": store.get("eta", ""),
                "shipping_cost": float(store.get("delivery_price", 0) or 0),
                "rating": float(store.get("rating", 0) or 0),
                "matching_products": matching_products,
            })
        if results:
            return results
    except Exception as e:
        print(f"[Rappi] unified-search falló: {e}")

    # Intento 2: unified-suggestions (fallback, menos resultados)
    try:
        resp = _http.post(
            _SEARCH_URL_FALLBACK,
            params=params,
            headers=headers,
            json=body,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("suggestions", []):
            if item.get("type") != "store":
                continue
            store_data = item.get("store", {})
            store_id = str(store_data.get("store_id", ""))
            if not store_id:
                continue
            name = _store_display_name(store_data)
            logo = store_data.get("logo", "")
            image_url = f"{_LOGO_CDN}{logo}" if logo and not logo.startswith("http") else logo
            results.append({
                "store_id": store_id,
                "brand_name": name,
                "image_url": image_url,
                "eta": store_data.get("eta", ""),
                "shipping_cost": float(store_data.get("delivery_price", 0) or 0),
                "rating": float(store_data.get("rating", 0) or 0),
            })
    except Exception as e:
        print(f"[Rappi] unified-suggestions falló: {e}")

    return results


_REST_HOME_URL = "https://services.mxgrability.rappi.com/api/home-router/context/rest-home/content"
_offers_cache = TTLStore(maxsize=4096, ttl=1200, stale_ttl=3600)  # feed por zona de ~2 km, 20 min

# rest-home es un endpoint de la app: pide headers de Android (la sesión de invitado sirve igual)
_HEADERS_APP = {
    "authorization": "",
    "deviceid": RAPPI_DEVICE_ID,
    "app-version": "90037",
    "app-version-name": "8.40.20261001-90037",
    "store-platform": "google",
    "custom_country_code": "MX",
    "country-code": "MX",
    "language": "es",
    "accept-language": "es-MX",
    "user-agent": "Dalvik/2.1.0 (Linux; U; Android 10; YAL-L21 Build/HUAWEIYAL-L21)",
    "accept": "application/json",
    "content-type": "application/json; charset=utf-8",
}
_READ_HEADERS = (_HEADERS, _HEADERS_SEARCH, _HEADERS_APP)  # todos con la sesión de invitado


def _get_rest_home(lat: float, lng: float) -> list[dict]:
    """
    Componentes de la pestaña de restaurantes de la app en la zona: carruseles de productos
    y de tiendas, y la lista de restaurantes cercanos. Una sola petición por zona cada 20 min.
    """
    lat, lng = zone_center(lat, lng)

    def fetch() -> list[dict]:
        body = {
            "context": "rest-home", "stores": [], "offset": 0, "limit": 50,
            "state": {"store_type": "restaurant", "lat": str(lat), "lng": str(lng), "is_prime": "false",
                      "prime": "0", "prime_plan": "none", "unlimited_shipping": "false"},
            "additional_data": None, "store_type": "restaurant",
        }
        r = _http.post(_REST_HOME_URL, headers=_HEADERS_APP, json=body, timeout=20)
        r.raise_for_status()
        data = r.json()
        return (data.get("data") or {}).get("components") or data.get("components") or []
    return _offers_cache.get_or_fetch((lat, lng), fetch)


def fetch_offer_sections(lat: float, lng: float) -> list[dict]:
    """
    Carruseles de productos de la pestaña de restaurantes ("Promos imperdibles",
    "Comidas hasta por $179", ...). Los productos con precio exclusivo de Rappi Pro se
    descartan: un usuario normal paga otro precio. El resto coincide con el menú de la
    tienda (verificado contra store/id).
    """
    sections = []
    for comp in _get_rest_home(lat, lng):
        if comp.get("name") != "TOP_CAROUSEL_PRODUCTS":
            continue
        res = comp.get("resource") or {}
        title = (((res.get("header") or {}).get("title")) or {}).get("text", "")
        items = []
        for p in res.get("products") or []:
            pricing = p.get("pricing") or {}
            price = pricing.get("price")
            if not price or pricing.get("offer_icon") == "pro" or not p.get("is_enabled", True):
                continue
            store = p.get("stores") or {}
            images = p.get("images") or []
            items.append({
                "product_id": str(p["id"]),
                "name": p.get("title", ""),
                "image_url": images[0] if images else "",
                "price": float(price),
                "real_price": max(float(price), float(pricing.get("original_price") or 0)),
                "store_id": str(p["store_id"]),
                "store_name": store.get("title", ""),
                "eta": store.get("subtitle", ""),
            })
        if title and items:
            sections.append({"title": title, "platform": "rappi", "kind": "products", "items": items})
    if not sections:
        # Los carruseles dependen de la hora (de noche casi no hay): respaldo con los menús
        menu_offers = _offers_from_menus(lat, lng)
        if menu_offers:
            sections.append({"title": "Ofertas cerca de ti", "platform": "rappi", "kind": "products",
                             "items": menu_offers})
    return sections


_MENU_OFFER_STORES = 8  # menús a revisar por zona (cada 20 min, compartido por toda la zona)


def _offers_from_menus(lat: float, lng: float) -> list[dict]:
    """Productos en oferta (sin Pro) de los menús de los restaurantes cercanos, los mayores descuentos primero."""
    zlat, zlng = zone_center(lat, lng)

    def fetch() -> list[dict]:
        connector = RappiConnector()
        items = []
        for st in fetch_nearby_stores(zlat, zlng)[:_MENU_OFFER_STORES]:
            try:
                data = connector._fetch_store(st["store_id"], zlat, zlng)
            except Exception as e:
                logger.info("Rappi: menú %s para ofertas falló (%s)", st["store_id"], e)
                continue
            if data.get("status") != "OPEN":
                continue
            seen: set[str] = set()
            for corridor in data.get("corridors", []):
                for p in corridor.get("products", []):
                    pid = str(p["product_id"])
                    offer = _offer_price(p)
                    if offer is None or pid in seen:
                        continue
                    seen.add(pid)
                    items.append({
                        "product_id": pid,
                        "name": p["name"],
                        "image_url": _rappi_image(p.get("image", "")),
                        "price": offer,
                        "real_price": float(p["price"]),
                        "store_id": st["store_id"],
                        "store_name": st["brand_name"],
                        "eta": str(data.get("eta") or ""),
                    })
        items.sort(key=lambda it: it["price"] / it["real_price"])
        per_store: dict[str, int] = {}
        picked = []
        for it in items:  # máximo 4 por tienda, para que no sea solo un restaurante
            if per_store.get(it["store_id"], 0) < 4:
                per_store[it["store_id"]] = per_store.get(it["store_id"], 0) + 1
                picked.append(it)
        return picked[:20]
    return _offers_cache.get_or_fetch(("menu-offers", zlat, zlng), fetch)


def fetch_nearby_stores(lat: float, lng: float) -> list[dict]:
    """Restaurantes de Rappi que entregan en la zona (de la misma respuesta en caché)."""
    stores: dict[str, dict] = {}
    for comp in _get_rest_home(lat, lng):
        if comp.get("name") not in ("STORE_CARD", "TOP_CAROUSEL"):
            continue
        for st in (comp.get("resource") or {}).get("stores") or []:
            store_id = str(st.get("store_id") or "")
            if not store_id or store_id in stores or st.get("store_type") not in (None, "restaurant"):
                continue
            backgrounds = st.get("background_images") or []
            stores[store_id] = {
                "store_id": store_id,
                "store_name": (st.get("store_name") or "").strip(),
                "brand_name": (st.get("brand_name") or st.get("store_name") or "").strip(),
                "image_url": (backgrounds[0].get("image") if backgrounds else "") or st.get("logo") or "",
            }
    return list(stores.values())
