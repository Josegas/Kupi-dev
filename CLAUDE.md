# Kupi - Resumen técnico (para continuar en Claude Code)

## Qué es Kupi
Metabuscador de precios de comida a domicilio (Rappi, Uber Eats, DiDi Food) en México. Muestra el precio final real (producto + envío + cuota de servicio) en tiempo real para comparar plataformas. Incluye sistema de favoritos con alertas de precio, cupones, y autenticación con Supabase.

## Contexto del proyecto
- Kupi nació en el hackathon **AWS "Zero to Shipped"** (18 sept – 2 oct 2026). El hackathon ya se entregó, está desplegado en AWS con URL pública y cumple todos los requisitos del hackathon. Actualmente en revisión por los jueces.
- **Este repo (`Kupi-dev`)** es el repo de **desarrollo activo**, creado el 4 de octubre de 2026 para continuar construyendo el producto con features nuevas, mejoras y evolución del código sin afectar la entrega del hackathon.
- **El repo original (`Kupi`, github: Josegas/Kupi) está congelado**: está en revisión por los jueces del hackathon y lo entregado se queda tal cual. No se modifica nada ahí, ni siquiera fixes de bugs. Todo cambio se hace solo en `Kupi-dev`.
- Kupi-dev tampoco debe compartir estado con el desplegado: nada de copiar cookies/sesiones del `.env` del repo original (comparten la misma cuenta de Uber Eats y las pruebas locales llenan su tope de carritos).
- El proyecto tiene intención real de crecer como producto más allá del hackathon - la arquitectura se decidió pensando en esa escala futura.

---

## Flujo de trabajo con Claude Code
- **Control de commits manual**: Claude Code **no** puede hacer `git commit` ni modificar el control de versiones por su cuenta. Siempre debe pedir autorización expresa antes de realizar cualquier commit o alteración en el repositorio.
- **Siempre usar pnpm, nunca npm.** Para cualquier operación de Node.js (install, dev, build, etc.) usar exclusivamente `pnpm`. npm está prohibido por problemas de seguridad.
- **Presupuesto: $0, sin excepciones.** No activar, aprovisionar ni dejar corriendo ningún recurso de AWS (ni de ningún otro servicio) que pueda generar un cobro, ni siquiera "solo por probar" - esto no es negociable ni con permiso explícito caso por caso: si algo puede llegar a cobrar, se evita por completo o se reemplaza por una alternativa genuinamente gratuita antes de usarlo.
- **Pedir permiso obligatorio antes de**: cualquier `git commit`, `git push`, cambios estructurales de código, modificar los parsers de Rappi/Uber Eats ya funcionando, borrar o crear archivos, o cualquier acción sobre AWS y la infraestructura.
- Claude Code solo puede proponer los cambios o mostrar el código, pero el dueño del proyecto es quien revisa, aprueba y ejecuta los commits para que cada cambio refleje exactamente lo hecho por él.

---

## Estado actual del proyecto (actualizado 7 oct 2026)

### Lo que ya funciona end-to-end

**Backend (Python + FastAPI):**
- Conector Rappi completo: menú, cotización individual, carrito multi-producto, búsqueda de restaurantes
- Conector Uber Eats completo: menú (getStoreV1), cotización con desglose real (createDraftOrderV2 → getCheckoutPresentationV1), carrito multi-producto, auto-customización de productos con opciones obligatorias
- Conector DiDi parcial: scraping web público (solo precios de producto, sin delivery fee ni cuota de servicio)
- Worker proxy en Cloudflare para Uber Eats (evita bloqueo de IPs de AWS)
- 18+ endpoints en la API: `/search`, `/compare`, `/compare-cart`, `/menu/combined`, `/products/featured`, `/products/deals`, `/stores/status`, `/coupons`, `/favorites/*`, `/alerts/*`, `/proxy/image`, etc.
- Rate limiting por IP (30 búsquedas/min), caché TTL, request coalescing
- Filtros: blacklist de tiendas no-comida (OXXO, farmacias), normalización de nombres, detección de variantes

