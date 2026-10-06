"""
Health check de conectores: verifica que las cookies/tokens de Rappi y Uber Eats
sigan funcionando. Se ejecuta periódicamente vía EventBridge.
Si detecta fallo, envía email de alerta vía Resend.
"""
import os
import requests as http_requests
from datetime import datetime, timezone

from kupi.connectors.rappi.connector import RappiConnector
from kupi.connectors.ubereats.connector import UberEatsConnector
from kupi.core.config import DEFAULT_LAT, DEFAULT_LNG

# Tiendas "probe" para verificar — solo necesitamos que respondan, no importa cuál
# Usar IDs de tiendas estables (franquicias grandes que no cierran)
_PROBE_RAPPI_STORE = os.getenv("PROBE_RAPPI_STORE", "1923220071")      # Pizza Hut Culiacán
_PROBE_UE_STORE = os.getenv("PROBE_UE_STORE", "793b1eae-e077-44d0-8744-cf23f54fec50")  # Little Caesars Humaya UE

_ALERT_EMAIL = os.getenv("ALERT_EMAIL", "joseangelgap@gmail.com")


def _send_alert(subject: str, body_html: str) -> bool:
    """Envía email de alerta vía Resend. Retorna True si se envió."""
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        print("[health_check] RESEND_API_KEY no configurado, no se puede alertar")
        return False

    resp = http_requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
        json={
            "from": "Kupi <onboarding@resend.dev>",
            "to": [_ALERT_EMAIL],
            "subject": subject,
            "html": body_html,
        },
        timeout=10,
    )
    sent = resp.status_code == 200
    if not sent:
        print(f"[health_check] Error enviando email: {resp.status_code} {resp.text}")
    return sent


def _check_rappi() -> dict:
    """Verifica que el token de Rappi funcione (HTTP 200 = token válido)."""
    try:
        r = RappiConnector()
        # Usamos _fetch_store directamente: si el token es inválido lanza 401,
        # si la tienda está cerrada igual retorna 200 con data válida.
        data = r._fetch_store(_PROBE_RAPPI_STORE, DEFAULT_LAT, DEFAULT_LNG)
        status = data.get("status", "unknown")
        n_products = sum(
            len(c.get("products", []))
            for c in data.get("corridors", [])
        )
        return {
            "platform": "rappi",
            "ok": True,
            "store_status": status,
            "products": n_products,
        }
    except Exception as e:
        return {"platform": "rappi", "ok": False, "error": str(e)}


def _check_ubereats() -> dict:
    """Intenta obtener el menú de una tienda Uber Eats. Retorna status."""
    try:
        ue = UberEatsConnector()
        products = ue.fetch_menu(_PROBE_UE_STORE, DEFAULT_LAT, DEFAULT_LNG)
        if products:
            return {"platform": "ubereats", "ok": True, "products": len(products)}
        return {"platform": "ubereats", "ok": False, "error": "0 productos (tienda cerrada o cookies inválidas)"}
    except Exception as e:
        return {"platform": "ubereats", "ok": False, "error": str(e)}


def run() -> dict:
    """
    Ejecuta health check de todos los conectores.
    Envía alerta por email si alguno falla.
    Retorna dict con resultados para logging.
    """
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "timestamp": now,
        "rappi": _check_rappi(),
        "ubereats": _check_ubereats(),
    }

    failures = []
    if not results["rappi"]["ok"]:
        failures.append(f"<b>Rappi</b>: {results['rappi']['error']}")
    if not results["ubereats"]["ok"]:
        failures.append(f"<b>Uber Eats</b>: {results['ubereats']['error']}")

    results["all_ok"] = len(failures) == 0

    if failures:
        platform_names = []
        if not results["rappi"]["ok"]:
            platform_names.append("Rappi")
        if not results["ubereats"]["ok"]:
            platform_names.append("Uber Eats")

        subject = f"Kupi: cookies caídas — {', '.join(platform_names)}"
        body = (
            f"<h2>Alerta de conectores — Kupi</h2>"
            f"<p>El health check detectó que los siguientes conectores fallaron:</p>"
            f"<ul>{''.join(f'<li>{f}</li>' for f in failures)}</ul>"
            f"<p>Probablemente las cookies/tokens expiraron. "
            f"Hay que capturar credenciales frescas y actualizar Parameter Store.</p>"
            f"<p><b>Pasos:</b></p>"
            f"<ol>"
            f"<li>Abrir el navegador con sesión activa en la plataforma</li>"
            f"<li>Capturar cookies/token desde DevTools</li>"
            f"<li>Actualizar .env y correr el script de rotación</li>"
            f"</ol>"
            f"<p><small>Health check ejecutado: {now}</small></p>"
        )
        sent = _send_alert(subject, body)
        results["alert_sent"] = sent
        print(f"[health_check] FALLO: {', '.join(platform_names)}. Alerta enviada: {sent}")
    else:
        print(f"[health_check] OK — Rappi: {results['rappi']['products']} productos, "
              f"UE: {results['ubereats']['products']} productos")

    return results
