import json
import logging
import os
import re
import urllib.parse
import uuid as uuid_lib
import requests as _requests
from curl_cffi import requests
from kupi.connectors.base import BaseConnector
from kupi.core.cache import PlatformHealth, Throttle, TTLStore, loc_key, zone_center
from kupi.core.config import UBEREATS_COOKIE_STRING
from kupi.core.models import Product, PriceQuote, CartItemDetail

logger = logging.getLogger(__name__)

_throttle = Throttle(0.35)                      # espacio mínimo entre peticiones a Uber Eats
health = PlatformHealth("Uber Eats")
_store_cache = TTLStore(maxsize=512, ttl=300)   # getStoreV1, 5 min
_quote_cache = TTLStore(maxsize=1024, ttl=300)  # cotizaciones (draft + checkout), 5 min

_BASE_URL = "https://www.ubereats.com/_p/api"
_WORKER_URL = os.getenv("UBEREATS_WORKER_URL", "")
_WORKER_SECRET = os.getenv("UBEREATS_WORKER_SECRET", "")

_HEADERS_BASE = {
    "accept": "*/*",
    "accept-language": "es-419,es;q=0.5",
    "content-type": "application/json",
    "origin": "https://www.ubereats.com",
    "priority": "u=1, i",
    "sec-ch-ua": '"Brave";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "sec-gpc": "1",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "x-csrf-token": "x",
    "x-uber-client-gitref": "1732c3b88979083c69bf194084b10b1d475ff81d",
}


def _parse_cookies(cookie_string: str) -> dict[str, str]:
    cookies = {}
    for part in cookie_string.split(";"):
        part = part.strip()
        if "=" in part:
            name, value = part.split("=", 1)
            cookies[name.strip()] = value.strip()
    return cookies


_LOC_COOKIE = re.compile(r"(^|;\s*)uev2\.loc=[^;]*")
_place_cache = TTLStore(maxsize=2048, ttl=86400)  # lugar de Uber Eats por zona de ~110 m, 24 h


def _cookie_for(lat: float, lng: float, place: dict | None = None) -> str:
    """
    Cookies de la sesión con la ubicación del usuario. Uber Eats toma la ubicación del feed,
    la búsqueda y la dirección de entrega de los borradores de la cookie uev2.loc (ignora los
    headers x-uber-*-location), así que se reescribe con las coordenadas de cada petición.
    Los borradores además exigen la referencia de un lugar (si no, 401): ver _place_at.
    """
    place = place or {}
    line1, line2 = place.get("addressLine1", ""), place.get("addressLine2", "")
    loc = {
        "address": {"address1": line1, "address2": line2, "aptOrSuite": "",
                    "eaterFormattedAddress": ", ".join(x for x in (line1, line2) if x),
                    "subtitle": line2, "title": line1, "uuid": ""},
        "latitude": lat, "longitude": lng,
        "reference": place.get("id", ""), "referenceType": place.get("provider", ""), "type": place.get("provider", ""),
        "addressComponents": {}, "categories": place.get("categories", []),
        "originType": "user_autocomplete" if place else "",
    }
    value = urllib.parse.quote(json.dumps(loc, separators=(",", ":")))
    cookie, n = _LOC_COOKIE.subn(lambda m: f"{m.group(1)}uev2.loc={value}", UBEREATS_COOKIE_STRING)
    return cookie if n else f"{UBEREATS_COOKIE_STRING}; uev2.loc={value}"


def _headers(lat: float, lng: float, cookie: str, referer: str) -> dict:
    return {
        **_HEADERS_BASE,
        "cookie": cookie,
        "referer": referer,
        "x-uber-device-location-latitude": str(lat),
        "x-uber-device-location-longitude": str(lng),
        "x-uber-target-location-latitude": str(lat),
        "x-uber-target-location-longitude": str(lng),
    }


