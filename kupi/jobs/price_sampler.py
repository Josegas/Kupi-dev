"""
Job de muestreo de precios: captura el precio total real de los productos
que los usuarios tienen en favoritos. Se ejecuta cada 6 horas vía EventBridge.
"""
import os
import requests as http_requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from kupi.connectors.rappi.connector import RappiConnector
from kupi.connectors.ubereats.connector import UberEatsConnector


def _zone(coord: float) -> float:
    """Redondea a 2 decimales (~1 km): zona en la que se cotizan los favoritos."""
    return round(float(coord), 2)


def run() -> dict:
    """Ejecuta el muestreo de precios y la evaluación de alertas."""
    from kupi.catalog.supabase_client import get_client

    try:
        sb = get_client()
    except RuntimeError as e:
        return {"error": str(e)}

    # 1. Obtener productos únicos que alguien tiene en favoritos
    favs_resp = sb.table("user_favorites").select(
        "rappi_product_id, ubereats_product_id, product_name, rappi_store_id, ubereats_store_id, lat, lng"
    ).execute()

    if not favs_resp.data:
        return {"sampled": 0, "alerts_sent": 0}

    # Deduplicar por producto y zona (~1 km): el envío depende de dónde está cada usuario,
    # así que se cotiza en la zona de quien lo guardó. Sin ubicación no se puede cotizar.
    seen = set()
    unique_products = []
    for f in favs_resp.data:
        if f.get("lat") is None or f.get("lng") is None:
            continue
        f = {**f, "lat": _zone(f["lat"]), "lng": _zone(f["lng"])}
        key_tuple = (f.get("rappi_product_id"), f.get("ubereats_product_id"), f["lat"], f["lng"])
        if key_tuple not in seen:
            seen.add(key_tuple)
            unique_products.append(f)

    print(f"[price_sampler] {len(unique_products)} productos únicos a samplear")

    # 2. Samplear precios en paralelo (max 4 workers para no saturar APIs)
    rappi = RappiConnector()
    ubereats = UberEatsConnector()
    snapshots = []

    def sample_one(product: dict) -> list[dict]:
        results = []
        rappi_sid = product.get("rappi_store_id")
        ue_sid = product.get("ubereats_store_id")
        rappi_pid = product.get("rappi_product_id")
        ue_pid = product.get("ubereats_product_id")
        name = product.get("product_name", "")
        lat, lng = product["lat"], product["lng"]

        # Rappi
        if rappi_sid and rappi_pid:
            try:
                menu = rappi.fetch_menu(rappi_sid, lat, lng)
                prod = next((p for p in menu if p.product_id == rappi_pid), None)
                if prod:
                    quote = rappi.fetch_price(rappi_sid, prod, lat, lng)
                    results.append({
                        "rappi_product_id": rappi_pid,
                        "ubereats_product_id": ue_pid,
                        "product_name": name,
                        "platform": "rappi",
                        "product_price": quote.product_price,
                        "delivery_fee": quote.delivery_fee,
                        "service_fee": quote.service_fee,
                        "total": quote.total,
                        "rappi_store_id": rappi_sid,
                        "ubereats_store_id": ue_sid,
                        "lat": lat,
                        "lng": lng,
                    })
            except Exception as e:
                print(f"[price_sampler] Rappi error {rappi_pid}: {e}")

        # UberEats
        if ue_sid and ue_pid:
            try:
                menu = ubereats.fetch_menu(ue_sid, lat, lng)
                prod = next((p for p in menu if p.product_id == ue_pid), None)
                if prod:
                    quote = ubereats.fetch_price(ue_sid, prod, lat, lng)
                    results.append({
                        "rappi_product_id": rappi_pid,
                        "ubereats_product_id": ue_pid,
                        "product_name": name,
                        "platform": "ubereats",
                        "product_price": quote.product_price,
                        "delivery_fee": quote.delivery_fee,
                        "service_fee": quote.service_fee,
                        "total": quote.total,
                        "rappi_store_id": rappi_sid,
                        "ubereats_store_id": ue_sid,
                        "lat": lat,
                        "lng": lng,
                    })
            except Exception as e:
                print(f"[price_sampler] UberEats error {ue_pid}: {e}")

        return results

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(sample_one, p) for p in unique_products]
        for f in as_completed(futures):
            try:
                snapshots.extend(f.result())
            except Exception as e:
                print(f"[price_sampler] error: {e}")

    # 3. Insertar snapshots en Supabase
    if snapshots:
        sb.table("price_snapshots").insert(snapshots).execute()

    print(f"[price_sampler] {len(snapshots)} snapshots guardados")

    # 4. Evaluar alertas
    alerts_sent = _evaluate_alerts(sb, snapshots)

    return {"sampled": len(snapshots), "alerts_sent": alerts_sent}