**Frontend (Next.js 15 + React 19 + Tailwind 4):**
- Landing page con hero animado (GSAP), video de fondo
- Búsqueda de restaurantes con filtros por categoría y plataforma
- Comparación dinámica de precios entre plataformas
- Carrito multi-producto: contexto con validación de plataformas en común (cart.tsx), CartBar con UI expandible, comparación integrada en CompareClient.tsx, límite de 10 items, conectado al endpoint `/compare-cart`
- Menú del restaurante (CompareClient.tsx): los filtros de plataforma (Todo / Ambas apps / Solo Rappi / Solo Uber Eats) y las etiquetas "Solo X" solo aparecen si el menú trae productos de las dos apps; se ocultan los filtros sin productos. Si solo hay una app, el subtítulo dice "En tu zona este restaurante solo está disponible en X".
- Errores de `/compare`, `/compare-cart` y `/menu/combined`: 404 con mensaje legible en vez de 502 con JSON técnico
- Sistema de favoritos con historial de precios y alertas
- Página de deals (productos baratos verificados con checkout completo)
- Página de cupones
- Login con Supabase Auth (email/password + Google OAuth)
- Toggle de tema (claro/oscuro) e idioma (es/en)
- Proxy de imágenes con caché

**Base de datos (Supabase Postgres):**
- Tablas: `restaurants`, `user_favorites`, `price_snapshots`, `price_alerts`, `alert_notifications`, `coupons`
- Auto-populate: las búsquedas registran restaurantes automáticamente en background
- Storage: imágenes de restaurantes subidas a CDN de Supabase

**Jobs:**
- Price sampler: cada 6h vía EventBridge, samplea precios de productos en favoritos, evalúa alertas, envía emails con Resend si hay caída de precio >= threshold
- Health check de conectores: verifica que tokens/cookies de Rappi y UE sigan funcionando, envía alerta por email si alguno falla (`kupi/jobs/health_check.py`, endpoint manual `GET /health/connectors`, invocable por EventBridge con `{"job": "health_check"}`)

**Herramientas de mantenimiento (scripts/):**
- `check-tokens.sh` — muestra estado y expiración de tokens/cookies (decodifica JWT de UE, prueba llamada real a Rappi)
- `rotate-rappi-token.sh` — sube token de .env a Parameter Store y reinicia Lambda
- `rotate-cookies/rotate.py` — script con Playwright que captura cookies/tokens automáticamente desde el navegador y actualiza .env. Usa Brave para ambas plataformas, con perfil persistente: no requiere login cada vez, solo `python rotate.py`

**Despliegue:**
- Backend: AWS Lambda + Function URL (sin API Gateway) + Mangum
- Frontend: AWS Amplify Hosting
- Secretos: AWS Parameter Store (tier estándar, gratis)
- BD: Supabase (plan gratuito, no AWS)
- Emails: Resend (free tier, 100/día)
- Proxy UE: Cloudflare Worker

### Lo que está parcial

- **DiDi Food**: solo scraping de web pública. Sin delivery fee ni cuota de servicio. Bloqueado por hardware (necesita Honor 20 con scrcpy + Frida + mitmproxy para capturar endpoints de la API privada).

### Pendientes