def _place_at(lat: float, lng: float) -> dict:
    """
    Lugar de Uber Eats en las coordenadas (mapsSearchV1 con "lat,lng" devuelve el lugar que
    está en ese punto). Es la referencia que exigen los borradores para cotizar la entrega.
    """
    def fetch() -> dict:
        data = _call_ubereats(
            f"{_BASE_URL}/mapsSearchV1?localeCode=mx",
            _headers(lat, lng, _cookie_for(lat, lng), "https://www.ubereats.com/"),
            {"query": f"{lat},{lng}"},
        )
        places = data.get("data") or []
        return places[0] if places else {}
    return _place_cache.get_or_fetch(loc_key(lat, lng), fetch)


def _build_headers(lat: float, lng: float, referer: str = "https://www.ubereats.com/", with_place: bool = False) -> dict:
    """
    Headers con cookies y ubicación. Solo los borradores (cotizar) necesitan la referencia del
    lugar: menús, feed y búsqueda funcionan sin ella y así no cuestan una consulta extra.
    """
    place = None
    if with_place:
        try:
            place = _place_at(lat, lng)
        except Exception as e:
            logger.warning("Uber Eats: no se pudo obtener el lugar en (%.4f, %.4f): %s", lat, lng, e)
    return _headers(lat, lng, _cookie_for(lat, lng, place), referer)


def _build_session(lat: float, lng: float) -> requests.Session:
    """Crea una sesión con cookies y headers de ubicación listos (uso local)."""
    session = requests.Session()
    cookies = _parse_cookies(UBEREATS_COOKIE_STRING)
    for name, value in cookies.items():
        session.cookies.set(name, value, domain=".ubereats.com")
    session.headers.update({
        **_HEADERS_BASE,
        "x-uber-device-location-latitude": str(lat),
        "x-uber-device-location-longitude": str(lng),
        "x-uber-target-location-latitude": str(lat),
        "x-uber-target-location-longitude": str(lng),
    })
    return session


def _auto_customizations(store_id: str, product: Product, lat: float, lng: float) -> tuple[dict, str]:
    """
    Llama a getMenuItemV1 para obtener los grupos de personalización del producto
    y auto-selecciona la primera opción de cada grupo requerido.
    Devuelve (customizations_dict, variant_label) donde variant_label es el nombre
    de la primera opción seleccionada, ej. "6 Piezas".
    """
    headers = _build_headers(lat, lng)
    body = {
        "sectionUuid": product.section_uuid,
        "subsectionUuid": product.subsection_uuid,
        "itemUuid": product.product_id,
        "storeUuid": store_id,
    }
    try:
        data = _call_ubereats(f"{_BASE_URL}/getMenuItemV1?localeCode=mx", headers, body)
        item = data.get("data", {}).get("catalogItem", {})
        groups = item.get("itemCustomizationList", []) or item.get("customizationList", [])
        result = {"customizationGroups": []}
        labels = []
        for group in groups:
            options = group.get("options") or group.get("optionList") or []
            if not options:
                continue
            first = options[0]
            label = first.get("title") or first.get("name") or ""
            if label:
                labels.append(label)
            result["customizationGroups"].append({
                "customizationGroupId": group.get("id") or group.get("customizationGroupId", ""),
                "selectedOptions": [{
                    "optionId": first.get("id") or first.get("optionId", ""),
                    "quantity": 1,
                }],
            })
        return result, ", ".join(labels)
    except Exception:
        return {}, ""


def _call_ubereats(url: str, headers: dict, body: dict) -> dict:
    """
    Llama a UberEats. Si hay un Worker configurado, lo usa como proxy
    (evita el bloqueo de IPs de AWS). Si no, llama directo con curl_cffi.
    """
    if not health.allow():
        raise RuntimeError("Uber Eats no está respondiendo por ahora")
    _throttle.wait()
    if _WORKER_URL and _WORKER_SECRET:
        resp = _requests.post(
            _WORKER_URL,
            json={"url": url, "method": "POST", "headers": headers, "body": body},
            headers={"x-kupi-secret": _WORKER_SECRET},
            timeout=20,
        )
    else:
        # Desarrollo local: llamada directa con curl_cffi
        resp = requests.post(url, json=body, headers=headers, impersonate="chrome120", timeout=20)
    health.record(resp.status_code)
    resp.raise_for_status()
    return resp.json()


