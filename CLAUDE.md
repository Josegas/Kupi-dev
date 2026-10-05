# Kupi - Resumen técnico (para continuar en Claude Code)

## Qué es Kupi
Metabuscador de precios de comida a domicilio (Rappi, Didi Food, Uber Eats) en México. Muestra el precio final real (producto + envío) en tiempo real para comparar plataformas. Sin login de usuario requerido. Incluye cupones de canales de WhatsApp.

## Contexto del proyecto
- Kupi nació en el hackathon **AWS "Zero to Shipped"** (18 sept – 2 oct 2026). El hackathon ya se entregó, está desplegado en AWS con URL pública y cumple todos los requisitos del hackathon. Actualmente en revisión por los jueces.
- **Este repo (`Kupi-dev`)** es el repo de **desarrollo activo**, creado el 4 de octubre de 2026 para continuar construyendo el producto con features nuevas, mejoras y evolución del código sin afectar la entrega del hackathon.
- **El repo original (`Kupi`, github: Josegas/Kupi)** se usa solo para **mantenimiento operativo**: corregir bugs, rotar cookies/tokens, ajustes mínimos para mantener el producto funcionando. No se desarrollan features nuevas ahí — está en revisión por los jueces del hackathon.
- El proyecto tiene intención real de crecer como producto más allá del hackathon - la arquitectura se decidió pensando en esa escala futura.

---

## Flujo de trabajo con Claude Code
- **Control de commits manual**: Claude Code **no** puede hacer `git commit` ni modificar el control de versiones por su cuenta. Siempre debe pedir autorización expresa antes de realizar cualquier commit o alteración en el repositorio.
- **Siempre usar pnpm, nunca npm.** Para cualquier operación de Node.js (install, dev, build, etc.) usar exclusivamente `pnpm`. npm está prohibido por problemas de seguridad.
- **Presupuesto: $0, sin excepciones.** No activar, aprovisionar ni dejar corriendo ningún recurso de AWS (ni de ningún otro servicio) que pueda generar un cobro, ni siquiera "solo por probar" - esto no es negociable ni con permiso explícito caso por caso: si algo puede llegar a cobrar, se evita por completo o se reemplaza por una alternativa genuinamente gratuita antes de usarlo.
- **Pedir permiso obligatorio antes de**: cualquier `git commit`, `git push`, cambios estructurales de código, modificar los parsers de Rappi/Uber Eats ya funcionando, borrar o crear archivos, o cualquier acción sobre AWS y la infraestructura.
- Claude Code solo puede proponer los cambios o mostrar el código, pero el dueño del proyecto es quien revisa, aprueba y ejecuta los commits para que cada cambio refleje exactamente lo hecho por él.



### Endpoint principal
```
POST https://services.mxgrability.rappi.com/api/web-gateway/web/restaurants-bus/store/id/{store_id}/
```

**Body**:
```json
{"lat": 24.80769, "lng": -107.39447, "store_type": "restaurant", "is_prime": false, "prime_config": {"unlimited_shipping": false}}
```

**Headers requeridos**:
```
authorization: Bearer ft.gAAAA...   (reutilizable standalone)
app-version: 1.162.2
deviceid: 817b8d4a-df4f-459e-bcb6-bb4505349fec
content-type: application/json; charset=UTF-8
user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36
accept: application/json
accept-language: es-MX
```

### Respuesta - campos clave
- `delivery_price`: costo de envío
- `corridors[].products[]`: `product_id`, `name`, `price` (con descuento), `real_price` (sin descuento), `discounts[]`
- `discount_tags[]`: promociones activas
- `eta`, `rating`

### Notas
- Cloudflare bloquea `curl` desnudo (429) - resolver con headers de navegador real (`user-agent`, `accept`, `accept-language`).
- No es bloqueo por IP permanente - esperar 5-10 min si se dispara el rate limit.

