import os
from supabase import create_client, Client

_client: Client | None = None

# Proyecto de Supabase del Kupi entregado en el hackathon (congelado, en revisión).
# Kupi-dev puede leerlo, pero nunca escribir en él: cambiaría lo que ven los jueces.
_HACKATHON_PROJECT = "zoncxujbbropduccfumy"
_WRITE_METHODS = {"insert", "update", "upsert", "delete"}


class _ReadOnlyTable:
    def __init__(self, builder, name: str):
        self._builder = builder
        self._name = name

    def __getattr__(self, attr: str):
        if attr in _WRITE_METHODS:
            raise RuntimeError(
                f"Kupi-dev no escribe en la BD del hackathon ({attr} en '{self._name}'). "
                "Configura SUPABASE_URL con el proyecto de Kupi-dev."
            )
        return getattr(self._builder, attr)


class _ReadOnlyClient:
    def __init__(self, client: Client):
        self._client = client

    def table(self, name: str):
        return _ReadOnlyTable(self._client.table(name), name)

    @property
    def storage(self):
        raise RuntimeError("Kupi-dev no sube archivos al storage de la BD del hackathon.")

    def __getattr__(self, attr: str):
        return getattr(self._client, attr)


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SECRET_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL y SUPABASE_SECRET_KEY deben estar definidos en el entorno")
        client = create_client(url, key)
        _client = _ReadOnlyClient(client) if _HACKATHON_PROJECT in url else client
    return _client