def _get_store(store_id: str, lat: float, lng: float) -> dict:
    """getStoreV1 (catálogo, nombre, dirección y horario de la tienda), en caché 5 min."""
    def fetch() -> dict:
        body = {"storeUuid": store_id, "diningMode": "DELIVERY", "time": {"asap": True}, "cbType": "EATER_ENDORSED"}
        data = _call_ubereats(f"{_BASE_URL}/getStoreV1?localeCode=mx", _build_headers(lat, lng), body)
        if data.get("status") != "success":
            raise RuntimeError(f"getStoreV1 falló: {data.get('data', {}).get('errorMessage', 'unknown')}")
        return data["data"]
    return _store_cache.get_or_fetch((store_id, loc_key(lat, lng, 2)), fetch)


def _discard_draft(draft_order_uuid: str, store_id: str, lat: float, lng: float) -> None:
    """Borra el draft order: Uber Eats limita cuántos carritos abiertos tiene una cuenta."""
    try:
        _call_ubereats(
            f"{_BASE_URL}/discardDraftOrdersV1?localeCode=mx",
            _build_headers(lat, lng),
            {"draftOrderUUIDs": [draft_order_uuid], "storeUUID": store_id},
        )
    except Exception as e:
        logger.warning("No se pudo borrar el draft %s: %s", draft_order_uuid, e)


