"""
Caché en memoria para las llamadas a Rappi y Uber Eats.

Cada petición a las plataformas cuesta tiempo y riesgo de bloqueo de la cuenta, así que
todo lo que se repite (menús, cotizaciones, feeds de ofertas) pasa por aquí:
  - TTL: el resultado se reutiliza mientras no expire.
  - Una sola petición en vuelo por clave: si llegan N solicitudes iguales a la vez,
    la primera consulta y las demás esperan su resultado.
  - Throttle: espacio mínimo entre peticiones a una misma plataforma.
"""
import logging
import threading
import time
from typing import Any, Callable, Hashable

from cachetools import TTLCache

logger = logging.getLogger(__name__)


class TTLStore:
    """
    `ttl`: segundos que un valor está fresco. `stale_ttl` (opcional, mayor que ttl): después
    de `ttl` el valor viejo se sigue entregando al instante mientras se actualiza una sola vez
    en segundo plano. Solo para datos de listado (feeds), nunca para cotizaciones.
    """

    def __init__(self, maxsize: int, ttl: float, stale_ttl: float | None = None):
        self._ttl = ttl
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=stale_ttl or ttl)
        self._lock = threading.Lock()
        self._inflight: dict[Hashable, threading.Lock] = {}

    def _store(self, key: Hashable, fetch: Callable[[], Any]) -> Any:
        value = fetch()
        with self._lock:
            self._cache[key] = (value, time.monotonic())
        return value

    def _refresh_in_background(self, key: Hashable, fetch: Callable[[], Any]) -> None:
        with self._lock:
            if key in self._inflight:
                return
            key_lock = self._inflight[key] = threading.Lock()

        def run():
            with key_lock:
                try:
                    self._store(key, fetch)
                except Exception:
                    pass  # se queda el valor viejo; se reintenta en la siguiente consulta
                finally:
                    with self._lock:
                        self._inflight.pop(key, None)
        threading.Thread(target=run, daemon=True).start()

    def get_or_fetch(self, key: Hashable, fetch: Callable[[], Any]) -> Any:
        with self._lock:
            hit = self._cache.get(key)
        if hit is not None:
            value, fetched_at = hit
            if time.monotonic() - fetched_at > self._ttl:
                self._refresh_in_background(key, fetch)
            return value
        with self._lock:
            key_lock = self._inflight.setdefault(key, threading.Lock())
        with key_lock:
            with self._lock:
                hit = self._cache.get(key)
            if hit is not None:
                return hit[0]
            try:
                return self._store(key, fetch)
            finally:
                with self._lock:
                    self._inflight.pop(key, None)


class Throttle:
    """Garantiza al menos `min_interval` segundos entre llamadas a wait()."""

    def __init__(self, min_interval: float):
        self._min_interval = min_interval
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self._min_interval
        if delay > 0:
            time.sleep(delay)


def loc_key(lat: float, lng: float, decimals: int = 3) -> tuple[float, float]:
    """Redondea coordenadas para la clave de caché (3 decimales ≈ 110 m)."""
    return round(lat, decimals), round(lng, decimals)


def zone_center(lat: float, lng: float, cell: float = 0.02) -> tuple[float, float]:
    """
    Centro de la zona (cuadro de `cell` grados, 0.02 ≈ 2 km) que contiene el punto. Los feeds
    de restaurantes y ofertas casi no cambian dentro de esa distancia: se piden una sola vez
    desde el centro y los comparten todos los usuarios de la zona.
    """
    return (round(round(lat / cell) * cell, 4), round(round(lng / cell) * cell, 4))


class PlatformHealth:
    """
    Estado de una plataforma visto desde las respuestas reales (sin peticiones extra):
    con `fail_after` respuestas seguidas de sesión inválida (401) o error de servidor está
    caída (un 502 suelto de un endpoint no tumba toda la app); una respuesta buena la levanta.
    """

    def __init__(self, name: str = "", probe_every: float = 30.0, fail_after: int = 3):
        self._name = name
        self._ok = True
        self._since = time.time()
        self._probe_every = probe_every
        self._last_try = 0.0
        self._fail_after = fail_after
        self._fails = 0

    def allow(self) -> bool:
        """Con la plataforma caída no se le insiste: un solo intento cada `probe_every` segundos."""
        if self._ok:
            return True
        now = time.time()
        if now - self._last_try >= self._probe_every:
            self._last_try = now
            return True
        return False

    def record(self, status_code: int) -> None:
        if status_code != 401 and status_code < 500:
            self._fails = 0
            if not self._ok:
                self._ok, self._since = True, time.time()
                logger.warning("%s volvió a responder", self._name or "Plataforma")
            return
        self._fails += 1
        logger.warning("%s respondió HTTP %s (%s seguidas)", self._name or "Plataforma", status_code, self._fails)
        if self._ok and self._fails >= self._fail_after:
            self._ok, self._since = False, time.time()

    def snapshot(self) -> dict:
        return {"ok": self._ok, "since": int(self._since)}