### Parser base (Python)
```python
HEADERS_BASE = {
    "authorization": f"Bearer {RAPPI_TOKEN}",
    "app-version": "1.162.2",
    "deviceid": RAPPI_DEVICE_ID,
    "content-type": "application/json; charset=UTF-8",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "accept": "application/json",
    "accept-language": "es-MX",
}

def _fetch_rappi(store_id, lat, lng):
    url = f"https://services.mxgrability.rappi.com/api/web-gateway/web/restaurants-bus/store/id/{store_id}/"
    body = {"lat": lat, "lng": lng, "store_type": "restaurant", "is_prime": False, "prime_config": {"unlimited_shipping": False}}
    resp = requests.post(url, headers=HEADERS_BASE, json=body, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    return {
        "delivery_fee": data["delivery_price"],
        "products": [
            {"product_id": p["product_id"], "name": p["name"], "price": p["price"], "real_price": p["real_price"]}
            for corridor in data["corridors"] for p in corridor["products"]
        ]
    }
```

---

## UBER EATS - ✅ Completado

### Flujo completo confirmado (2 pasos para delivery fee + 1 para catálogo)
```
1. getStoreV1              → catálogo de productos de la tienda
2. createDraftOrderV2      → crea un draft order con el producto (server genera draftOrderUUID)
3. getCheckoutPresentationV1 → con ese draftOrderUUID, trae el desglose real: subtotal, delivery fee, cuota de servicio
```

**Confirmado funcionando end-to-end** (ejemplo real, Little Caesars Humaya, Culiacán):
```
Subtotal: $189.00
Costo de envío: $25.00
Cuota de servicio: $17.01
```

### Endpoint principal - menú completo
```
POST https://www.ubereats.com/_p/api/getStoreV1?localeCode=mx
```

**Body**:
```json
{"storeUuid": "793b1eae-e077-44d0-8744-cf23f54fec50", "diningMode": "DELIVERY", "time": {"asap": true}, "cbType": "EATER_ENDORSED"}
```

### Autenticación - diferente a Rappi
- **No hay Bearer token reutilizable.** Depende de **cookies de sesión** completas (capturadas del navegador vía DevTools → Application → Cookies).
- Headers clave: `content-type`, `x-csrf-token: "x"` (parece estático, verificar si cambia por sesión), `x-uber-session-id` (UUID de sesión).
- **Cloudflare bloqueaba `requests` normal (JA3/TLS fingerprint)** - se resolvió usando **`curl_cffi`** con `impersonate="chrome120"`, que imita la huella TLS de un navegador real. Con esto + cookies completas, respuesta `200 OK` confirmada.

### Código funcional (confirmado, status 200)
```python
from curl_cffi import requests

cookies_dict = {}  # parsear del cookie_string capturado en DevTools
headers = {
    "content-type": "application/json; charset=UTF-8",
    "x-csrf-token": "x",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "origin": "https://www.ubereats.com",
    "referer": "https://www.ubereats.com/",
}
body = {"storeUuid": STORE_UUID, "diningMode": "DELIVERY", "time": {"asap": True}, "cbType": "EATER_ENDORSED"}

resp = requests.post(
    "https://www.ubereats.com/_p/api/getStoreV1?localeCode=mx",
    json=body, headers=headers, cookies=cookies_dict, impersonate="chrome120",
)
data = resp.json()  # {"status": ..., "data": {...}}
```

### Estructura de respuesta (confirmada)
Los productos **NO** están en `sectionEntitiesMap` (viene vacío). Están anidados en:

```
data["catalogSectionsMap"][sectionUUID] → lista de sub-secciones
  └── cada sub-sección:
        payload.standardItemsPayload.catalogItems → lista de productos
          ├── uuid
          ├── title
          ├── itemDescription
          ├── price          (centavos, ej: 18900 = $189.00 MXN)
          └── priceTagline.text  (precio formateado, con descuento visible)
```

`data["sections"][0]["subsectionUuids"]` da la lista de UUIDs de sub-secciones a recorrer.

### Parser de catálogo (funcional)
```python
def _fetch_ubereats_menu(store_data):
    products = []
    catalog_map = store_data.get("catalogSectionsMap", {})
    for section_uuid, subsections in catalog_map.items():
        for subsection in subsections:
            items = subsection.get("payload", {}).get("standardItemsPayload", {}).get("catalogItems", [])
            for item in items:
                products.append({
                    "product_id": item.get("uuid"),
                    "name": item.get("title"),
                    "description": item.get("itemDescription"),
                    "price": item.get("price", 0) / 100,
                    "price_display": item.get("priceTagline", {}).get("text"),
                })
    return products
```

