#!/usr/bin/env python3
"""
Captura automática de cookies/tokens de Rappi y Uber Eats usando Playwright.

Uso:
  Primera vez:  python rotate.py --setup
                (abre navegador, haces login en ambas plataformas, cierras)
  Rotación:     python rotate.py
                (captura cookies/token y actualiza .env)
  Solo Rappi:   python rotate.py --rappi
  Solo UE:      python rotate.py --ubereats

Requiere: pip install playwright && playwright install chromium
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: Playwright no está instalado.")
    print("Instálalo con: pip install playwright && playwright install chromium")
    sys.exit(1)

# Rutas
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
PROFILE_DIR = SCRIPT_DIR / ".browser-profile"

# URLs
RAPPI_STORE_URL = "https://www.rappi.com.mx/restaurantes/900022583-little-caesars"
UBEREATS_URL = "https://www.ubereats.com/mx"
BRAVE_PATH = "/usr/bin/brave-browser"
BRAVE_PROFILE_DIR = SCRIPT_DIR / ".brave-profile"


def _update_env(key: str, value: str) -> bool:
    """Actualiza una variable en .env. Retorna True si se actualizó."""
    if not ENV_FILE.exists():
        print(f"ERROR: No se encontró {ENV_FILE}")
        return False

    content = ENV_FILE.read_text()
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)

    if pattern.search(content):
        new_content = pattern.sub(f"{key}={value}", content)
    else:
        new_content = content.rstrip() + f"\n{key}={value}\n"

    ENV_FILE.write_text(new_content)
    return True


def setup(pw):
    """Abre los navegadores para que el usuario haga login manual."""
    print("=== SETUP ===")
    print("Se abrirán 2 navegadores (uno para cada plataforma).\n")

    # --- Uber Eats: Chromium de Playwright (login con email/password) ---
    print("--- Uber Eats (Chromium) ---")
    print("Haz login con email y contraseña. Cierra cuando termines.\n")
    browser_ue = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        viewport={"width": 1280, "height": 800},
        locale="es-MX",
    )
    page = browser_ue.new_page()
    page.goto("https://www.ubereats.com/mx")
    try:
        page.wait_for_event("close", timeout=0)
    except Exception:
        pass
    try:
        browser_ue.close()
    except Exception:
        pass
    print("  Sesión de Uber Eats guardada.\n")

    # --- Rappi: Brave real (permite Google OAuth) ---
    print("--- Rappi (Brave) ---")
    print("Haz login con Google. Cierra cuando termines.\n")
    browser_rappi = pw.chromium.launch_persistent_context(
        executable_path=BRAVE_PATH,
        user_data_dir=str(BRAVE_PROFILE_DIR),
        headless=False,
        viewport={"width": 1280, "height": 800},
        locale="es-MX",
    )
    page = browser_rappi.new_page()
    page.goto("https://www.rappi.com.mx")
    try:
        page.wait_for_event("close", timeout=0)
    except Exception:
        pass
    try:
        browser_rappi.close()
    except Exception:
        pass
    print("  Sesión de Rappi guardada.\n")

    print("Setup completo. Ahora puedes correr: python rotate.py")


def capture_rappi(pw) -> bool:
    """Captura el Bearer token de Rappi interceptando llamadas a la API."""
    print("\n=== Capturando token de Rappi ===")

    browser = pw.chromium.launch_persistent_context(
        executable_path=BRAVE_PATH,
        user_data_dir=str(BRAVE_PROFILE_DIR),
        headless=False,
        viewport={"width": 1280, "height": 800},
        locale="es-MX",
    )

    page = browser.new_page()
    token_found = None

    def handle_request(request):
        nonlocal token_found
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ft.") and not token_found:
            token_found = auth.replace("Bearer ", "")
            print(f"  Token capturado ({len(token_found)} chars)")

    page.on("request", handle_request)

    print("  Navegando a Rappi...")
    try:
        page.goto(RAPPI_STORE_URL, wait_until="domcontentloaded")
    except Exception:
        pass  # El usuario puede haber cerrado el navegador

    # Esperar a que se dispare alguna llamada con el token
    for _ in range(30):
        if token_found:
            break
        time.sleep(1)

    if not token_found:
        print("  No se detectó el token automáticamente.")
        print("  Navega a cualquier restaurante en Rappi en el navegador abierto.")
        print("  Esperando... (máx 2 minutos)")
        for _ in range(120):
            if token_found:
                break
            time.sleep(1)

    try:
        browser.close()
    except Exception:
        pass  # El usuario ya cerró el navegador

    if token_found:
        if _update_env("RAPPI_TOKEN", token_found):
            print(f"  .env actualizado con RAPPI_TOKEN")
            return True
    else:
        print("  ERROR: No se pudo capturar el token.")
        print("  Verifica que tengas sesión activa: python rotate.py --setup")
        return False


def capture_ubereats(pw) -> bool:
    """Captura las cookies de Uber Eats del perfil del navegador."""
    print("\n=== Capturando cookies de Uber Eats ===")

    browser = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        viewport={"width": 1280, "height": 800},
        locale="es-MX",
    )

    page = browser.new_page()
    print("  Navegando a Uber Eats...")
    page.goto(UBEREATS_URL, wait_until="domcontentloaded")

    # Esperar a que la página cargue y las cookies se establezcan
    time.sleep(5)

    cookies = browser.cookies(["https://www.ubereats.com"])

    try:
        browser.close()
    except Exception:
        pass  # El usuario ya cerró el navegador

    if not cookies:
        print("  ERROR: No se encontraron cookies.")
        print("  Verifica que tengas sesión activa: python rotate.py --setup")
        return False

    # Mostrar cookies capturadas para debug
    cookie_names = {c["name"] for c in cookies}
    print(f"  Cookies encontradas: {', '.join(sorted(cookie_names))}")

    # Verificar que las cookies críticas existan
    critical = {"jwt-session", "dId"}
    missing = critical - cookie_names
    if missing:
        print(f"  ADVERTENCIA: Faltan cookies críticas: {', '.join(missing)}")
        print("  Probablemente no tienes sesión activa. Corre: python rotate.py --setup")
        return False

    # Construir cookie string en el mismo formato que usa el .env
    cookie_string = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

    if _update_env("UBEREATS_COOKIE_STRING", cookie_string):
        print(f"  .env actualizado con UBEREATS_COOKIE_STRING ({len(cookies)} cookies)")

        # Mostrar info del JWT si existe
        jwt_cookie = next((c for c in cookies if c["name"] == "jwt-session"), None)
        if jwt_cookie:
            try:
                import base64
                payload = jwt_cookie["value"].split(".")[1]
                payload += "=" * (-len(payload) % 4)
                data = json.loads(base64.b64decode(payload))
                from datetime import datetime, timezone
                exp = datetime.fromtimestamp(data["exp"], tz=timezone.utc)
                print(f"  jwt-session expira: {exp.strftime('%Y-%m-%d %H:%M')} UTC")
            except Exception:
                pass

        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Captura cookies/tokens de Rappi y Uber Eats")
    parser.add_argument("--setup", action="store_true", help="Login manual (primera vez)")
    parser.add_argument("--rappi", action="store_true", help="Solo capturar token de Rappi")
    parser.add_argument("--ubereats", action="store_true", help="Solo capturar cookies de UE")
    args = parser.parse_args()

    # Si no se especifica plataforma, capturar ambas
    both = not args.rappi and not args.ubereats and not args.setup

    with sync_playwright() as pw:
        if args.setup:
            setup(pw)
            return

        results = {}

        if args.rappi or both:
            results["rappi"] = capture_rappi(pw)

        if args.ubereats or both:
            results["ubereats"] = capture_ubereats(pw)

        # Resumen
        print("\n=== Resumen ===")
        for platform, ok in results.items():
            status = "OK" if ok else "FALLÓ"
            print(f"  {platform}: {status}")

        if all(results.values()):
            print("\n.env actualizado. Para aplicar en Lambda:")
            print("  bash scripts/rotate-rappi-token.sh   (si rotaste Rappi)")
            print("  bash scripts/deploy.sh               (si rotaste UE)")
        elif any(results.values()):
            print("\nAlgunas capturas fallaron. Revisa los errores arriba.")
        else:
            print("\nNada se capturó. Corre primero: python rotate.py --setup")


if __name__ == "__main__":
    main()