1. **DiDi Food completo** — Capturar endpoints de API privada con hardware real (Honor 20).
2. **Dominio propio** — Namecheap con GitHub Student Pack.
3. **Experimento de precios dinámicos** — Muestreo intensivo (15-20 productos cada 5 min, 48-72h) para detectar patrones.
4. **Configurar EventBridge para health check** — Cuando Kupi-dev tenga su propia Lambda, crear regla EventBridge con `{"job": "health_check"}` cada 4-6 horas (solo aplica a la infra de Kupi-dev, no tocar la del hackathon).
5. **Ofertas del canal de WhatsApp de Rappi** (pendiente desde 6 oct 2026) — El canal "Rappi México" (`https://www.whatsapp.com/channel/0029Vavdy1EBFLga5N5T5d1J`) publica promos de precio por tiempo limitado, no códigos (ej. "Caffenio: Mexicano Caliente — $19" + enlace `rappi.sng.link` que en web solo abre el inicio de Rappi). Las publicaciones no son públicas: requieren entrar a WhatsApp.
   - **Hallazgo (7 oct 2026, promo "Frutos Prohibidos — Chilaquiles medianos a $78", CDMX):** la promo **sí existe en Rappi pero depende de la dirección**. En la app, con dirección registrada en Ámsterdam 244, Hipódromo, CDMX, aparece una sección "Ahorros Exclusivos" con Chilaquiles medianos $77.50 (-40%, antes $129) y Pecado original $122.50 (-30%). Con dirección en Culiacán no aparece.
   - Sin embargo, el endpoint web que usa Kupi (`store/id` con lat/lng de CDMX) sigue dando $129, `real_price` = `price`, `discounts[]` vacío y sin pasillo "Ahorros Exclusivos" (probado en Frutos Prohibidos - Orizaba, `990008239`). El checkout de Rappi falla con 400 para tiendas de CDMX porque `change-address` no puede mover la dirección de la cuenta.
   - **Las promos son solo de la app de Rappi:** se probó Rappi web de escritorio y web móvil (`rappi.com.mx/promociones`, que es a donde manda el enlace) con la dirección de CDMX, y en ninguna aparece la oferta ni "Ahorros Exclusivos".
   - También existe `web.rappi.com.mx/promotions` (sitio nuevo, renderizado en servidor). Su lista sale de `GET web.rappi.com.mx/_server-islands/PromotionsContent` y cada producto trae `pricing.originalPrice`, `currentPrice` y `offerTag`. Pero las 30 "promociones" que mostró en CDMX tenían `originalPrice: null` y `offerTag` vacío: son recomendaciones, no ofertas. Si algún día trae descuentos reales, ahí se verían. La ficha de producto (`_server-islands/RestProductDetailContent`) trae `pricing.price` y `basePrice`.
   - **Siguiente paso recomendado:** capturar el tráfico de la **app** de Rappi con el mismo montaje planeado para DiDi (Honor 20 + scrcpy + mitmproxy + Frida para saltar certificate pinning), para encontrar el endpoint de "Ahorros Exclusivos". Con eso Kupi consultaría promos por zona directo de Rappi (todas, no solo las del canal). Conviene hacerlo junto con el pendiente 1 (DiDi), porque el montaje es el mismo.
   - **HALLAZGO (7 oct 2026) — captura de la app Rappi lograda.** Montaje que funcionó en el Honor 20 (YAL-L21, Android 10, sin root): APK de Rappi (4 splits) sacado con `adb`, parcheado con `apk-mitm` + apktool 2.12.1 (hubo que corregir a mano dos `meta-data` con `android:resource="@null"` → `@mipmap/ic_rappi_launcher` para que Android 10 instalara); el APK parcheado confía en certificados de usuario (`nsc_mitm.xml`); certificado de mitmproxy instalado en el celular como **VPN y apps** (no wifi); proxy wifi manual apuntando a la laptop. Con eso el tráfico HTTPS de Rappi se descifra (pinning vencido). Login en la app con **número de teléfono** (Google no sirve en APK re-firmado).
   - **Endpoint de ofertas encontrado:** `POST https://services.mxgrability.rappi.com/api/home-router/context/content`.
     - Body: `{"context":"main_home","stores":[],"offset":0,"limit":20,"state":{"lat":"...","lng":"...","is_prime":"false","city_id":"166","city":"Culiacán","address_id":"2182736325","microzone_id":"3660"},"additional_data":null,"store_type":null}`.
     - Headers móviles: `authorization: Bearer ft.gAAAA...` (mismo formato Fernet que ya usa Kupi), `deviceid`, `user_id`, `app-version: 90037`, `app-version-name: 8.40.20261001-90037`, `store-platform: google`, `user-agent: Dalvik/... Android 10`.
     - Respuesta (~186 KB): cada producto trae `price` (con descuento), `real_price` (normal), `discount`, `discountPercentage`, `have_discount`, `discount_type`, `discounts`. Confirmado con productos reales en descuento (ej. "Cape Cod Papas Fritas $189 antes $234").
   - **Esto confirma que las ofertas SÍ están en los datos de la app** (no en la web).
   - **CONFIRMADO desde el backend (7 oct 2026), ya NO se necesita el celular para esto:**
     - El **token web actual de Kupi (`RAPPI_TOKEN`) funciona en los endpoints móviles** (HTTP 200). No hace falta token especial de la app.
     - La cuenta de Rappi de Kupi es la **misma** del celular; ya tiene direcciones registradas en varias ciudades (`GET /api/ms/users-address/addresses`): cada una da `id` (=address_id), `city_id` y `zone.id` (=microzone_id). Ej: Culiacán→zona 3660, CDMX Ámsterdam→zona 3613 "Condesa-Roma", Monterrey, etc.
     - El feed de ofertas se replica con `POST /api/home-router/context/content`, **`offset:1`** (en offset 0 no hay ofertas; están en la página 1), `context:"main_home"` y el `state` de la dirección. Probado con el token de Kupi: devolvió **26 productos con descuento** (`real_price` > `price`), igual que la captura.
   - **Siguiente paso = puro desarrollo en Kupi (sin celular):** módulo que (a) para cada zona registrada recorra los offsets de `home-router/context/content` y extraiga productos en oferta (`name`, `price`, `real_price`, `discount`, `discountPercentage`), con headers móviles (`app-version: 90037`, `user-agent: Dalvik/... Android 10`, `deviceid`, Bearer de Kupi); (b) para zonas nuevas, registre una dirección vía POST a users-address para obtener su address_id/zona; (c) guarde y muestre esas ofertas en Kupi. Scripts de referencia en scratchpad: `analyze_flows.py` (análisis de captura), `test_rappi_mobile.py` (prueba del endpoint con el token de Kupi).

   ### Plan de OFERTAS de restaurante (Rappi + Uber Eats) — actualizado 8 oct 2026
   El usuario SÍ quiere las ofertas/"Ahorros Exclusivos" de cada restaurante, y el precio final. Panorama confirmado para ambas plataformas:

   **Dos tipos de ofertas en Rappi, no confundir:**
   - **Descuentos de súper/market** (Rappi Turbo): el feed `home-router/context/content` (offset 1) trae productos de abarrotes con `real_price`>`price` (ej. Cape Cod, Ruffles, aguacate). **NO son comida de restaurante → no sirven para Kupi.**
   - **Ofertas de restaurante** (las del canal de WhatsApp, ej. Frutos Prohibidos chilaquiles -40%): viven en la página del restaurante, endpoint **`POST /api/consumer-ui/v2/context/content/rest-store-detail`**. Body: `{"context":"restaurants_store_detail","offset":0,"limit":20,"state":{"store_id":"...","brand_id":"...","lat","lng","city_id","address_id","microzone_id",...},"store_type":"restaurant"}`. Funciona con el token de Kupi. Ojo: hay ofertas "Oferta Exclusiva Pro" (requieren Rappi Prime) — esas NO aplican a un usuario normal, no mostrarlas como precio para todos (regla de precio exacto). Solo las ofertas normales.

   **Uber Eats:** mismo tipo de ofertas. En `getStoreV1` (que Kupi ya consulta) vienen `promotion` (null si no hay), `hasStorePromotion`, y `priceTagline` por producto (precio rebajado; cuando hay descuento suele venir precio original tachado). Ofertas por tienda/hora.

   **Precio final exacto: YA resuelto en ambas.** Los conectores de Rappi y UE ya hacen el checkout completo (producto + envío + cuota). Para cualquier producto en oferta, Kupi ya puede calcular el total exacto. No hace falta nada nuevo para el precio final.

   **Lo único pendiente (requiere una PROMO ACTIVA, de día):** confirmar los campos exactos que marcan un producto rebajado en `rest-store-detail` (Rappi) y en `getStoreV1` (UE), y distinguir descuento-normal de Pro. Las ofertas dependen mucho de la hora (de madrugada casi no hay). Cuando el usuario vea una promo de restaurante activa, probar el endpoint de esa tienda desde el backend y cerrar la lógica de extracción.

   **Diseño del módulo de ofertas (backend, sin celular):** recorrer `rest-store-detail` de los restaurantes de cada zona registrada → detectar productos con descuento (no-Pro) → por cada uno, usar el checkout ya existente para el precio final → guardar en Supabase y mostrar en Kupi como "ofertas". Aplica igual para UE con `getStoreV1`/`promotion`.
   - Si no → script local con Playwright + número dedicado leyendo WhatsApp Web, parseo con reglas (tienda, producto, precio). Riesgo: va contra los términos de WhatsApp (baneo del número) y se rompe con cambios de la página. Extraer con IA tendría costo (choca con presupuesto $0).