### Delivery fee - RESUELTO
`data["fareInfo"]` de `getStoreV1` **no** trae el dato real (solo `serviceFeeCents: null`, y hay un banner promocional engañoso "$0 usuarios nuevos"). El fee real solo aparece tras simular la creación de un pedido:

**Paso 2 - `createDraftOrderV2`** (crea el draft order, el UUID lo genera el servidor - nunca lo mandes tú):
```python
create_body = {
    "isMulticart": True,
    "shoppingCartItems": [{
        "uuid": ITEM_UUID,                    # product_id del catálogo
        "shoppingCartItemUuid": str(uuid.uuid4()),
        "storeUuid": STORE_UUID,
        "sectionUuid": SECTION_UUID,
        "subsectionUuid": SUBSECTION_UUID,    # ¡debe ser el correcto del item, no cualquiera del catálogo!
        "price": ITEM_PRICE,
        "title": ITEM_TITLE,
        "quantity": 1,
        "customizations": {...},              # requerido si el producto tiene personalización obligatoria - sacarlo de getMenuItemV1
        "imageURL": "...",
        "specialInstructions": "",
        "itemId": None
    }],
    "useCredits": True,
    "extraPaymentProfiles": [],
    "promotionOptions": {"autoApplyPromotionUUIDs": [], "selectedPromotionInstanceUUIDs": [], "skipApplyingPromotion": False},
    "deliveryTime": {"asap": True},
    "deliveryType": "ASAP",
    "currencyCode": "MXN",
    "interactionType": "door_to_door",
    "checkMultipleDraftOrdersCap": True,
    "actionMeta": {"isQuickAdd": False, "numClicks": 1},
    "businessDetails": {}
}
resp1 = session.post("https://www.ubereats.com/_p/api/createDraftOrderV2?localeCode=mx", json=create_body, headers=headers, impersonate="chrome120")
draft_order_uuid = resp1.json()["data"]["draftOrder"]["uuid"]
```

**Paso 3 - `getCheckoutPresentationV1`** (con el `draftOrderUUID` del paso anterior):
```python
checkout_body = {
    "draftOrderUUID": draft_order_uuid,
    "isGroupOrder": False,
    "webGiftingPersonalizationEnabled": True,
    "clientFeaturesData": {"paymentSelectionContext": {"value": '{"deviceContext":{"thirdPartyApplications":[]}}'}},
    "payloadTypes": ["canonicalProductStorePickerPayload", "total", "subtotal", "fareBreakdown", "paymentProfilesEligibility", "requestUtensilPayload", "versionMetadata"]
}
resp2 = session.post("https://www.ubereats.com/_p/api/getCheckoutPresentationV1?localeCode=mx", json=checkout_body, headers=headers, impersonate="chrome120")
charges = resp2.json()["data"]["checkoutPayloads"]["fareBreakdown"]["charges"]
# cada charge: {"title": {"text": "Costo de envío"}, "value": {"text": "$25.00"}, "fareBreakdownChargeMetadata": {"fareInfoID": "eats_fare.delivery_fee"}}
```

### Headers críticos que faltaban (causaban error 500 sin mensaje)
No basta con `content-type` + `x-csrf-token` + cookies. `createDraftOrderV2` valida huella de navegador - headers obligatorios adicionales:
```
accept: */*
accept-language: es-419,es;q=0.5
sec-ch-ua, sec-ch-ua-mobile, sec-ch-ua-platform
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-origin
sec-gpc: 1
priority: u=1, i
referer: <URL completa de la tienda, incluyendo mod=quickView&modctx=<json url-encoded doble> del producto específico>
```
Sin estos, la petición responde `200` pero con body `{"status":"failure","code":"500"}` - engañoso porque el status HTTP es 200.

### Sesión - usar `Session()`, no cookies sueltas
Usar `curl_cffi.requests.Session()` en vez de pasar `cookies=` en cada llamada - el servidor va rotando cookies de sesión (`uev2.id.session_v2`, etc.) entre requests, y `Session()` las persiste automáticamente igual que un navegador.