class UberEatsConnector(BaseConnector):

    def fetch_menu(self, store_id: str, lat: float, lng: float) -> list[Product]:
        """
        Llama a getStoreV1 y parsea el catálogo completo.
        Guarda section_uuid y subsection_uuid por producto (necesarios para cotizar).
        """
        return _parse_menu(_get_store(store_id, lat, lng))

    def fetch_price(self, store_id: str, product: Product, lat: float, lng: float) -> PriceQuote:
        key = ("price", store_id, product.product_id, loc_key(lat, lng))
        return _quote_cache.get_or_fetch(key, lambda: self._fetch_price(store_id, product, lat, lng))

    def _fetch_price(self, store_id: str, product: Product, lat: float, lng: float) -> PriceQuote:
        """
        Cotiza el precio real en 2 pasos:
          1. createDraftOrderV2  → obtiene draftOrderUUID
          2. getCheckoutPresentationV1 → desglose: producto + envío + cuota de servicio
        Reutiliza el getStoreV1 (ya llamado en fetch_menu) para obtener nombre y dirección.
        """
        # Obtener nombre y dirección de la tienda
        try:
            store_data = _get_store(store_id, lat, lng)
        except RuntimeError:
            store_data = {}
        store_name = store_data.get("title", "")
        store_address = store_data.get("location", {}).get("address", "")
        is_open = store_data.get("isOpen", True) and store_data.get("isOrderable", True)
        opens_at = store_data.get("closedMessage", "") if not is_open else ""

        # Construir el referer con el quickView del producto específico
        modctx = json.dumps({
            "storeUuid": store_id,
            "sectionUuid": product.section_uuid,
            "subsectionUuid": product.subsection_uuid,
            "itemUuid": product.product_id,
            "showSeeDetailsCTA": True,
        })
        modctx_encoded = urllib.parse.quote(urllib.parse.quote(modctx))  # doble encode para el header
        modctx_deep = urllib.parse.quote(modctx)  # encode simple para el deep link
        referer = (
            f"https://www.ubereats.com/mx/store/store/{store_id}"
            f"?diningMode=DELIVERY&mod=quickView&modctx={modctx_encoded}"
        )
        deep_link_ue = (
            f"https://www.ubereats.com/mx/store/store/{store_id}"
            f"?diningMode=DELIVERY&mod=quickView&modctx={modctx_deep}"
        )
        # Paso 1 - crear draft order
        create_body = {
            "isMulticart": True,
            "shoppingCartItems": [{
                "uuid": product.product_id,
                "shoppingCartItemUuid": str(uuid_lib.uuid4()),
                "storeUuid": store_id,
                "sectionUuid": product.section_uuid,
                "subsectionUuid": product.subsection_uuid,
                "price": int(product.price * 100),  # centavos
                "title": product.name,
                "quantity": 1,
                "customizations": product.customizations,
                "imageURL": product.image_url,
                "specialInstructions": "",
                "itemId": None,
            }],
            "useCredits": True,
            "extraPaymentProfiles": [],
            "promotionOptions": {
                "autoApplyPromotionUUIDs": [],
                "selectedPromotionInstanceUUIDs": [],
                "skipApplyingPromotion": False,
            },
            "deliveryTime": {"asap": True},
            "deliveryType": "ASAP",
            "currencyCode": "MXN",
            "interactionType": "door_to_door",
            "checkMultipleDraftOrdersCap": True,
            "actionMeta": {"isQuickAdd": False, "numClicks": 1},
            "businessDetails": {},
        }
        variant_label = ""
        data1 = _call_ubereats(f"{_BASE_URL}/createDraftOrderV2?localeCode=mx", _build_headers(lat, lng, referer, with_place=True), create_body)
        if data1.get("status") != "success":
            # Puede fallar por customizaciones obligatorias vacías — obtenerlas y reintentar
            auto_custom, variant_label = _auto_customizations(store_id, product, lat, lng)
            if auto_custom:
                create_body["shoppingCartItems"][0]["customizations"] = auto_custom
                create_body["shoppingCartItems"][0]["shoppingCartItemUuid"] = str(uuid_lib.uuid4())
                data1 = _call_ubereats(f"{_BASE_URL}/createDraftOrderV2?localeCode=mx", _build_headers(lat, lng, referer, with_place=True), create_body)
            if data1.get("status") != "success":
                raise RuntimeError(f"createDraftOrderV2 falló: {data1}")

        draft_order_uuid = data1["data"]["draftOrder"]["uuid"]

        # Paso 2 - obtener desglose de precios
        checkout_body = {
            "draftOrderUUID": draft_order_uuid,
            "isGroupOrder": False,
            "webGiftingPersonalizationEnabled": True,
            "clientFeaturesData": {
                "paymentSelectionContext": {
                    "value": '{"deviceContext":{"thirdPartyApplications":[]}}'
                }
            },
            "payloadTypes": [
                "canonicalProductStorePickerPayload",
                "total",
                "subtotal",
                "fareBreakdown",
                "deliveryOptInInfo",
                "paymentProfilesEligibility",
                "requestUtensilPayload",
                "versionMetadata",
            ],
        }
        try:
            data2 = _call_ubereats(f"{_BASE_URL}/getCheckoutPresentationV1?localeCode=mx", _build_headers(lat, lng, referer, with_place=True), checkout_body)
        finally:
            _discard_draft(draft_order_uuid, store_id, lat, lng)
        if data2.get("status") != "success":
            raise RuntimeError(f"getCheckoutPresentationV1 falló: {data2}")

        checkout_data = data2["data"]
        return _parse_checkout(checkout_data, product, store_id, store_name, store_address, deep_link=deep_link_ue, variant_label=variant_label, is_open=is_open, opens_at=opens_at)


    def fetch_cart_price(
        self,
        store_id: str,
        products: list[Product],
        lat: float,
        lng: float,
    ) -> PriceQuote:
        key = ("cart", store_id, tuple(p.product_id for p in products), loc_key(lat, lng))
        return _quote_cache.get_or_fetch(key, lambda: self._fetch_cart_price(store_id, products, lat, lng))

    def _fetch_cart_price(
        self,
        store_id: str,
        products: list[Product],
        lat: float,
        lng: float,
    ) -> PriceQuote:
        """
        Cotiza múltiples productos en un solo draft order de Uber Eats.
        Mismos 2 pasos que fetch_price pero con N items en shoppingCartItems.
        """
        try:
            store_data = _get_store(store_id, lat, lng)
        except RuntimeError:
            store_data = {}
        store_name = store_data.get("title", "")
        store_address = store_data.get("location", {}).get("address", "")
        is_open = store_data.get("isOpen", True) and store_data.get("isOrderable", True)
        opens_at = store_data.get("closedMessage", "") if not is_open else ""

        referer = f"https://www.ubereats.com/mx/store/store/{store_id}?diningMode=DELIVERY"
        deep_link = referer

        # Paso 1 - crear draft order con N items
        cart_items = []
        for p in products:
            cart_items.append({
                "uuid": p.product_id,
                "shoppingCartItemUuid": str(uuid_lib.uuid4()),
                "storeUuid": store_id,
                "sectionUuid": p.section_uuid,
                "subsectionUuid": p.subsection_uuid,
                "price": int(p.price * 100),
                "title": p.name,
                "quantity": 1,
                "customizations": p.customizations,
                "imageURL": p.image_url,
                "specialInstructions": "",
                "itemId": None,
            })

        create_body = {
            "isMulticart": True,
            "shoppingCartItems": cart_items,
            "useCredits": True,
            "extraPaymentProfiles": [],
            "promotionOptions": {
                "autoApplyPromotionUUIDs": [],
                "selectedPromotionInstanceUUIDs": [],
                "skipApplyingPromotion": False,
            },
            "deliveryTime": {"asap": True},
            "deliveryType": "ASAP",
            "currencyCode": "MXN",
            "interactionType": "door_to_door",
            "checkMultipleDraftOrdersCap": True,
            "actionMeta": {"isQuickAdd": False, "numClicks": 1},
            "businessDetails": {},
        }

        data1 = _call_ubereats(f"{_BASE_URL}/createDraftOrderV2?localeCode=mx", _build_headers(lat, lng, referer, with_place=True), create_body)
        if data1.get("status") != "success":
            # Reintentar con auto-customizaciones por cada producto que lo necesite
            for i, p in enumerate(products):
                auto_custom, _ = _auto_customizations(store_id, p, lat, lng)
                if auto_custom:
                    create_body["shoppingCartItems"][i]["customizations"] = auto_custom
                    create_body["shoppingCartItems"][i]["shoppingCartItemUuid"] = str(uuid_lib.uuid4())
            data1 = _call_ubereats(f"{_BASE_URL}/createDraftOrderV2?localeCode=mx", _build_headers(lat, lng, referer, with_place=True), create_body)
            if data1.get("status") != "success":
                raise RuntimeError(f"createDraftOrderV2 cart falló: {data1}")

        draft_order_uuid = data1["data"]["draftOrder"]["uuid"]

        # Paso 2 - checkout
        checkout_body = {
            "draftOrderUUID": draft_order_uuid,
            "isGroupOrder": False,
            "webGiftingPersonalizationEnabled": True,
            "clientFeaturesData": {
                "paymentSelectionContext": {
                    "value": '{"deviceContext":{"thirdPartyApplications":[]}}'
                }
            },
            "payloadTypes": [
                "canonicalProductStorePickerPayload",
                "total",
                "subtotal",
                "fareBreakdown",
                "deliveryOptInInfo",
                "paymentProfilesEligibility",
                "requestUtensilPayload",
                "versionMetadata",
            ],
        }
        try:
            data2 = _call_ubereats(f"{_BASE_URL}/getCheckoutPresentationV1?localeCode=mx", _build_headers(lat, lng, referer, with_place=True), checkout_body)
        finally:
            _discard_draft(draft_order_uuid, store_id, lat, lng)
        if data2.get("status") != "success":
            raise RuntimeError(f"getCheckoutPresentationV1 cart falló: {data2}")

        return _parse_cart_checkout(data2["data"], products, store_id, store_name, store_address, deep_link, is_open, opens_at)