---

## Gestión de cookies/tokens

### Rappi
- **Qué se necesita**: Bearer token Fernet (`RAPPI_TOKEN`) + Device ID UUID fijo (`RAPPI_DEVICE_ID`)
- **Dónde se guarda**: `.env` (local), Parameter Store `/kupi/rappi-token` (Lambda)
- **Cómo se rota**: `python scripts/rotate-cookies/rotate.py --rappi` (abre Brave con perfil persistente, captura token automáticamente, actualiza .env). Luego `bash scripts/rotate-rappi-token.sh` para subir a Parameter Store.

### Uber Eats
- **Qué se necesita**: Cookie string completo (`UBEREATS_COOKIE_STRING`) con `dId`, `jwt-session`, `uev2.id.session_v2`, etc.
- **Dónde se guarda**: `.env` (local), Parameter Store en 2 partes `/kupi/ubereats-cookie-1` + `/kupi/ubereats-cookie-2` (Lambda)
- **Cuenta**: Kupi-dev usa su **propia cuenta de Uber Eats** (correo y contraseña), distinta a la del desplegado. Nunca copiar cookies/`sid` del `.env` del repo original.
- **Cómo se rota**: `python scripts/rotate-cookies/rotate.py --ubereats` (abre Brave con perfil persistente, captura cookies automáticamente, actualiza .env). Luego `bash scripts/deploy.sh` para subir a Parameter Store.
- **Cookies que importan**: `sid` (sesión iniciada; sin ella los menús cargan pero cotizar falla — el script no toca el .env si falta), `uev2.loc` / `uev2.diningMode` / `user_city_ids` (ubicación; sin ellas casi todo sale "Entrega no disponible" — el script las conserva del .env si el navegador no las trae). `cf_clearance` se descarta: está atada a la huella del navegador y con la del conector da 403.
- **La expiración del JWT no es la señal para rotar**: `check-tokens.sh` puede decir "EXPIRADO" mientras Uber Eats sigue aceptando las cookies. Rotar solo cuando falle el health check.
- **Borradores (draft orders)**: cada cotización crea un borrador en la cuenta; Uber Eats limita cuántos puede haber ("Demasiados carritos"). El conector los borra con `discardDraftOrdersV1` después de cotizar (`fetch_price` y `fetch_cart_price`). El desplegado (congelado) no los borra: si ahí sale "Demasiados carritos", hay que vaciar carritos a mano en el navegador de esa cuenta.
- **Mitigación**: Worker de Cloudflare como proxy alternativo + curl_cffi con impersonate="chrome120"