### Cómo obtener `subsectionUuid` correcto por producto
Cada producto vive en una subsección específica dentro de `catalogSectionsMap` (ver estructura arriba) - no asumir que todos comparten la misma subsección. Sacarlo del mismo parser de catálogo, guardado junto a cada producto.

### Personalización obligatoria (`customizations`)
Si un producto tiene opciones obligatorias (ej. sabor, tamaño), `createDraftOrderV2` **falla con 500** si se manda `customizations: {}` vacío. Hay que capturar la estructura real desde `getMenuItemV1` (detalle del producto) y replicarla. Para cotizar precios sin intervención del usuario, definir una regla simple: tomar siempre la primera opción disponible de cada grupo de personalización obligatorio.

---

## DIDI FOOD - ⏸️ Pausado (bloqueado por hardware)

### Estado
- App instalada y funcional en emulador (`com.xiaojukeji.global.customer_3.2.6`, bundle ARM64 corriendo en x86_64 vía traducción binaria).
- Frida + unpinning funcionando - tráfico HTTPS interceptado sin errores TLS.
- Cobertura de Culiacán confirmada en config Apollo (`"52250100": {"cityName": "mx_Culiacan"}`).
- **Bloqueador real**: el flujo del Home depende del selector de mapa (Google Maps SDK), que crashea en el emulador (swiftshader sin aceleración GPU real). Proceso `1.raster` truena consistentemente.
- Nunca se llegó a capturar tráfico al dominio real de comida (`didi-food.com`) - la app nunca cargó el feed completo.

### Endpoints conocidos (sin confirmar, extraídos de config Apollo, no probados en vivo)
- `c.didi-food.com/feed/indexV3` - feed principal
- `c.didi-food.com/shop/index` - página de restaurante
- `c.didi-food.com/item/detail` - detalle de producto
- `c.didi-food.com/address/textSearch`, `/address/create`
- `c.didi-food.com/cart/info`, `/order/createV2`

### Plan de retoma
- Celular físico disponible: **Honor 20** (sin rootear).
- Bloqueado por "demora de seguridad" de Android (24h) al intentar activar Depuración USB - reiniciado para iniciar el conteo.
- Pantalla táctil del Honor 20 defectuosa ("touch fantasma") → plan es usar **scrcpy** (`sudo apt install scrcpy`) para controlar el celular desde la laptop vía USB una vez pase la demora de 24h.
- Con scrcpy + Frida + mitmproxy en el Honor 20 (hardware real, sin problemas de GPU), se debería poder completar el flujo de mapa sin crashes y capturar el tráfico real de `didi-food.com`.

---

## DISEÑO (UI/UX) - decidido en el lienzo de Diseño de Claude

Diseño hecho directamente en un lienzo de Claude (Design canvas), con 5 artboards: Inicio (móvil), Comparación (móvil, exploración inicial descartada visualmente), Inicio (web), Comparación de precios (web) - dirección final - y Logotipo. La dirección final del producto es **web-first, responsivo** (no app móvil nativa).

### Paleta de colores (final)
| Token | Hex | Uso |
|---|---|---|
| `bg` | `#F5F5F3` | Fondo general de la página |
| `surface` | `#FFFFFF` | Tarjetas, barra de navegación, inputs |
| `border` | `#E4E4DF` | Bordes de tarjetas e inputs |
| `text-primary` | `#1F2323` | Texto principal (nombres, títulos, carbón oscuro) |
| `text-secondary` | `#6B6558` | Texto secundario (cuisine, ETA, descripciones) |
| `text-muted` | `#9A9384` | Placeholders, etiquetas sutiles |
| `brand` (naranja) | `#C2410C` | Logo "Kupi", nav activo, ubicación (hover), ícono de estrella, badges de marca |
| `brand-tint` | `#FCE8DC` | Fondo claro de badges de marca (ej. avatar, "3 apps") |
| `savings` (verde) | `#15803D` | Precio, badge "Más barato", tarjeta destacada, botón de acción - **reservado exclusivamente para el concepto de ahorro/mejor precio** |
| `savings-tint` | `#EAF6EE` | Fondo de la tarjeta de plataforma más barata |