def _evaluate_alerts(sb, new_snapshots: list[dict]) -> int:
    """
    Compara los precios nuevos con los anteriores.
    Si baja >= threshold_pct y no se notificó en 24h, crea notificación.
    """
    # Obtener alertas activas con info del favorito
    alerts_resp = sb.table("price_alerts").select(
        "*, user_favorites(rappi_product_id, ubereats_product_id, product_name, restaurant_name, lat, lng)"
    ).eq("is_active", True).execute()

    if not alerts_resp.data:
        return 0

    now = datetime.now(timezone.utc)
    cooldown = timedelta(hours=24)
    sent_count = 0

    for alert in alerts_resp.data:
        fav = alert.get("user_favorites", {})
        if not fav:
            continue

        rappi_pid = fav.get("rappi_product_id")
        ue_pid = fav.get("ubereats_product_id")
        if fav.get("lat") is None or fav.get("lng") is None:
            continue
        zlat, zlng = _zone(fav["lat"]), _zone(fav["lng"])

        # Buscar el snapshot nuevo para este producto en la zona del usuario
        new = None
        for s in new_snapshots:
            if s.get("lat") != zlat or s.get("lng") != zlng:
                continue
            if (rappi_pid and s.get("rappi_product_id") == rappi_pid) or \
               (ue_pid and s.get("ubereats_product_id") == ue_pid):
                if new is None or s["total"] < new["total"]:
                    new = s

        if not new:
            continue

        # Buscar el snapshot anterior (el más reciente antes de este batch)
        since = (now - timedelta(days=7)).isoformat()
        prev_query = (
            sb.table("price_snapshots").select("total, platform")
            .eq("platform", new["platform"]).eq("lat", zlat).eq("lng", zlng)
        )

        if rappi_pid:
            prev_query = prev_query.eq("rappi_product_id", rappi_pid)
        elif ue_pid:
            prev_query = prev_query.eq("ubereats_product_id", ue_pid)

        prev_resp = prev_query.gte("sampled_at", since).order("sampled_at", desc=True).limit(2).execute()

        if not prev_resp.data or len(prev_resp.data) < 2:
            continue

        # El segundo es el anterior (el primero es el que acabamos de insertar)
        prev_total = prev_resp.data[1]["total"]
        new_total = new["total"]

        if prev_total <= 0:
            continue

        pct_drop = ((prev_total - new_total) / prev_total) * 100

        if pct_drop < alert.get("threshold_pct", 5):
            continue

        # Verificar cooldown
        last_notified = alert.get("last_notified_at")
        if last_notified:
            last_dt = datetime.fromisoformat(last_notified.replace("Z", "+00:00"))
            if now - last_dt < cooldown:
                continue

        # Crear notificación
        message = (
            f"El precio de {fav.get('product_name', '')} en {fav.get('restaurant_name', '')} "
            f"bajo de ${prev_total:.0f} a ${new_total:.0f} en {new['platform'].title()} "
            f"({pct_drop:.0f}% menos)"
        )

        sb.table("alert_notifications").insert({
            "alert_id": alert["id"],
            "user_id": alert["user_id"],
            "message": message,
            "channel": "email",
        }).execute()

        # Enviar email via Resend
        _send_alert_email(sb, alert["user_id"], fav.get("product_name", ""), message)

        # Actualizar last_notified_at
        sb.table("price_alerts").update({"last_notified_at": now.isoformat()}).eq("id", alert["id"]).execute()

        sent_count += 1
        print(f"[alert] {message}")

    return sent_count


def _send_alert_email(sb, user_id: str, product_name: str, message: str):
    """Envía email de alerta via Resend (free tier: 100 emails/día)."""
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        print("[alert] RESEND_API_KEY no configurado, email no enviado")
        return

    # Obtener email del usuario desde Supabase Auth
    try:
        user = sb.auth.admin.get_user_by_id(user_id)
        email = user.user.email
        if not email:
            print(f"[alert] usuario {user_id} sin email")
            return
    except Exception as e:
        print(f"[alert] error obteniendo email de {user_id}: {e}")
        return

    try:
        resp = http_requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": "Kupi <onboarding@resend.dev>",
                "to": [email],
                "subject": f"Bajo el precio de {product_name}",
                "html": (
                    f"<h2>Alerta de precio - Kupi</h2>"
                    f"<p>{message}</p>"
                    f"<p><a href='https://main.d2edvoaz20no1j.amplifyapp.com/favoritos'>"
                    f"Ver en Kupi</a></p>"
                ),
            },
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"[alert] email enviado a {email}")
        else:
            print(f"[alert] error enviando email: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[alert] error enviando email: {e}")