### Flujo de rotación completo
1. Health check detecta fallo → llega alerta por email
2. Correr `python scripts/rotate-cookies/rotate.py` → captura ambos automáticamente (~30 seg)
3. Si la sesión del navegador también expiró: `python scripts/rotate-cookies/rotate.py --setup` → login manual una vez
4. Subir a Lambda: `bash scripts/rotate-rappi-token.sh` y/o `bash scripts/deploy.sh`

### Primera vez (setup de perfiles)
```bash
pip install playwright && playwright install chromium
python scripts/rotate-cookies/rotate.py --setup
```
Abre Brave con dos pestañas: Rappi (login con Google) y Uber Eats (login con la cuenta de Kupi-dev + fijar dirección de entrega en Culiacán). Las sesiones quedan en el perfil local `scripts/rotate-cookies/.brave-profile/`. Se usa Brave y no el Chromium de Playwright porque Google bloquea su login y Cloudflare de Uber Eats lo detiene en la verificación anti-bots.

---

## Referencia técnica de APIs

### RAPPI

#### Endpoint principal - menú de tienda
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

#### Respuesta - campos clave
- `delivery_price`: costo de envío
- `corridors[].products[]`: `product_id`, `name`, `price` (con descuento), `real_price` (sin descuento), `discounts[]`
- `discount_tags[]`: promociones activas
- `eta`, `rating`

#### Notas
- Cloudflare bloquea `curl` desnudo (429) - resolver con headers de navegador real.
- No es bloqueo por IP permanente - esperar 5-10 min si se dispara el rate limit.