Solo 2 colores saturados con propósito claro (naranja = marca/entrega, verde = ahorro/comparación), inspirados en la energía de Rappi/Uber Eats/DiDi Food sin copiar a ninguna - todo lo demás es neutro. Evitar agregar más tonos saturados; si se necesita un tercer estado, usar variaciones de opacidad/tint de estos dos antes que un color nuevo.

### Tipografía
- **Encabezados / logo**: `Space Grotesk` (Google Fonts), pesos 500/600/700
- **Cuerpo / UI**: `IBM Plex Sans` (Google Fonts), pesos 400/500/600/700
- Tamaños: logo 24px, h1 26px, h2 16–18px, cuerpo 13–15px, caption 10–12px

### Logotipo (wordmark)
Ícono geométrico minimalista + wordmark, vectorial (SVG):
- Base: cuadrado redondeado (`rx: 18`) relleno `#1F2323` (carbón).
- Dos esquinas diagonales recortadas: superior-izquierda en naranja `#C2410C`, inferior-derecha en verde `#15803D` - evocan "comparar dos opciones" de forma abstracta, sin ser un ícono literal.
- Wordmark "Kupi" en Space Grotesk Bold 700, color `#1F2323`, `letter-spacing: -0.03em`.
- Aislado sobre fondo `#F5F5F3` (gris claro limpio), sin gradientes ni saturación excesiva.

### Espaciado y radios
- Padding de página (desktop): 48px laterales
- Radio de tarjetas: 16–18px · Radio de pills/badges: 999px · Radio de botón CTA: 14px
- Gap de grid de restaurantes: 24px
- Grid de restaurantes: `repeat(3, minmax(0,1fr))` desktop → 2 columnas tablet → 1 columna móvil

### Componentes

**TopNav** - Logo "Kupi" (`brand`, Space Grotesk 24px) + buscador con ícono de lupa (foco: anillo `rgba(194,65,12,0.14)` + borde `brand`) + botón de ubicación (texto `text-primary`, hover `brand`) + avatar circular (fondo `brand-tint`, texto `brand`).

**CategoryChip** - Pill 13px/600. No-seleccionado: fondo `surface`, borde `border`. Seleccionado: fondo `brand`, texto blanco.

**RestaurantCard** - Imagen (placeholder 140px), nombre (16px/700), cuisine + ⭐ rating (ícono estrella en `brand`, no ámbar), badge "3 apps" (`brand-tint` bg + `brand` texto), **precio "Desde $X"** (el precio base del producto, no el total final) en `savings` (verde), 15px/700. Sombra sutil (`0 1px 3px rgba(31,35,35,0.05)`), al hover: eleva `-3px` + sombra `0 12px 28px rgba(31,35,35,0.10)`.

**PlatformCompareCard** (pantalla de comparación) - Nombre + ETA, precio total grande (20px/700, en `savings` si es la más barata, si no `text-primary`), desglose Producto/Envío/Cuota de servicio. Si es la más barata: badge "Más barato" (`savings` bg, texto blanco) + fondo `savings-tint` + borde `savings` 1.5px. Mismo hover-lift que RestaurantCard.

**CTAButton** - Pill 14px radio, fondo `savings`, texto blanco 15px/700, sombra `0 4px 12px rgba(21,128,61,0.25)`, ícono de flecha. Al hover: eleva `-1px` + `filter: brightness(1.06)`. Texto dinámico: "Ir a {plataforma} · {precio total}".

### Micro-interacciones (implementadas como CSS real en el mockup - replicar tal cual en producción)
```css
.kupi-card{transition:transform .18s ease, box-shadow .18s ease}
.kupi-card:hover{transform:translateY(-3px);box-shadow:0 12px 28px rgba(31,35,35,0.10)}
.kupi-btn{transition:transform .15s ease, filter .15s ease}
.kupi-btn:hover{transform:translateY(-1px);filter:brightness(1.06)}
.kupi-input:focus-within{border-color:#C2410C;box-shadow:0 0 0 3px rgba(194,65,12,0.14)}
.kupi-link:hover{color:#C2410C}
```
Deliberadamente sutil - sin gradientes, sin animaciones vistosas. Efectos más elaborados (transiciones de página, entradas escalonadas) quedan para la implementación real con Framer Motion o CSS transitions en Next.js, no se prototiparon aquí.

