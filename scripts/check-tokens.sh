#!/bin/bash
# Verifica el estado actual de los tokens de Rappi y UberEats.
# Uso: bash scripts/check-tokens.sh

set -e
cd "$(dirname "$0")/.."

python3 - <<'EOF'
import base64, json, os, re, time, datetime, sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: instala requests: pip install requests")
    sys.exit(1)

# ── Leer .env ────────────────────────────────────────────────────────────────
env = {}
for line in Path(".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    env[k.strip()] = v.strip()

# ── UberEats: decodificar jwt-session (sin llamada a la API) ─────────────────
print("=== UberEats jwt-session ===")
cookie = env.get("UBEREATS_COOKIE_STRING", "")
m = re.search(r'jwt-session=([^;]+)', cookie)
if m:
    try:
        payload = m.group(1).split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.b64decode(payload))
        iat = datetime.datetime.fromtimestamp(data["iat"], tz=datetime.timezone.utc)
        exp = datetime.datetime.fromtimestamp(data["exp"], tz=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        age = now - iat
        active_h = int(age.total_seconds() // 3600)
        active_m = int((age.total_seconds() % 3600) // 60)
        remaining = exp - now
        secs = remaining.total_seconds()
        if secs > 0:
            h = int(secs // 3600)
            m2 = int((secs % 3600) // 60)
            if h > 4:
                status = f"VÁLIDO — quedan {h}h {m2}m"
            elif h > 0:
                status = f"ATENCIÓN — quedan solo {h}h {m2}m, rota pronto"
            else:
                status = f"ATENCIÓN — quedan solo {m2}min, rota YA"
        else:
            h_ago = abs(int(secs // 3600))
            status = f"EXPIRADO hace {h_ago}h — rota la cookie en .env y corre deploy.sh"
        print(f"  Capturado: {iat.strftime('%Y-%m-%d %H:%M')} UTC (lleva {active_h}h {active_m}m activo)")
        print(f"  Estado: {status}")
        print(f"  Expira: {exp.strftime('%Y-%m-%d %H:%M')} UTC")
    except Exception as e:
        print(f"  No se pudo decodificar jwt-session: {e}")
else:
    print("  jwt-session no encontrado en UBEREATS_COOKIE_STRING")

print()

# ── Rappi: llamada real para verificar ───────────────────────────────────────
print("=== Rappi Bearer token ===")
token = env.get("RAPPI_TOKEN", "")
device_id = env.get("RAPPI_DEVICE_ID", "")

if not token:
    print("  RAPPI_TOKEN no encontrado en .env")
else:
    # Extraer timestamp de creación directo del Fernet token
    try:
        import base64, struct
        fernet_b64 = token[3:] if token.startswith("ft.") else token
        raw = base64.urlsafe_b64decode(fernet_b64 + "=" * (-len(fernet_b64) % 4))
        ts = struct.unpack(">Q", raw[1:9])[0]
        created_at = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        age = now - created_at
        active_h = int(age.total_seconds() // 3600)
        active_m = int((age.total_seconds() % 3600) // 60)
        print(f"  Capturado: {created_at.strftime('%Y-%m-%d %H:%M')} UTC (lleva {active_h}h {active_m}m activo)")
    except Exception:
        pass

    url = "https://services.mxgrability.rappi.com/api/web-gateway/web/restaurants-bus/store/id/1923772704/"
    headers = {
        "authorization": f"Bearer {token}",
        "app-version": "1.162.2",
        "deviceid": device_id,
        "content-type": "application/json; charset=UTF-8",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "accept": "application/json",
        "accept-language": "es-MX",
    }
    lat = float(env.get("DEFAULT_LAT", "24.7950"))
    lng = float(env.get("DEFAULT_LNG", "-107.4310"))
    body = {"lat": lat, "lng": lng, "store_type": "restaurant",
            "is_prime": False, "prime_config": {"unlimited_shipping": False}}
    try:
        t0 = time.time()
        resp = requests.post(url, headers=headers, json=body, timeout=10)
        elapsed = time.time() - t0
        if resp.status_code == 200:
            data = resp.json()
            products = sum(len(c.get("products", [])) for c in data.get("corridors", []))
            print(f"  Estado: VÁLIDO — {products} productos, envío ${data.get('delivery_price','?')}")
        elif resp.status_code == 401:
            print("  Estado: EXPIRADO — actualiza RAPPI_TOKEN en .env y corre rotate-rappi-token.sh")
        elif resp.status_code == 429:
            print("  Estado: Rate limit (espera ~5min antes de volver a probar)")
        else:
            print(f"  Estado: Error inesperado HTTP {resp.status_code}")
        print(f"  Tiempo de respuesta: {elapsed:.2f}s")
    except Exception as e:
        print(f"  Error de conexión: {e}")

print()
print("Para rotar tokens:")
print("  UberEats: actualiza UBEREATS_COOKIE_STRING en .env → bash scripts/deploy.sh")
print("  Rappi:    actualiza RAPPI_TOKEN en .env → bash scripts/rotate-rappi-token.sh")
EOF