def _parse_cart_checkout(
    checkout_data: dict,
    products: list[Product],
    store_id: str,
    store_name: str,
    store_address: str,
    deep_link: str,
    is_open: bool,
    opens_at: str,
) -> PriceQuote:
    """Parsea el checkout para un carrito multi-producto."""
    payloads = checkout_data.get("checkoutPayloads", {})
    charges = payloads.get("fareBreakdown", {}).get("charges", [])

    delivery_fee = 0.0
    service_fee = 0.0

    for charge in charges:
        fare_id = charge.get("fareBreakdownChargeMetadata", {}).get("fareInfoID", "")
        amount = _parse_money_text(charge.get("value", {}).get("text", ""))
        if fare_id == "eats_fare.delivery_fee":
            delivery_fee = amount
        elif "service_fee" in fare_id or "basket_dependent_fee" in fare_id or "tax_and_fees" in fare_id:
            service_fee += amount

    product_price = sum(p.price for p in products)
    checkout_total = _parse_money_text(payloads.get("total", {}).get("value", {}).get("text", ""))
    if checkout_total > 0:
        total = checkout_total
        service_fee = round(total - product_price - delivery_fee, 2)
        if service_fee < 0:
            service_fee = 0.0
    else:
        total = product_price + delivery_fee + service_fee

    items = [CartItemDetail(product_id=p.product_id, name=p.name, price=p.price) for p in products]

    return PriceQuote(
        platform="ubereats",
        product_price=product_price,
        delivery_fee=delivery_fee,
        service_fee=service_fee,
        total=total,
        deep_link=deep_link,
        store_name=store_name,
        store_address=store_address,
        is_open=is_open,
        opens_at=opens_at,
    )