### Pantallas
1. **Inicio**: TopNav → título + tagline → CategoryChips → grid de RestaurantCard (3 columnas desktop).
2. **Comparación de precios**: header con volver + nombre del restaurante → panel del producto (imagen + nombre + descripción) a la izquierda → grid de 3 PlatformCompareCard a la derecha (fila en desktop, columna apilada en móvil) → CTAButton fijo abajo.

### Responsivo
- Grid de restaurantes: 3 → 2 → 1 columnas según ancho de viewport (Tailwind: `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`).
- Las 3 tarjetas de comparación pasan de fila horizontal (desktop) a columna apilada (móvil) - mismo componente, solo cambia el contenedor.
- Se exploraron artboards móviles por separado al inicio del proceso de diseño (con otra paleta, ya descartada) - no usar esos colores; solo sirven como referencia de layout en pantalla angosta si hace falta.


- **Catálogo** (qué restaurantes/productos existen): indexado periódicamente (cada 12-24h).
- **Precios**: live query en el momento de la búsqueda del usuario (deben coincidir con lo que el usuario ve en cada app).
- **Caché de búsquedas idénticas**: máximo 30-60 segundos.
- **Botón "verificar ahora"**: live query bajo demanda.
- **Seguridad**: nunca usar cuentas personales en ninguna plataforma. Tokens/cookies sensibles solo en `.env`, nunca en código.
- **Patrón de arquitectura decidido: monolito modular.** Un solo servicio desplegable, pero organizado internamente en módulos con fronteras claras - así el hackathon no obliga a sobre-diseñar microservicios desde el día uno, pero el código queda listo para separarse en servicios independientes si el proyecto crece después (ej. cada conector de plataforma podría volverse su propia Lambda/servicio más adelante sin reescribir lógica de negocio).
- **Principio de portabilidad (importante):** usar servicios gratuitos hoy (Lambda, Supabase) no debe encerrar el proyecto a futuro. Dos reglas para lograrlo:
  1. **El código de AWS es solo el "sobre", nunca la lógica.** `main.py` es una app de FastAPI normal; `lambda_handler.py` (con Mangum) es un archivo aparte que solo la envuelve para correr en Lambda. Si el día de mañana Kupi se mueve a un contenedor, un VPS u otro proveedor, se cambia ese archivo de entrada - el resto del código (`connectors/`, `pricing/`, `catalog/`) no toca nada específico de AWS y no se reescribe.
  2. **El modelo de datos siempre en Postgres, nunca en DynamoDB**, aunque hoy se aloje gratis en Supabase por costo. Postgres es portable (un `pg_dump`/`pg_restore` lo mueve a RDS, a otra nube o a un servidor propio sin tocar el modelo). DynamoDB obliga a diseñar los patrones de acceso desde el día uno y es costoso de adaptar si el producto pivota - mal trade-off para un proyecto que se piensa hacer crecer.

### Estructura de módulos sugerida
```
kupi/
├── core/            # config, modelos compartidos, tipos comunes (Product, PriceQuote, etc.)
├── connectors/       # un módulo por plataforma, cada uno expone la misma interfaz (fetch_menu, fetch_price)
│   ├── rappi/
│   ├── ubereats/
│   └── didi/
├── catalog/          # jobs de indexado periódico de catálogo (qué restaurantes/productos existen)
├── pricing/          # orquesta consultas live a los conectores, arma la comparación final
├── coupons/          # scraping de canales de WhatsApp
├── api/               # capa HTTP (endpoints REST que consume el frontend)
└── web/               # frontend (o repo aparte)
```
La regla clave: cada conector implementa la misma interfaz, así `pricing/` no le importa si es Rappi, Uber Eats o DiDi - solo pide `fetch_price(product_id)` y recibe un resultado normalizado. Esto es lo que permite que a futuro cada conector se pueda extraer como servicio propio sin tocar el resto del sistema.

## Stack tecnológico sugerido

