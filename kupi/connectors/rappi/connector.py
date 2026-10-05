import logging
import time
import requests

logger = logging.getLogger(__name__)
from kupi.connectors.base import BaseConnector
from kupi.core.config import RAPPI_TOKEN, RAPPI_DEVICE_ID, RAPPI_AUTH_USER
from kupi.core.models import Product, PriceQuote, CartItemDetail

_HEADERS = {
    "authorization": f"Bearer {RAPPI_TOKEN}",
    "app-version": "1.162.2",
    "deviceid": RAPPI_DEVICE_ID,
    "content-type": "application/json; charset=UTF-8",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "accept": "application/json",
    "accept-language": "es-MX",
    "origin": "https://www.rappi.com.mx",
    "referer": "https://www.rappi.com.mx/",
}

_STORE_URL = "https://services.mxgrability.rappi.com/api/web-gateway/web/restaurants-bus/store/id"
_CART_BASE = "https://services.mxgrability.rappi.com/api/ms/shopping-cart"
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


class RappiConnector(BaseConnector):

    def _fetch_store(self, store_id: str, lat: float, lng: float) -> dict:
        url = f"{_STORE_URL}/{store_id}/"
        body = {
            "lat": lat,
            "lng": lng,
            "store_type": "restaurant",
            "is_prime": False,
            "prime_config": {"unlimited_shipping": False},
        }
        resp = requests.post(url, headers=_HEADERS, json=body, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def fetch_menu(self, store_id: str, lat: float, lng: float) -> list[Product]:
        data = self._fetch_store(store_id, lat, lng)
        # Si la tienda no está disponible para delivery, no devolver productos
        if data.get("status") != "OPEN":
            logger.info("Rappi store %s no disponible (status=%s)", store_id, data.get("status"))
            return []
        products = []
        for corridor in data.get("corridors", []):
            for p in corridor.get("products", []):
                products.append(Product(
                    product_id=str(p["product_id"]),
                    name=p["name"],
                    price=float(p["price"]),
                    real_price=float(p.get("real_price", p["price"])),
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
        delivery_fee = float(data.get("delivery_price", 0))
        eta = data.get("eta")
        eta_minutes = int("".join(filter(str.isdigit, str(eta)))) if eta else None
        raw_name = data.get("name", "")
        # Rappi devuelve el nombre como "41230063 - Little Caesars Nicolas Bravo" — quitar el prefijo numérico
        store_name = raw_name.split(" - ", 1)[-1] if " - " in raw_name else raw_name
        store_address = data.get("address", "")
        is_open = data.get("status") == "OPEN"

        # Siempre intentar checkout real para obtener envío y service fee con promos aplicadas
        try:
            return self._fetch_checkout(
                store_id=store_id,
                product=product,
                lat=lat,
                lng=lng,
                toppings=toppings or [],
                store_data=data,
                eta_minutes=eta_minutes,
                is_open=is_open,
            )
        except Exception as e:
            # Si falla (ej. producto con personalización obligatoria), caer al precio del menú
            # ADVERTENCIA: el fallback NO tiene service_fee ni envío real — el total será inexacto
            print(f"[Rappi] checkout falló ({e}), usando precio de menú — TOTAL SERÁ INEXACTO")

        return PriceQuote(
            platform="rappi",
            product_price=product.price,
            delivery_fee=delivery_fee,
            service_fee=0.0,
            total=product.price + delivery_fee,
            eta_minutes=eta_minutes,
            deep_link=f"https://www.rappi.com.mx/restaurantes/{store_id}?product={product.product_id}",
            store_name=store_name,
            store_address=store_address,
            variant_label="Precio base" if product.has_variants else "",
            is_open=is_open,
            is_estimate=True,
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
        """
        Simula el checkout de Rappi en 3 pasos para obtener el desglose real:
          1. PUT  /v2/restaurant/store     - pone el producto en el carrito
          2. POST /v1/restaurant/recalculate - recalcula precios y fees
          3. GET  /v1/restaurant/summary-v2  - desglose completo (envío, servicio, descuentos)
        """
        raw_name = store_data.get("name", "")
        store_name = raw_name.split(" - ", 1)[-1] if " - " in raw_name else raw_name
        store_address = store_data.get("address", "")

        # Extraer partner_id del store si está disponible, sino usar el store_id
        partner_id = str(store_data.get("partner_id") or store_data.get("brand_id") or store_id)
        timestamp_ms = int(time.time() * 1000)
        vendor_id = f"{partner_id}_{timestamp_ms}"

        # Paso 1 - PUT carrito (reintenta una vez si hay 409 por carrito previo activo)
        product_entry_id = f"{store_id}_{product.product_id}"
        cart_body = [{
            "id": int(store_id),
            "products": [{
                "id": product_entry_id,
                "units": 1,
                "sale_type": "Unit",
                "nodeId": product.product_id,
                "toppings": toppings,
            }],
            "vendor": {
                "id": vendor_id,
                "type": "rappi",
                "flow_type": "rappi-web",
            },
        }]
        r1 = requests.put(
            f"{_CART_BASE}/v2/restaurant/store",
            headers=_HEADERS,
            json=cart_body,
            timeout=10,
        )
        if r1.status_code == 409:
            # Carrito previo activo - vaciarlo y reintentar
            time.sleep(0.5)
            requests.put(
                f"{_CART_BASE}/v2/restaurant/store",
                headers=_HEADERS,
                json=[{"id": int(store_id), "products": [], "vendor": {"id": vendor_id, "type": "rappi", "flow_type": "rappi-web"}}],
                timeout=10,
            )
            time.sleep(0.3)
            r1 = requests.put(
                f"{_CART_BASE}/v2/restaurant/store",
                headers=_HEADERS,
                json=cart_body,
                timeout=10,
            )
        r1.raise_for_status()

        # Paso 2a - cambiar dirección de entrega a la del usuario
        addr_body = {
            "lat": lat,
            "lng": lng,
            "description": "",
        }
        try:
            ra = requests.post(
                f"{_CART_BASE}/v1/restaurant/change-address",
                headers=_HEADERS,
                json=addr_body,
                timeout=10,
            )
            ra.raise_for_status()
        except Exception as e:
            print(f"[Rappi] change-address falló ({e}), continuando con recalculate")

        # Paso 2b - recalcular con la nueva dirección
        r2 = requests.post(
            f"{_CART_BASE}/v1/restaurant/recalculate",
            headers=_HEADERS,
            json={},
            timeout=10,
        )
        r2.raise_for_status()

        # Paso 3 - summary-v2 con desglose completo
        r3 = requests.get(
            f"{_CART_BASE}/v1/restaurant/summary-v2",
            headers=_HEADERS,
            timeout=10,
        )
        r3.raise_for_status()
        summary = r3.json()

        return _parse_summary(summary, product, store_id, store_name, store_address, eta_minutes,
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
        Mismo flujo de 4 pasos que _fetch_checkout pero con N productos.
        """
        data = self._fetch_store(store_id, lat, lng)
        raw_name = data.get("name", "")
        store_name = raw_name.split(" - ", 1)[-1] if " - " in raw_name else raw_name
        store_address = data.get("address", "")
        eta = data.get("eta")
        eta_minutes = int("".join(filter(str.isdigit, str(eta)))) if eta else None
        is_open = data.get("status") == "OPEN"

        partner_id = str(data.get("partner_id") or data.get("brand_id") or store_id)
        timestamp_ms = int(time.time() * 1000)
        vendor_id = f"{partner_id}_{timestamp_ms}"

        # Paso 1 - PUT carrito con N productos
        cart_products = [
            {
                "id": f"{store_id}_{p.product_id}",
                "units": 1,
                "sale_type": "Unit",
                "nodeId": p.product_id,
                "toppings": [],
            }
            for p in products
        ]
        cart_body = [{
            "id": int(store_id),
            "products": cart_products,
            "vendor": {
                "id": vendor_id,
                "type": "rappi",
                "flow_type": "rappi-web",
            },
        }]
        r1 = requests.put(
            f"{_CART_BASE}/v2/restaurant/store",
            headers=_HEADERS,
            json=cart_body,
            timeout=10,
        )
        if r1.status_code == 409:
            time.sleep(0.5)
            requests.put(
                f"{_CART_BASE}/v2/restaurant/store",
                headers=_HEADERS,
                json=[{"id": int(store_id), "products": [], "vendor": {"id": vendor_id, "type": "rappi", "flow_type": "rappi-web"}}],
                timeout=10,
            )
            time.sleep(0.3)
            r1 = requests.put(
                f"{_CART_BASE}/v2/restaurant/store",
                headers=_HEADERS,
                json=cart_body,
                timeout=10,
            )
        r1.raise_for_status()

        # Paso 2a - cambiar dirección
        try:
            requests.post(
                f"{_CART_BASE}/v1/restaurant/change-address",
                headers=_HEADERS,
                json={"lat": lat, "lng": lng, "description": ""},
                timeout=10,
            ).raise_for_status()
        except Exception as e:
            print(f"[Rappi] cart change-address falló ({e}), continuando")

        # Paso 2b - recalcular
        requests.post(
            f"{_CART_BASE}/v1/restaurant/recalculate",
            headers=_HEADERS,
            json={},
            timeout=10,
        ).raise_for_status()

        # Paso 3 - summary
        r3 = requests.get(
            f"{_CART_BASE}/v1/restaurant/summary-v2",
            headers=_HEADERS,
            timeout=10,
        )
        r3.raise_for_status()
        summary = r3.json()

        return _parse_cart_summary(summary, products, store_id, store_name, store_address, eta_minutes, is_open)


def _parse_cart_summary(
    summary: dict,
    products: list[Product],
    store_id: str,
    store_name: str,
    store_address: str,
    eta_minutes: int | None,
    is_open: bool = True,
) -> PriceQuote:
    """Parsea summary-v2 para un carrito multi-producto."""
    product_price = sum(p.price for p in products)
    delivery_fee = 0.0
    service_fee = 0.0
    extra_fees = 0.0

    for section in summary.get("summary", []):
        for sub in (section.get("sub_value") or []):
            t = sub.get("type")
            val = float(sub.get("raw_value") or 0)
            if t == "product_total":
                product_price = val
            elif t == "shipping":
                delivery_fee = val
            elif t == "service_fee":
                service_fee = val
            elif t == "tip" or t is None:
                pass
            else:
                extra_fees += val

    delivery_fee += extra_fees
    total = product_price + delivery_fee + service_fee

    items = [CartItemDetail(product_id=p.product_id, name=p.name, price=p.price) for p in products]

    return PriceQuote(
        platform="rappi",
        product_price=product_price,
        delivery_fee=delivery_fee,
        service_fee=service_fee,
        total=total,
        eta_minutes=eta_minutes,
        deep_link=f"https://www.rappi.com.mx/restaurantes/{store_id}",
        store_name=store_name,
        store_address=store_address,
        is_open=is_open,
    )


def _parse_summary(
    summary: dict,
    product: Product,
    store_id: str,
    store_name: str,
    store_address: str,
    eta_minutes: int | None,
    variant_label: str = "",
    is_open: bool = True,
) -> PriceQuote:
    """
    Parsea summary-v2 usando los sub_value del Total (más precisos que fees[]):
      type="product_total" → precio con descuento
      type="shipping"      → costo de envío real (0 si hay promo de envío gratis)
      type="service_fee"   → tarifa de servicio
      type="tip"           → propina (se excluye - es opcional del usuario)
    Cualquier otro tipo de fee (ej. tarifa de entrega extendida) se suma a delivery_fee.
    """
    product_price = product.price
    delivery_fee = 0.0
    service_fee = 0.0
    extra_fees = 0.0

    for section in summary.get("summary", []):
        for sub in (section.get("sub_value") or []):
            t = sub.get("type")
            val = float(sub.get("raw_value") or 0)
            if t == "product_total":
                product_price = val
            elif t == "shipping":
                delivery_fee = val
            elif t == "service_fee":
                service_fee = val
            elif t == "tip" or t is None:
                pass
            else:
                logger.info("rappi summary sub_value tipo desconocido: %s = %s", t, val)
                extra_fees += val

    delivery_fee += extra_fees
    total = product_price + delivery_fee + service_fee

    return PriceQuote(
        platform="rappi",
        product_price=product_price,
        delivery_fee=delivery_fee,
        service_fee=service_fee,
        total=total,
        eta_minutes=eta_minutes,
        deep_link=f"https://www.rappi.com.mx/restaurantes/{store_id}?product={product.product_id}",
        store_name=store_name,
        store_address=store_address,
        variant_label=variant_label,
        is_open=is_open,
    )


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

    headers = {**_HEADERS_SEARCH}
    if RAPPI_AUTH_USER:
        headers["auth_user"] = RAPPI_AUTH_USER

    results = []

    # Intento 1: unified-search (más resultados)
    try:
        resp = requests.post(
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
            name = store.get("store_name", "")
            # Quitar prefijo numérico "41230063 - Little Caesars..."
            if " - " in name:
                name = name.split(" - ", 1)[-1]
            logo = store.get("logo", "")
            image_url = f"{_LOGO_CDN}{logo}" if logo and not logo.startswith("http") else logo
            # Parsear productos que matchean la búsqueda
            matching_products = []
            for p in store.get("products", []):
                p_name = p.get("name", "")
                p_price = float(p.get("price", 0) or 0)
                p_img = p.get("image", "")
                if p_img and not p_img.startswith("http"):
                    p_img = f"{_IMAGE_CDN}{p_img}"
                if p_name and p_price > 0:
                    matching_products.append({
                        "name": p_name,
                        "price": p_price,
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
        resp = requests.post(
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
            name = store_data.get("store_name", "")
            if " - " in name:
                name = name.split(" - ", 1)[-1]
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