def _parse_menu(store_data: dict) -> list[Product]:
    products = []
    catalog_map = store_data.get("catalogSectionsMap", {})
    for section_uuid, subsections in catalog_map.items():
        for subsection in subsections:
            subsection_uuid = subsection.get("catalogSectionUUID", "")
            items = (
                subsection.get("payload", {})
                .get("standardItemsPayload", {})
                .get("catalogItems", [])
            )
            for item in items:
                price = item.get("price", 0) / 100
                products.append(Product(
                    product_id=item.get("uuid", ""),
                    name=item.get("title", ""),
                    price=price,
                    real_price=max(price, _original_price(item)),
                    description=item.get("itemDescription", ""),
                    image_url=item.get("imageUrl") or "",
                    section_uuid=section_uuid,
                    subsection_uuid=subsection_uuid,
                ))
    return products


_STRIKETHROUGH_PRICE = re.compile(r"line-through[^>]*>\s*\$([\d,]+(?:\.\d+)?)")


def _original_price(item: dict) -> float:
    """
    Precio sin oferta de un producto del menú. `price` ya trae la rebaja aplicada; el precio
    original solo viene tachado en el HTML de priceTagline.textFormat. 0 si no hay oferta.
    """
    fmt = (item.get("priceTagline") or {}).get("textFormat") or ""
    m = _STRIKETHROUGH_PRICE.search(fmt)
    return _parse_money_text(m.group(1)) if m else 0.0


