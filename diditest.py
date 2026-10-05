"""
DiDi Food (páginas públicas web) -> precios de menú para Kupi.

Fuente: https://web.didiglobal.com/mx/food/<ciudad>/<slug>/<id>/
Limitaciones (importante):
  - Solo trae precios de MENÚ. No hay costo de envío ni cuota de servicio
    (eso solo existe dentro de la app), por eso delivery_fee siempre es None.
  - El HTML real no se pudo ver al escribir esto; el parser asume que los
    nombres de producto van en <h4>, las categorías en <h3> y el precio como
    texto "MX$189.00" justo después. Si algo sale vacío, corre el modo
    `diagnostico` y pásame la salida.

Uso:
  python3 didi_web.py menu  <url completa de la sucursal>
  python3 didi_web.py buscar <texto>          (ej. humaya)
  python3 didi_web.py diagnostico <url>

Dependencias:
  pip3 install curl_cffi beautifulsoup4 --break-system-packages
"""
import re
import sys
import time
import html as htmllib
from curl_cffi import requests
from bs4 import BeautifulSoup

BASE = "https://web.didiglobal.com"
CITY_SLUG = "culiacan-cul-sin"
PRICE_RE = re.compile(r"MX\$\s*([\d.,]+)")
STORE_HREF_RE = re.compile(r"/mx/food/([a-z0-9-]+)/([a-z0-9-]+)/(\d+)/?$")

HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "accept-language": "es-MX,es;q=0.9",
}

# Pausa mínima entre peticiones: son páginas públicas, uso ligero.
PAUSE_SECONDS = 1.0


def _get(url):
    resp = requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=15)
    resp.raise_for_status()
    return resp.text


def _to_float(text):
    """'1,234.50' -> 1234.5"""
    return float(text.replace(",", ""))


INVISIBLE_RE = re.compile("[\u00ad\u200b\u200c\u200d\u2060\ufeff]")


def _clean(node):
    """Texto de un nodo como lo mostraría un navegador: sin separador entre
    nodos (el HTML ya trae sus espacios), sin caracteres invisibles y con los
    espacios colapsados. Unir con ' ' parte palabras cuando el texto viene
    fragmentado en muchos <span>."""
    text = htmllib.unescape(node.get_text())
    text = INVISIBLE_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_menu(page_html):
    """Devuelve (nombre_restaurante, [productos]) desde el HTML de una sucursal."""
    soup = BeautifulSoup(page_html, "html.parser")
    h1 = soup.find("h1")
    restaurant = _clean(h1) if h1 else None

    products = []
    category = None
    for tag in soup.find_all(["h3", "h4"]):
        text = _clean(tag)
        if tag.name == "h3":
            category = text
            continue
        # h4 = producto; su precio es el primer "MX$..." que aparece después
        price_node = tag.find_next(string=PRICE_RE)
        # el precio debe pertenecer a ESTE producto (su encabezado previo más
        # cercano es este h4); si no, el producto no tiene precio y se omite
        if price_node is None or price_node.find_previous(["h3", "h4"]) is not tag:
            continue
        match = PRICE_RE.search(price_node)
        products.append(
            {
                "name": text,
                "price": _to_float(match.group(1)),
                "category": category,
            }
        )
    return restaurant, products


def fetch_didi(store_url):
    """Misma forma de salida que los parsers de Rappi/Uber Eats de Kupi."""
    restaurant, products = parse_menu(_get(store_url))
    return {
        "platform": "didi",
        "restaurant": restaurant,
        "delivery_fee": None,  # no disponible fuera de la app
        "products": products,
    }


def list_stores(page=1, city_slug=CITY_SLUG):
    """Sucursales de una página del listado de la ciudad: [(nombre, url)]."""
    url = f"{BASE}/mx/food/{city_slug}/" + (f"?page={page}" if page > 1 else "")
    soup = BeautifulSoup(_get(url), "html.parser")
    seen, stores = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = STORE_HREF_RE.search(href.replace(BASE, ""))
        name = _clean(a)
        if not m or m.group(1) != city_slug or not name or m.group(3) in seen:
            continue
        seen.add(m.group(3))
        stores.append((name, BASE + m.group(0)))
    return stores


def search_stores(query, max_pages=5, city_slug=CITY_SLUG):
    query = query.lower()
    found = []
    for page in range(1, max_pages + 1):
        try:
            stores = list_stores(page, city_slug)
        except Exception as exc:  # una página caída no debe tirar la búsqueda
            print(f"(página {page} falló: {exc})")
            continue
        found += [(n, u) for n, u in stores if query in n.lower()]
        time.sleep(PAUSE_SECONDS)
    return found


def _print_menu(data):
    print(f"{data['restaurant']}  |  envío: {data['delivery_fee']}")
    print(f"{len(data['products'])} productos")
    for p in data["products"][:15]:
        print(f"  {p['price']:>8.2f}  [{p['category']}]  {p['name']}")
    if len(data["products"]) > 15:
        print("  ...")
    if not data["products"]:
        print("0 productos: corre 'diagnostico' con la misma URL y pásame la salida.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, arg = sys.argv[1], " ".join(sys.argv[2:])
    if cmd == "menu":
        _print_menu(fetch_didi(arg))
    elif cmd == "buscar":
        results = search_stores(arg)
        print(f"{len(results)} resultado(s) para '{arg}':")
        for name, url in results:
            print(f"  {name}\n    {url}")
    elif cmd == "diagnostico":
        page = _get(arg)
        soup = BeautifulSoup(page, "html.parser")
        print("bytes:", len(page))
        print("h1:", [h.get_text(strip=True) for h in soup.find_all("h1")][:3])
        print("h3 (categorías):", len(soup.find_all("h3")))
        print("h4 (productos):", len(soup.find_all("h4")))
        print("precios 'MX$' en el HTML:", len(PRICE_RE.findall(page)))
        print("tiene __NEXT_DATA__:", "__NEXT_DATA__" in page)
        h1 = soup.find("h1")
        if h1:
            print("h1 nodos de texto:", [s for s in h1.strings])
            print("h1 limpio:", repr(_clean(h1)))
        for h4 in soup.find_all("h4")[:6]:
            print("h4 crudo:", repr(h4.get_text()), "-> limpio:", repr(_clean(h4)))
        i = page.find("MX$")
        print("contexto del primer precio:\n", page[max(0, i - 400): i + 120])
    else:
        print(__doc__)