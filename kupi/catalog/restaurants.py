"""
Catálogo de restaurantes en Supabase.
Tabla: restaurants(id, name, rappi_store_id, ubereats_store_id, cuisine, image_url, city, match_confidence, created_at, updated_at)
"""
from kupi.catalog.supabase_client import get_client


def lookup_by_ue_ids(ue_store_ids: list[str]) -> dict[str, dict]:
    """Busca restaurantes por sus UberEats store IDs. Retorna {ue_id: row}."""
    if not ue_store_ids:
        return {}
    sb = get_client()
    resp = sb.table("restaurants").select("*").in_("ubereats_store_id", ue_store_ids).execute()
    return {r["ubereats_store_id"]: r for r in (resp.data or [])}


def lookup_by_rappi_ids(rappi_store_ids: list[str]) -> dict[str, dict]:
    """Busca restaurantes por sus Rappi store IDs. Retorna {rappi_id: row}."""
    if not rappi_store_ids:
        return {}
    sb = get_client()
    resp = sb.table("restaurants").select("*").in_("rappi_store_id", rappi_store_ids).execute()
    return {r["rappi_store_id"]: r for r in (resp.data or [])}


def upsert_restaurant(
    name: str,
    rappi_store_id: str | None = None,
    ubereats_store_id: str | None = None,
    cuisine: str = "",
    image_url: str = "",
    city: str = "",
    match_confidence: str = "auto",
) -> None:
    """Inserta o actualiza un restaurante en la BD."""
    sb = get_client()

    # Buscar si ya existe por rappi o ue ID
    existing = None
    if rappi_store_id:
        resp = sb.table("restaurants").select("*").eq("rappi_store_id", rappi_store_id).limit(1).execute()
        if resp.data:
            existing = resp.data[0]
    if not existing and ubereats_store_id:
        resp = sb.table("restaurants").select("*").eq("ubereats_store_id", ubereats_store_id).limit(1).execute()
        if resp.data:
            existing = resp.data[0]

    row = {
        "name": name,
        "cuisine": cuisine,
        "image_url": image_url,
        "city": city,
        "match_confidence": match_confidence,
    }
    if rappi_store_id:
        row["rappi_store_id"] = rappi_store_id
    if ubereats_store_id:
        row["ubereats_store_id"] = ubereats_store_id

    if existing:
        # Actualizar: merge IDs que no teníamos
        update = {k: v for k, v in row.items() if v}
        if rappi_store_id and not existing.get("rappi_store_id"):
            update["rappi_store_id"] = rappi_store_id
        if ubereats_store_id and not existing.get("ubereats_store_id"):
            update["ubereats_store_id"] = ubereats_store_id
        sb.table("restaurants").update(update).eq("id", existing["id"]).execute()
    else:
        sb.table("restaurants").insert(row).execute()


def get_all(city: str | None = None) -> list[dict]:
    """Retorna todos los restaurantes, opcionalmente filtrados por ciudad."""
    sb = get_client()
    query = sb.table("restaurants").select("*")
    if city:
        query = query.eq("city", city)
    resp = query.execute()
    return resp.data or []


def seed_featured(featured_list: list[dict]) -> None:
    """Siembra los restaurantes hardcodeados en la BD si no existen."""
    for r in featured_list:
        upsert_restaurant(
            name=r.get("restaurant_name", r.get("name", "")),
            rappi_store_id=r.get("rappi_store_id"),
            ubereats_store_id=r.get("ubereats_store_id"),
            cuisine=r.get("cuisine", ""),
            image_url=r.get("imageUrl", r.get("image_url", "")),
            match_confidence="hardcoded",
        )
