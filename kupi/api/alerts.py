"""
Endpoints de alertas de precio: crear, modificar, listar y eliminar.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from kupi.api.auth import get_current_user
from kupi.catalog.supabase_client import get_client

router = APIRouter()


class AlertCreate(BaseModel):
    favorite_id: int
    alert_type: str = "price_drop"  # 'price_drop' | 'coupon'
    threshold_pct: float = 5.0


class AlertUpdate(BaseModel):
    threshold_pct: float | None = None
    is_active: bool | None = None


@router.get("")
def list_alerts(user: dict = Depends(get_current_user)):
    sb = get_client()
    resp = (
        sb.table("price_alerts")
        .select("*, user_favorites(product_name, restaurant_name, image_url)")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


@router.post("")
def create_alert(body: AlertCreate, user: dict = Depends(get_current_user)):
    sb = get_client()

    # Verificar que el favorito existe y pertenece al usuario
    fav = sb.table("user_favorites").select("id").eq("id", body.favorite_id).eq("user_id", user["id"]).limit(1).execute()
    if not fav.data:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")

    row = {
        "user_id": user["id"],
        "favorite_id": body.favorite_id,
        "alert_type": body.alert_type,
        "threshold_pct": body.threshold_pct,
        "is_active": True,
    }
    resp = sb.table("price_alerts").insert(row).execute()
    return resp.data[0] if resp.data else row


@router.patch("/{alert_id}")
def update_alert(alert_id: int, body: AlertUpdate, user: dict = Depends(get_current_user)):
    sb = get_client()
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    resp = sb.table("price_alerts").update(update).eq("id", alert_id).eq("user_id", user["id"]).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return resp.data[0]


@router.delete("/{alert_id}")
def delete_alert(alert_id: int, user: dict = Depends(get_current_user)):
    sb = get_client()
    resp = sb.table("price_alerts").delete().eq("id", alert_id).eq("user_id", user["id"]).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return {"ok": True}