### Backend
- **Python + FastAPI**, empaquetado para correr en **AWS Lambda vía Mangum** - coherente con todo el trabajo de scraping/parsers ya hecho en Python (`curl_cffi`, parsers de Rappi/Uber). El "monolito modular" se empaqueta como una sola función Lambda; la modularidad es del código (`core/`, `connectors/`, etc.), no de la infraestructura.
- **APScheduler no aplica dentro de Lambda** (no hay proceso persistente) - el indexado periódico de catálogo se dispara con **EventBridge Scheduler** invocando la misma función Lambda con un evento distinto (EventBridge Scheduler también tiene capa gratuita amplia; verificar términos vigentes antes de asumir "permanente").
- **Base de datos: PostgreSQL, alojado en Supabase** (no RDS) - ver sección de despliegue.

### Frontend
- **Next.js exportado como sitio estático** (`output: 'export'`) - la app no necesita renderizado en servidor (todo el fetch de precios va del frontend al backend por API), así que un export estático cubre buscador, comparación de precios y redirección a la plataforma elegida sin perder el framework.

### Despliegue en AWS (requisito del hackathon) - todo dentro de la capa gratuita, sin excepción
- ⚠️ **AWS App Runner NO tiene capa gratuita** - cobra desde la primera hora de uso. Descartado.
- ⚠️ **RDS (PostgreSQL) solo es gratis 12 meses** en cuentas nuevas. Descartado.
- ⚠️ **API Gateway también es solo 12 meses gratis** (no "Always Free" como se dijo antes en una versión anterior de este documento) - por eso no se usa aquí.
- ⚠️ **S3 y CloudFront tampoco son "Always Free"** - su capa gratuita es de 12 meses para cuentas nuevas, igual que RDS. No asumir que son una opción permanente sin verificarlo primero en la página oficial de AWS Free Tier (los términos cambian).
- **Backend → AWS Lambda con Function URL habilitada** (sin API Gateway) + Mangum + FastAPI: Function URL es una característica nativa de Lambda, no pasa por API Gateway, así que hereda el free tier **permanente** de Lambda (1 millón de invocaciones/mes, 400,000 GB-segundos de cómputo) sin fecha de caducidad.
- **Base de datos → Supabase (Postgres), plan gratuito** - no es de AWS, así que no toca en absoluto la facturación de la cuenta de AWS, y su capa gratuita no caduca a los 12 meses como la de RDS. Se mantiene SQL real para las consultas de histórico de precios. Alternativa 100% nativa de AWS si se prefiere: **DynamoDB** (capa gratuita permanente, 25 GB), adaptando el modelo a NoSQL.
- **Frontend → Amplify Hosting** para el export estático de Next.js - **verificar en la documentación oficial vigente** si sus términos de free tier (build minutes + hosting) son distintos a los de S3/CloudFront directo antes de darlo por permanente.
- **Secretos → AWS Systems Manager Parameter Store, tier estándar** (gratis) - nunca Secrets Manager (cobra por secreto desde el día 1) y nunca en el repo.
- **Coding agent conectado a AWS** (requisito a documentar): usar Claude Code con AWS CLI configurado (`aws configure`) o el AWS Toolkit, y guardar evidencia (capturas de terminal, logs de despliegue) de que el agente interactuó con la consola/CLI de AWS - esto en sí no tiene costo, es solo el agente ejecutando comandos.
- **Red de seguridad obligatoria: AWS Budget en $0 con alerta por correo** - gratis de crear, y avisa de inmediato si algún recurso empieza a generar cargos por error humano o por un cambio futuro en los términos de un free tier.
- **Antes de crear cualquier recurso nuevo en AWS**, verificar explícitamente en la documentación oficial vigente si su capa gratuita es "Always Free" (permanente) o "12 meses para cuentas nuevas" - los créditos de GitHub Student Pack cubren el costo, pero un cargo cubierto por créditos sigue siendo un recurso que cobra, y va contra la regla de presupuesto $0 de este proyecto: no aprovisionar nada así, ni con créditos de por medio.

### GitHub Student Developer Pack - qué aprovechar
- **Créditos de AWS** incluidos en el pack: quedan como colchón de emergencia sin usar, no como plan - la meta es no necesitarlos nunca.
- **Dominio gratis vía Namecheap** (incluido en el pack) - para tener una URL propia en vez de la default de AWS, se ve más serio para el jurado y para usuarios reales después.
- **GitHub Copilot gratis** - puede acelerar el desarrollo del frontend y de los parsers restantes (DiDi).
- **JetBrains gratis** (si se prefiere PyCharm sobre el editor actual) - opcional, no crítico dado que ya se está trabajando cómodo en el entorno actual.

