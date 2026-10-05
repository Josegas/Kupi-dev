"""
Endpoints de favoritos: guardar platillos, ver historial de precios.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from kupi.api.auth import get_current_user
from kupi.catalog.supabase_client import get_client

router = APIRouter()


class FavoriteCreate(BaseModel):
    restaurant_name: str
    product_name: str
    rappi_product_id: str | None = None
    ubereats_product_id: str | None = None
    rappi_store_id: str | None = None
    ubereats_store_id: str | None = None
    image_url: str = ""


@router.get("")
def list_favorites(user: dict = Depends(get_current_user)):
    sb = get_client()
    resp = sb.table("user_favorites").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
    return resp.data or []


@router.post("")
def add_favorite(body: FavoriteCreate, user: dict = Depends(get_current_user)):
    sb = get_client()
    row = {
        "user_id": user["id"],
        "restaurant_name": body.restaurant_name,
        "product_name": body.product_name,
        "rappi_product_id": body.rappi_product_id,
        "ubereats_product_id": body.ubereats_product_id,
        "rappi_store_id": body.rappi_store_id,
        "ubereats_store_id": body.ubereats_store_id,
        "image_url": body.image_url,
    }
    try:
        resp = sb.table("user_favorites").insert(row).execute()
        return resp.data[0] if resp.data else row
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Este producto ya está en tus favoritos")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{favorite_id}")
def remove_favorite(favorite_id: int, user: dict = Depends(get_current_user)):
    sb = get_client()
    resp = sb.table("user_favorites").delete().eq("id", favorite_id).eq("user_id", user["id"]).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")
    return {"ok": True}


@router.get("/{favorite_id}/history")
def get_price_history(favorite_id: int, days: int = 30, user: dict = Depends(get_current_user)):
    """
    Historial de precios de un producto favorito (últimos N días).
    Retorna snapshots de ambas plataformas ordenados cronológicamente.
    """
    sb = get_client()

    # Verificar que el favorito pertenece al usuario
    fav_resp = sb.table("user_favorites").select("*").eq("id", favorite_id).eq("user_id", user["id"]).limit(1).execute()
    if not fav_resp.data:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")

    fav = fav_resp.data[0]
    rappi_pid = fav.get("rappi_product_id")
    ue_pid = fav.get("ubereats_product_id")

    if not rappi_pid and not ue_pid:
        return []

    # Buscar snapshots de los últimos N días
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = sb.table("price_snapshots").select("*").gte("sampled_at", since).order("sampled_at", desc=False)

    # Filtrar por product IDs
    if rappi_pid and ue_pid:
        # Buscar snapshots que coincidan con cualquiera de los dos IDs
        snapshots_rappi = (
            sb.table("price_snapshots").select("*")
            .eq("rappi_product_id", rappi_pid)
            .gte("sampled_at", since)
            .order("sampled_at", desc=False)
            .execute()
        )
        snapshots_ue = (
            sb.table("price_snapshots").select("*")
            .eq("ubereats_product_id", ue_pid)
            .gte("sampled_at", since)
            .order("sampled_at", desc=False)
            .execute()
        )
        all_snapshots = (snapshots_rappi.data or []) + (snapshots_ue.data or [])
        all_snapshots.sort(key=lambda s: s.get("sampled_at", ""))
        return all_snapshots
    elif rappi_pid:
        resp = query.eq("rappi_product_id", rappi_pid).execute()
    else:
        resp = query.eq("ubereats_product_id", ue_pid).execute()

    return resp.data or []