#### Cotización de precio (implementado en connector)
Flujo de 3 pasos: PUT carrito → POST recalcular → GET summary-v2. Extrae producto_price, delivery_fee, service_fee, total con promociones aplicadas.

---

### UBER EATS

#### Flujo completo (3 pasos)
```
1. getStoreV1              → catálogo de productos de la tienda
2. createDraftOrderV2      → crea un draft order con el producto (server genera draftOrderUUID)
3. getCheckoutPresentationV1 → con ese draftOrderUUID, trae el desglose real: subtotal, delivery fee, cuota de servicio
```

#### Endpoint principal - menú completo
```
POST https://www.ubereats.com/_p/api/getStoreV1?localeCode=mx
```

**Body**:
```json
{"storeUuid": "793b1eae-e077-44d0-8744-cf23f54fec50", "diningMode": "DELIVERY", "time": {"asap": true}, "cbType": "EATER_ENDORSED"}
```

#### Autenticación
- **No hay Bearer token reutilizable.** Depende de cookies de sesión completas (capturadas del navegador vía DevTools → Application → Cookies).
- Usa `curl_cffi` con `impersonate="chrome120"` para imitar huella TLS de navegador real.
- Usar `curl_cffi.requests.Session()` para que las cookies rotadas entre requests se persistan automáticamente.

#### Estructura de respuesta del catálogo
```
data["catalogSectionsMap"][sectionUUID] → lista de sub-secciones
  └── cada sub-sección:
        payload.standardItemsPayload.catalogItems → lista de productos
          ├── uuid
          ├── title
          ├── itemDescription
          ├── price          (centavos, ej: 18900 = $189.00 MXN)
          └── priceTagline.text  (precio formateado)
```

#### Delivery fee (resuelto)
`fareInfo` de `getStoreV1` NO trae el dato real. El fee real solo aparece tras `createDraftOrderV2` → `getCheckoutPresentationV1` → `fareBreakdown.charges`.

#### Headers críticos para createDraftOrderV2
Sin estos headers, responde HTTP 200 pero body `{"status":"failure","code":"500"}`:
```
accept: */*
accept-language: es-419,es;q=0.5
sec-ch-ua, sec-ch-ua-mobile, sec-ch-ua-platform
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-origin
sec-gpc: 1
priority: u=1, i
referer: <URL completa de la tienda con mod=quickView&modctx=...>
```

#### Personalización obligatoria
Si un producto tiene opciones obligatorias (sabor, tamaño), `createDraftOrderV2` falla con 500 si se manda `customizations: {}` vacío. El conector resuelve esto automáticamente: detecta el fallo, obtiene opciones de `getMenuItemV1`, toma la primera opción de cada grupo obligatorio, y reintenta.

---

### DIDI FOOD - Pausado (bloqueado por hardware)

#### Estado actual
- Conector implementado con scraping de web pública (BeautifulSoup)
- Solo extrae precios de producto (sin envío ni cuota de servicio)
- ~10 sucursales hardcodeadas en stores.json (Culiacán)

#### Endpoints conocidos (sin confirmar, extraídos de config Apollo)
- `c.didi-food.com/feed/indexV3` - feed principal
- `c.didi-food.com/shop/index` - página de restaurante
- `c.didi-food.com/item/detail` - detalle de producto
- `c.didi-food.com/cart/info`, `/order/createV2`

#### Plan de retoma
- Celular Honor 20 disponible (sin rootear, pantalla táctil defectuosa)
- Plan: scrcpy (control vía USB) + Frida + mitmproxy para capturar tráfico real de `didi-food.com`
- El emulador no funciona: Google Maps SDK crashea sin GPU real (swiftshader)

