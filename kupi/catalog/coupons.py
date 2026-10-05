"""
Extrae cupones/promociones de Rappi y UberEats y los guarda en Supabase.

Columnas de la tabla `coupons`:
  id              int8 (identity, no enviar)
  created_at      timestamptz
  restaurant_id   text[]   ← array con el ID interno del restaurante
  restaurant_name text
  platform        text     ("rappi" | "ubereats")
  description     text     (texto visible del cupón)
  is_active       bool
  last_seen_at    timestamptz
  deep_link       text | null

Fuentes de datos:
  Rappi    → data["discount_tags"]     en _fetch_store
  UberEats → data["promotionInfo"]     en getStoreV1
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from kupi.catalog.supabase_client import get_client
from kupi.connectors.rappi.connector import RappiConnector
from kupi.connectors.ubereats.connector import _call_ubereats, _build_headers, _BASE_URL
from kupi.core.config import DEFAULT_LAT, DEFAULT_LNG

logger = logging.getLogger(__name__)

def _get_restaurants() -> list[dict]:
    """Carga restaurantes desde Supabase para escanear cupones."""
    try:
        from kupi.catalog.restaurants import get_all
        all_r = get_all()
        return [
            {
                "restaurant_id": f"{r.get('rappi_store_id', '')}-{r.get('ubereats_store_id', '')}",
                "rappi_store_id": r.get("rappi_store_id", ""),
                "ubereats_store_id": r.get("ubereats_store_id", ""),
                "restaurant_name": r.get("name", ""),
            }
            for r in all_r
            if r.get("rappi_store_id") or r.get("ubereats_store_id")
        ]
    except Exception as e:
        logger.error("Error cargando restaurantes para cupones: %s", e)
        return []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_rappi_coupons(r: dict, lat: float, lng: float) -> list[dict]:
    connector = RappiConnector()
    try:
        data = connector._fetch_store(r["rappi_store_id"], lat, lng)
    except Exception as e:
        logger.warning("Rappi %s: %s", r["restaurant_id"], e)
        return []

    tags = data.get("discount_tags", []) or []
    now = _now_iso()
    coupons = []
    for tag in tags:
        # discount_tags puede ser una lista de strings o de dicts según la versión de la API
        if isinstance(tag, str):
            description = tag
        else:
            title = tag.get("title") or tag.get("name") or ""
            subtitle = tag.get("subtitle") or tag.get("description") or ""
            description = f"{title} {subtitle}".strip() if subtitle else title
        if not description:
            continue
        coupons.append({
            "restaurant_id": [r["restaurant_id"]],   # text[]
            "restaurant_name": r["restaurant_name"],
            "platform": "rappi",
            "description": description,
            "is_active": True,
            "last_seen_at": now,
            "deep_link": None,
        })
    return coupons


def _extract_ubereats_coupons(r: dict, lat: float, lng: float) -> list[dict]:
    try:
        headers = _build_headers(lat, lng)
        body = {
            "storeUuid": r["ubereats_store_id"],
            "diningMode": "DELIVERY",
            "time": {"asap": True},
            "cbType": "EATER_ENDORSED",
        }
        data = _call_ubereats(f"{_BASE_URL}/getStoreV1?localeCode=mx", headers, body).get("data", {})
    except Exception as e:
        logger.warning("UberEats %s: %s", r["restaurant_id"], e)
        return []

    promotion_info = data.get("promotionInfo") or {}
    promos = promotion_info.get("promotions") or []
    now = _now_iso()
    coupons = []
    for promo in promos:
        title = promo.get("title") or promo.get("header") or ""
        subtitle = promo.get("subtitle") or promo.get("description") or ""
        description = f"{title} {subtitle}".strip() if subtitle else title
        if not description:
            continue
        coupons.append({
            "restaurant_id": [r["restaurant_id"]],   # text[]
            "restaurant_name": r["restaurant_name"],
            "platform": "ubereats",
            "description": description,
            "is_active": True,
            "last_seen_at": now,
            "deep_link": promo.get("deepLink") or None,
        })
    return coupons


def refresh_coupons(lat: float = DEFAULT_LAT, lng: float = DEFAULT_LNG) -> int:
    """
    Escanea todos los restaurantes en paralelo, extrae cupones activos de
    Rappi y UberEats, y reemplaza la tabla `coupons` en Supabase.
    Devuelve el número de cupones guardados.
    """
    all_coupons: list[dict] = []

    def scan_one(r: dict) -> list[dict]:
        return _extract_rappi_coupons(r, lat, lng) + _extract_ubereats_coupons(r, lat, lng)

    with ThreadPoolExecutor(max_workers=8) as ex:
        for result in as_completed([ex.submit(scan_one, r) for r in _get_restaurants()]):
            all_coupons.extend(result.result())

    db = get_client()
    # Marcar todos como inactivos primero
    db.table("coupons").update({"is_active": False}).eq("is_active", True).execute()

    if all_coupons:
        db.table("coupons").insert(all_coupons).execute()

    logger.info("refresh_coupons: %d cupones guardados", len(all_coupons))
    return len(all_coupons)


def get_coupons(restaurant_id: str | None = None) -> list[dict]:
    """Devuelve solo cupones activos desde Supabase."""
    db = get_client()
    query = (
        db.table("coupons")
        .select("*")
        .eq("is_active", True)
        .order("last_seen_at", desc=True)
    )
    if restaurant_id:
        # Buscar en el array text[]
        query = query.contains("restaurant_id", [restaurant_id])
    return query.execute().data
