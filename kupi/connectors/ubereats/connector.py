import json
import os
import urllib.parse
import uuid as uuid_lib
import requests as _requests
from curl_cffi import requests
from kupi.connectors.base import BaseConnector
from kupi.core.config import UBEREATS_COOKIE_STRING
from kupi.core.models import Product, PriceQuote, CartItemDetail

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


def _build_headers(lat: float, lng: float, referer: str = "https://www.ubereats.com/") -> dict:
    """Construye el dict de headers con cookies y ubicación listos."""
    return {
        **_HEADERS_BASE,
        "cookie": UBEREATS_COOKIE_STRING,
        "referer": referer,
        "x-uber-device-location-latitude": str(lat),
        "x-uber-device-location-longitude": str(lng),
        "x-uber-target-location-latitude": str(lat),
        "x-uber-target-location-longitude": str(lng),
    }


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
    if _WORKER_URL and _WORKER_SECRET:
        resp = _requests.post(
            _WORKER_URL,
            json={"url": url, "method": "POST", "headers": headers, "body": body},
            headers={"x-kupi-secret": _WORKER_SECRET},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    else:
        # Desarrollo local: llamada directa con curl_cffi
        resp = requests.post(url, json=body, headers=headers, impersonate="chrome120", timeout=20)
        resp.raise_for_status()
        return resp.json()


class UberEatsConnector(BaseConnector):

    def fetch_menu(self, store_id: str, lat: float, lng: float) -> list[Product]:
        """
        Llama a getStoreV1 y parsea el catálogo completo.
        Guarda section_uuid y subsection_uuid por producto (necesarios para cotizar).
        """
        headers = _build_headers(lat, lng)
        body = {
            "storeUuid": store_id,
            "diningMode": "DELIVERY",
            "time": {"asap": True},
            "cbType": "EATER_ENDORSED",
        }
        data = _call_ubereats(f"{_BASE_URL}/getStoreV1?localeCode=mx", headers, body)
        if data.get("status") != "success":
            raise RuntimeError(f"getStoreV1 falló: {data.get('data', {}).get('errorMessage', 'unknown')}")

        store_data = data["data"]
        return _parse_menu(store_data)

    def fetch_price(self, store_id: str, product: Product, lat: float, lng: float) -> PriceQuote:
        """
        Cotiza el precio real en 2 pasos:
          1. createDraftOrderV2  → obtiene draftOrderUUID
          2. getCheckoutPresentationV1 → desglose: producto + envío + cuota de servicio
        Reutiliza el getStoreV1 (ya llamado en fetch_menu) para obtener nombre y dirección.
        """
        # Obtener nombre y dirección de la tienda
        store_body = {"storeUuid": store_id, "diningMode": "DELIVERY", "time": {"asap": True}, "cbType": "EATER_ENDORSED"}
        store_data = _call_ubereats(f"{_BASE_URL}/getStoreV1?localeCode=mx", _build_headers(lat, lng), store_body).get("data", {})
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
        data1 = _call_ubereats(f"{_BASE_URL}/createDraftOrderV2?localeCode=mx", _build_headers(lat, lng, referer), create_body)
        if data1.get("status") != "success":
            # Puede fallar por customizaciones obligatorias vacías — obtenerlas y reintentar
            auto_custom, variant_label = _auto_customizations(store_id, product, lat, lng)
            if auto_custom:
                create_body["shoppingCartItems"][0]["customizations"] = auto_custom
                create_body["shoppingCartItems"][0]["shoppingCartItemUuid"] = str(uuid_lib.uuid4())
                data1 = _call_ubereats(f"{_BASE_URL}/createDraftOrderV2?localeCode=mx", _build_headers(lat, lng, referer), create_body)
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
        data2 = _call_ubereats(f"{_BASE_URL}/getCheckoutPresentationV1?localeCode=mx", _build_headers(lat, lng, referer), checkout_body)
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
        """
        Cotiza múltiples productos en un solo draft order de Uber Eats.
        Mismos 2 pasos que fetch_price pero con N items en shoppingCartItems.
        """
        store_body = {"storeUuid": store_id, "diningMode": "DELIVERY", "time": {"asap": True}, "cbType": "EATER_ENDORSED"}
        store_data = _call_ubereats(f"{_BASE_URL}/getStoreV1?localeCode=mx", _build_headers(lat, lng), store_body).get("data", {})
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

        data1 = _call_ubereats(f"{_BASE_URL}/createDraftOrderV2?localeCode=mx", _build_headers(lat, lng, referer), create_body)
        if data1.get("status") != "success":
            # Reintentar con auto-customizaciones por cada producto que lo necesite
            for i, p in enumerate(products):
                auto_custom, _ = _auto_customizations(store_id, p, lat, lng)
                if auto_custom:
                    create_body["shoppingCartItems"][i]["customizations"] = auto_custom
                    create_body["shoppingCartItems"][i]["shoppingCartItemUuid"] = str(uuid_lib.uuid4())
            data1 = _call_ubereats(f"{_BASE_URL}/createDraftOrderV2?localeCode=mx", _build_headers(lat, lng, referer), create_body)
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
        data2 = _call_ubereats(f"{_BASE_URL}/getCheckoutPresentationV1?localeCode=mx", _build_headers(lat, lng, referer), checkout_body)
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
                products.append(Product(
                    product_id=item.get("uuid", ""),
                    name=item.get("title", ""),
                    price=item.get("price", 0) / 100,
                    real_price=item.get("price", 0) / 100,  # UberEats no distingue real_price en este endpoint
                    description=item.get("itemDescription", ""),
                    image_url=item.get("imageUrl") or "",
                    section_uuid=section_uuid,
                    subsection_uuid=subsection_uuid,
                ))
    return products


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
