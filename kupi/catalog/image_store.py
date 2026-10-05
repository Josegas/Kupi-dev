"""
Almacenamiento de imágenes de restaurantes en Supabase Storage.
Bucket: restaurant-images (público, creado manualmente en el dashboard).
Sube imágenes una sola vez y devuelve la URL pública del CDN de Supabase.
"""
import hashlib
import requests as _requests
from kupi.catalog.supabase_client import get_client

_BUCKET = "restaurant-images"

# Supabase Storage URL pública: {SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}
_SUPABASE_URL = ""


def _get_supabase_url() -> str:
    global _SUPABASE_URL
    if not _SUPABASE_URL:
        import os
        _SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
    return _SUPABASE_URL


def _hash_url(url: str) -> str:
    """Genera un hash corto de la URL para usarlo como nombre de archivo."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _guess_ext(content_type: str) -> str:
    """Determina extensión del archivo por content-type."""
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "svg" in content_type:
        return ".svg"
    return ".jpg"


def upload_image(source_url: str, restaurant_id: str = "") -> str | None:
    """
    Descarga una imagen de su URL original y la sube a Supabase Storage.
    Retorna la URL pública de Supabase o None si falla.
    No re-sube si el archivo ya existe.
    """
    if not source_url or not source_url.startswith("http"):
        return None

    sb_url = _get_supabase_url()
    if not sb_url:
        return None

    file_hash = _hash_url(source_url)
    prefix = restaurant_id[:20] if restaurant_id else "img"
    # Intentar con .jpg por defecto, ajustar después
    file_path = f"{prefix}_{file_hash}"

    sb = get_client()

    # Verificar si ya existe (listar por prefijo)
    try:
        existing = sb.storage.from_(_BUCKET).list(path="", options={"search": file_path, "limit": 1})
        if existing and any(f.get("name", "").startswith(file_path) for f in existing):
            # Ya existe, construir URL pública
            matched = next(f for f in existing if f.get("name", "").startswith(file_path))
            return f"{sb_url}/storage/v1/object/public/{_BUCKET}/{matched['name']}"
    except Exception:
        pass

    # Descargar imagen original
    try:
        referer = "https://www.ubereats.com/" if "uber" in source_url or "cloudfront" in source_url else "https://www.rappi.com.mx/"
        resp = _requests.get(
            source_url,
            headers={
                "Referer": referer,
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
            },
            timeout=8,
        )
        resp.raise_for_status()
    except Exception:
        return None

    content_type = resp.headers.get("content-type", "image/jpeg")
    ext = _guess_ext(content_type)
    full_path = f"{file_path}{ext}"
    img_bytes = resp.content

    # No subir imágenes > 1MB
    if len(img_bytes) > 1_048_576:
        return None

    # Subir a Supabase Storage (con retry)
    import time as _time
    for attempt in range(3):
        try:
            sb.storage.from_(_BUCKET).upload(
                path=full_path,
                file=img_bytes,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            return f"{sb_url}/storage/v1/object/public/{_BUCKET}/{full_path}"
        except Exception as e:
            err_str = str(e).lower()
            if "already" in err_str or "duplicate" in err_str:
                return f"{sb_url}/storage/v1/object/public/{_BUCKET}/{full_path}"
            if attempt < 2:
                _time.sleep(0.5 * (attempt + 1))
                continue
            print(f"[image_store] upload error after 3 attempts: {e}")
            return None


def get_public_url(file_path: str) -> str:
    """Construye la URL pública de un archivo en el bucket."""
    sb_url = _get_supabase_url()
    return f"{sb_url}/storage/v1/object/public/{_BUCKET}/{file_path}"
