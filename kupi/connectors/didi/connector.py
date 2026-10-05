"""
Conector de DiDi Food usando páginas web públicas (sin login).

store_id = ID numérico de la sucursal en DiDi (último segmento de la URL).
  Ej: "5764607637052981505"  → Little Caesars (Humaya 034)

El catálogo de sucursales disponibles está en stores.json (Culiacán).

Limitación importante:
  delivery_fee y service_fee siempre son None — esos datos solo existen
  dentro de la app de DiDi, no en las páginas web públicas.
  El total que devuelve fetch_price es solo el precio del producto.
"""
import json
import re
import html as htmllib
from pathlib import Path
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup

from kupi.connectors.base import BaseConnector
from kupi.core.models import Product, PriceQuote

_STORES_FILE = Path(__file__).parent / "stores.json"
_STORES: dict = json.loads(_STORES_FILE.read_text(encoding="utf-8"))

_PRICE_RE = re.compile(r"MX\$\s*([\d.,]+)")
_INVISIBLE_RE = re.compile("[\u00ad\u200b\u200c\u200d\u2060\ufeff]")

_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
    ),
    "accept-language": "es-MX,es;q=0.9",
}


def _clean(node) -> str:
    text = htmllib.unescape(node.get_text())
    text = _INVISIBLE_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _to_float(text: str) -> float:
    return float(text.replace(",", ""))


def get_store_url(store_id: str) -> str:
    """Devuelve la URL completa de una sucursal a partir de su ID numérico."""
    entry = _STORES.get(store_id)
    if not entry:
        raise ValueError(f"DiDi store_id '{store_id}' no está en el catálogo (stores.json)")
    return entry["url"]


def get_store_name(store_id: str) -> str:
    entry = _STORES.get(store_id)
    return entry["name"] if entry else store_id


class DidiConnector(BaseConnector):

    def _get(self, url: str) -> str:
        resp = cffi_requests.get(
            url, headers=_HEADERS, impersonate="chrome120", timeout=15
        )
        resp.raise_for_status()
        return resp.text

    def _parse_products(self, html: str, store_id: str) -> list[Product]:
        soup = BeautifulSoup(html, "html.parser")
        products: list[Product] = []
        category: str | None = None

        for tag in soup.find_all(["h3", "h4"]):
            text = _clean(tag)
            if tag.name == "h3":
                category = text
                continue
            # h4 = producto; buscar el primer precio MX$ inmediatamente después
            price_node = tag.find_next(string=_PRICE_RE)
            if price_node is None or price_node.find_previous(["h3", "h4"]) is not tag:
                continue
            match = _PRICE_RE.search(price_node)
            price = _to_float(match.group(1))
            # DiDi no expone un ID de producto en el HTML; usar store_id + nombre normalizado
            product_id = f"{store_id}_{re.sub(r'[^a-z0-9]', '_', text.lower())}"
            products.append(
                Product(
                    product_id=product_id,
                    name=text,
                    price=price,
                    real_price=price,   # DiDi no distingue precio tachado en el HTML
                    description="",
                    image_url="",
                )
            )
        return products

    def fetch_menu(self, store_id: str, lat: float, lng: float) -> list[Product]:
        """Descarga el menú de la sucursal desde la página pública de DiDi."""
        url = get_store_url(store_id)
        html = self._get(url)
        return self._parse_products(html, store_id)

    def fetch_price(
        self, store_id: str, product: Product, lat: float, lng: float
    ) -> PriceQuote:
        """
        Devuelve el precio de menú del producto.
        delivery_fee y service_fee son None (no disponibles fuera de la app).
        total = solo el precio del producto.
        """
        store_name = get_store_name(store_id)
        deep_link = get_store_url(store_id)
        return PriceQuote(
            platform="didi",
            product_price=product.price,
            delivery_fee=None,    # no disponible fuera de la app
            service_fee=None,     # no disponible fuera de la app
            total=product.price,  # total parcial — no incluye envío
            eta_minutes=None,
            deep_link=deep_link,
            store_name=store_name,
            store_address="",
        )