## Seguridad - checklist para proteger la marca y a los usuarios

### Secretos y credenciales
- **Nunca en el repo, ni en commits pasados.** `.env` en `.gitignore` desde el primer commit - si algo se sube por error, no basta con borrarlo después: hay que rotar la credencial, porque queda en el historial de git.
- **Las cookies/tokens de Uber Eats y Rappi usados durante las pruebas de este proyecto (pegados en esta conversación) deben tratarse como comprometidos** - no reusarlos en producción; capturar credenciales frescas directamente en el entorno de producción vía Parameter Store, nunca copiando y pegando las de desarrollo.
- Rotar periódicamente las cookies de sesión de los conectores (Rappi/Uber Eats/DiDi) - no son permanentes y capturarlas de nuevo es rutina, no una excepción.

### Autenticación de usuarios
- Toda la autenticación (login, contraseñas, tokens) la maneja el proveedor (Supabase Auth o Cognito) - Kupi **nunca** almacena ni procesa contraseñas en texto plano ni con hashing propio.
- El backend solo verifica el JWT que emite el proveedor de auth en cada request; no reimplementar lógica de sesión a mano.

### Red y transporte
- **HTTPS en todo el flujo** - Lambda Function URL y Amplify Hosting lo dan por defecto, no desactivarlo nunca.
- **CORS restringido al dominio real del frontend**, nunca `*` (wildcard) en producción.
- **Rate limiting en la propia API de Kupi** (no solo confiar en el rate-limit de las plataformas que se consultan) - protege contra abuso y reduce el riesgo de que Rappi/Uber Eats/DiDi detecten y bloqueen los conectores por tráfico anómalo.

### Permisos en AWS (IAM)
- El rol de ejecución de la Lambda debe tener **el mínimo permiso posible** (leer solo los parámetros de Parameter Store que necesita, nada de `AdministratorAccess` ni permisos amplios "por si acaso").

### Datos y logs
- **Nunca loguear cookies, tokens, ni datos completos de usuarios** en CloudWatch ni en ningún log - si hace falta depurar, loguear solo IDs o metadatos, nunca el secreto o dato sensible completo.
- Conexión a Supabase Postgres siempre con SSL (`sslmode=require`), nunca en texto plano.
- Confirmar que los backups automáticos de Supabase estén activos antes de tener datos reales de usuarios.

### Dependencias
- Activar **Dependabot** en GitHub (gratis) para alertas de vulnerabilidades en dependencias de Python (`pip`) y Node (`npm`) - mantenerlas actualizadas es la defensa más simple contra vulnerabilidades conocidas.

### Cabeceras de seguridad web (frontend)
- Configurar cabeceras básicas en Amplify/CloudFront: `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` - protegen contra clickjacking e inyección de contenido.

## Próximos pasos inmediatos
1. ~~Uber Eats: capturar el endpoint de carrito/checkout para obtener el delivery fee real.~~ ✅ Completado.
2. DiDi: esperar demora de 24h en el Honor 20, configurar scrcpy, repetir el flujo con Frida + mitmproxy en hardware real.
3. Definir estructura del monorepo (`core/`, `connectors/`, `catalog/`, `pricing/`, `coupons/`, `api/`) y migrar los parsers de Rappi/Uber Eats ya funcionales a esa estructura.
4. Implementar el frontend en Next.js siguiendo la sección de Diseño (paleta, tipografía, componentes, micro-interacciones) tal como quedó definida en el lienzo.
5. Configurar el proyecto en AWS (Lambda + Function URL, Supabase) desde el inicio, aunque sea con un endpoint mínimo, para no dejar el "ship gate" para el final.
6. Documentar la conexión del coding agent a AWS (requisito del hackathon) desde las primeras pruebas de despliegue.
7. Una vez completos los 3 backends: diseñar el experimento de muestreo de precios (15-20 productos cada 5 min durante 48-72h) para detectar patrones de precios dinámicos.

## Fecha límite
**2 de octubre de 2026** - entrega de proyecto para el hackathon "Zero to Shipped" (AWS).