#### CAPTURA LOGRADA (7 oct 2026) — pero bloqueada para producción por firma de peticiones
- **Montaje que funcionó (sin root):** mismo flujo que Rappi. App `com.xiaojukeji.didi.global.customer` (DiDi Food 3.2.2, 3 splits) sacada con adb, parcheada con `apk-mitm` + apktool 2.12.1 (no hizo falta corregir el manifiesto; instaló directo). Certificado mitmproxy ya instalado como "VPN y apps". El tráfico HTTPS de DiDi se descifra bien (el parche basta, no hizo falta Frida para el pinning).
- **Login:** Google NO sirve en el APK re-firmado. Hay que entrar con número/SMS. Ojo: el antifraude de DiDi (captcha + `api-sec.didiglobal.com/.../risk_sdk_check_sync`) **suprime el SMS cuando el proxy está activo**. Solución: iniciar sesión con el **proxy QUITADO** (conexión limpia), y recién después activar el proxy para navegar/capturar. (Confusión aparte: un SMS que no llegaba era por la línea telefónica sin activar, no por DiDi.)
- **Endpoints encontrados (host `c.didi-food.com`):**
  - `POST /shop/indexV3` — página de la tienda
  - `POST /shop/getItemListV3` — menú; productos con `price` (centavos, ej. 15500=$155.00), `priceDisplay`, `sellingPriceDesc`, campos de descuento
  - `POST /cart/setItem`, `/cart/info`, `/cart/updateExt` — carrito
  - `POST /bill/info` — **checkout con el desglose completo**: "Tarifa de servicio", envío, `total_fee` (centavos, ej. 10346=$103.46) y Total. (También `/bill/amount`, `/bill/update`, `/bill/alert`.)
  - `POST /feed/indexHeader`, `/feed/indexFeed` — feed de restaurantes. Ciudad Culiacán = `cityId: 52250100`.
- **BLOQUEO para usarlo en Kupi:** a diferencia de Rappi (Bearer simple que funcionó desde el backend), **DiDi firma cada request con su SDK nativo de seguridad**: headers `wsgsig`, `wsgdid`, `secdd-authentication`, `secdd-challenge`, `x-verify-capability` (JWT), y parámetro de URL `wsgenv`; más un `token` de sesión en el body. Son firmas generadas en código nativo ofuscado sobre el cuerpo + huella del dispositivo. **Replicar esas firmas desde el servidor de Kupi es inviable** sin ingeniería inversa pesada del binario (no vale la pena por ahora).
- **Conclusión:** la captura confirmó que los datos (menú + envío + cuota + total) existen y dónde están, pero DiDi **no se puede integrar como conector de backend** igual que Rappi/UE. Opciones futuras (todas costosas/frágiles): (a) seguir con el scraping web actual (solo precio de producto, sin fees) — es lo que hay hoy; (b) ejecutar las llamadas firmadas a través de un agente en el propio dispositivo/app instrumentada con Frida (llamando a las funciones de firma nativas) — complejo y frágil; (c) revertir el algoritmo `wsgsig` — muy difícil. **Recomendación: dejar DiDi con el scraping actual y no invertir más aquí por ahora.**

---

## Arquitectura

### Patrón: monolito modular
Un solo servicio desplegable (Lambda), organizado internamente en módulos con fronteras claras. Cada conector puede extraerse como servicio propio a futuro sin reescribir lógica de negocio.

### Estructura real del proyecto
```
kupi/
├── core/              # config, modelos compartidos (Product, PriceQuote, QuoteResponse, etc.)
├── connectors/        # un módulo por plataforma, misma interfaz (fetch_menu, fetch_price, fetch_cart_price)
│   ├── rappi/         # conector completo (menú + cotización + carrito + búsqueda)
│   ├── ubereats/      # conector completo (menú + cotización + carrito + auto-customización)
│   └── didi/          # conector parcial (solo scraping web público)
├── catalog/           # supabase_client, restaurants CRUD, coupons, image_store
├── jobs/              # price_sampler (cada 6h vía EventBridge)
├── api/               # FastAPI app (main.py + auth.py + favorites.py + alerts.py)
│
web/                   # frontend Next.js 15 (App Router, React 19, Tailwind 4)
├── app/
│   ├── buscar/        # búsqueda de restaurantes
│   ├── compare/       # comparación de precios
│   ├── cupones/       # listado de cupones
│   ├── deals/         # productos baratos verificados
│   ├── favoritos/     # favoritos + historial + alertas
│   ├── login/         # auth con Supabase
│   ├── components/    # TopNav, RestaurantCard, PlatformCompareCard, CartBar, etc.
│   └── lib/           # api.ts, auth.tsx, cart.tsx, i18n.tsx, location.tsx, supabase.ts
│
lambda_handler.py      # entrada para Lambda (Mangum + router de jobs EventBridge)
```

