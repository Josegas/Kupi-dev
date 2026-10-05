"""
Dependencia de autenticación para endpoints protegidos.
Extrae y verifica el JWT de Supabase del header Authorization.
"""
from fastapi import Depends, HTTPException, Request
from kupi.catalog.supabase_client import get_client


def get_current_user(request: Request) -> dict:
    """
    Dependencia de FastAPI que extrae el usuario del JWT.
    Retorna el dict del usuario de Supabase (id, email, etc.).
    Lanza 401 si no hay token o es inválido.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticación requerido")

    token = auth_header[7:]
    try:
        sb = get_client()
        user_response = sb.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Token inválido")
        return {
            "id": str(user_response.user.id),
            "email": user_response.user.email or "",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Error de autenticación: {e}")


def get_optional_user(request: Request) -> dict | None:
    """
    Igual que get_current_user pero retorna None si no hay token
    (para endpoints que funcionan con o sin auth).
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        return get_current_user(request)
    except HTTPException:
        return None