def _parse_money_text(text: str) -> float:
    """Convierte '$21.00' o '21.00' a float. Retorna 0.0 si no puede."""
    try:
        return float(text.replace("$", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _parse_checkout(checkout_data: dict, product: Product, store_id: str, store_name: str = "", store_address: str = "", deep_link: str = "", variant_label: str = "", is_open: bool = True, opens_at: str = "") -> PriceQuote:
    payloads = checkout_data.get("checkoutPayloads", {})
    charges = payloads.get("fareBreakdown", {}).get("charges", [])

    delivery_fee = 0.0
    service_fee = 0.0

    for charge in charges:
        fare_id = charge.get("fareBreakdownChargeMetadata", {}).get("fareInfoID", "")
        amount = _parse_money_text(charge.get("value", {}).get("text", ""))
        if fare_id == "eats_fare.delivery_fee":
            delivery_fee = amount
        elif "service_fee" in fare_id or "basket_dependent_fee" in fare_id or "tax_and_fees" in fare_id:
            service_fee += amount

    # Usar el total real del checkout (incluye descuentos y redondeos exactos)
    checkout_total = _parse_money_text(payloads.get("total", {}).get("value", {}).get("text", ""))
    if checkout_total > 0:
        total = checkout_total
        service_fee = round(total - product.price - delivery_fee, 2)
        if service_fee < 0:
            service_fee = 0.0
    else:
        total = product.price + delivery_fee + service_fee

    return PriceQuote(
        platform="ubereats",
        product_price=product.price,
        delivery_fee=delivery_fee,
        service_fee=service_fee,
        total=total,
        deep_link=deep_link or f"https://www.ubereats.com/mx/store/store/{store_id}",
        store_name=store_name,
        store_address=store_address,
        variant_label=variant_label,
        is_open=is_open,
        opens_at=opens_at,
    )


_feed_cache = TTLStore(maxsize=4096, ttl=1200, stale_ttl=3600)  # feed por zona de ~2 km, 20 min


def _get_feed(lat: float, lng: float) -> list[dict]:
    """feedItems del inicio de Uber Eats en la zona. Una sola petición por zona cada 20 min."""
    lat, lng = zone_center(lat, lng)

    def fetch() -> list[dict]:
        body = {
            "cacheKey": "", "feedSessionCount": {"announcementCount": 0, "announcementLabel": ""},
            "userQuery": "", "date": "", "startTime": 0, "endTime": 0, "carouselId": "", "sortAndFilters": [],
            "billboardUuid": "", "feedProvider": "", "promotionUuid": "", "targetingStoreTag": "",
            "venueUUID": "", "selectedSectionUUID": "", "favorites": "", "vertical": "", "searchSource": "",
            "searchType": "", "keyName": "", "serializedRequestContext": "", "isUserInitiatedRefresh": False,
        }
        data = _call_ubereats(f"{_BASE_URL}/getFeedV1?localeCode=mx", _build_headers(lat, lng), body)
        if data.get("status") != "success":
            raise RuntimeError("getFeedV1 falló")
        return (data.get("data") or {}).get("feedItems") or []
    return _feed_cache.get_or_fetch((lat, lng), fetch)


def _feed_store_card(s: dict) -> dict:
    # La imagen más chica que siga viéndose bien en una tarjeta
    images = sorted((s.get("image") or {}).get("items") or [], key=lambda i: i.get("width") or 0)
    image = next((i for i in images if (i.get("width") or 0) >= 500), images[-1] if images else {})
    return {
        "store_id": s.get("storeUuid", ""),
        "store_name": ((s.get("title") or {}).get("text") or "").strip(),
        "image_url": image.get("url", ""),
        "offer": " · ".join(sp.get("text", "").strip() for sp in s.get("signposts") or [] if sp.get("text")),
        "rating": (s.get("rating") or {}).get("text", ""),
    }


def fetch_offer_sections(lat: float, lng: float) -> list[dict]:
    """
    Carruseles de tiendas en oferta del inicio de Uber Eats ("Ofertas de hoy", "Ahorra en
    favoritos nacionales", ...) para la zona.
    Solo se toman los carruseles en los que todas las tiendas traen etiqueta de oferta
    (signpost); el resto son recomendaciones ("Popular en tu área", "Vistos recientemente").
    Se excluyen los de Uber One ("Desbloquea con Uber One"): requieren suscripción.
    """
    sections = []
    for feed_item in _get_feed(lat, lng):
        if feed_item.get("type") != "REGULAR_CAROUSEL":
            continue
        carousel = feed_item.get("carousel") or {}
        stores = carousel.get("stores") or []
        if not stores or not all(s.get("signposts") for s in stores):
            continue
        title = ((carousel.get("header") or {}).get("title") or {}).get("text", "").replace("\xa0", " ")
        if title and "Uber One" not in title:
            sections.append({"title": title, "platform": "ubereats", "kind": "stores",
                             "items": [_feed_store_card(s) for s in stores]})
    return sections


def fetch_nearby_stores(lat: float, lng: float) -> list[dict]:
    """Tiendas que entregan en la zona, en el orden del inicio de Uber Eats (mismo feed en caché)."""
    return [
        _feed_store_card(item["store"])
        for item in _get_feed(lat, lng)
        if item.get("type") == "REGULAR_STORE" and item.get("store")
    ]