### Principio de portabilidad
1. **AWS es solo el "sobre"**: `lambda_handler.py` envuelve la app FastAPI con Mangum. Si se mueve a contenedor/VPS, se cambia solo ese archivo.
2. **Datos siempre en Postgres** (Supabase): portable con `pg_dump`/`pg_restore`. Nunca DynamoDB.

### Stack
- **Backend**: Python 3.12 + FastAPI + curl_cffi + Mangum
- **Frontend**: Next.js 15 + React 19 + TypeScript + Tailwind 4 + GSAP
- **BD**: Supabase Postgres (plan gratuito)
- **Auth**: Supabase Auth (email/password + Google OAuth)
- **Emails**: Resend (free tier)
- **Despliegue**: Lambda + Function URL (backend), Amplify Hosting (frontend)
- **Secretos**: AWS Parameter Store (tier estándar, gratis)

---

## Despliegue

- **Backend**: AWS Lambda con Function URL habilitada (sin API Gateway). Free tier permanente (1M invocaciones/mes, 400K GB-seg).
- **Frontend**: AWS Amplify Hosting.
- **BD**: Supabase (`zoncxujbbropduccfumy.supabase.co`), plan gratuito, no toca facturación AWS.
- **Worker proxy UE**: Cloudflare Worker (`kupi-ubereats-proxy.joseangelgap.workers.dev`).
- **Secretos en Lambda**: Parameter Store — `/kupi/rappi-token`, `/kupi/ubereats-cookie-1`, `/kupi/ubereats-cookie-2`, etc.
- **Presupuesto**: $0 estricto. AWS Budget en $0 con alerta por correo. No usar servicios con free tier de 12 meses.

---

## Diseño (UI/UX)

Diseño hecho en lienzo de Claude. Dirección: **web-first, responsivo**.

### Paleta de colores
| Token | Hex | Uso |
|---|---|---|
| `bg` | `#F5F5F3` | Fondo general |
| `surface` | `#FFFFFF` | Tarjetas, nav, inputs |
| `border` | `#E4E4DF` | Bordes |
| `text-primary` | `#1F2323` | Texto principal |
| `text-secondary` | `#6B6558` | Texto secundario |
| `text-muted` | `#9A9384` | Placeholders |
| `brand` | `#C2410C` | Logo, nav activo, badges de marca (naranja) |
| `brand-tint` | `#FCE8DC` | Fondo claro de badges |
| `savings` | `#15803D` | Precio, "Más barato", CTA (verde) — solo para ahorro |
| `savings-tint` | `#EAF6EE` | Fondo de tarjeta más barata |

Solo 2 colores saturados (naranja = marca, verde = ahorro). Si se necesita un tercer estado, usar variaciones de opacidad/tint.

### Tipografía
- **Encabezados / logo**: `Space Grotesk` (500/600/700)
- **Cuerpo / UI**: `IBM Plex Sans` (400/500/600/700)

### Micro-interacciones
```css
.kupi-card{transition:transform .18s ease, box-shadow .18s ease}
.kupi-card:hover{transform:translateY(-3px);box-shadow:0 12px 28px rgba(31,35,35,0.10)}
.kupi-btn{transition:transform .15s ease, filter .15s ease}
.kupi-btn:hover{transform:translateY(-1px);filter:brightness(1.06)}
.kupi-input:focus-within{border-color:#C2410C;box-shadow:0 0 0 3px rgba(194,65,12,0.14)}
```

---

## Seguridad

- **Secretos**: nunca en el repo. `.env` en `.gitignore`. Producción solo vía Parameter Store.
- **Auth de usuarios**: 100% Supabase Auth. Kupi nunca almacena contraseñas.
- **HTTPS**: siempre (Lambda Function URL y Amplify lo dan por defecto).
- **CORS**: restringido al dominio del frontend, nunca `*` en producción.
- **Rate limiting**: implementado en la API (30 búsquedas/min por IP, 60 general/min).
- **IAM**: mínimo privilegio en el rol de Lambda.
- **Logs**: nunca loguear cookies, tokens ni datos de usuarios.
- **Supabase**: conexión SSL (`sslmode=require`).

---

## Fecha límite
**2 de octubre de 2026** - entrega del hackathon (ya entregado, en revisión por jueces).
