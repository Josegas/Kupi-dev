from abc import ABC, abstractmethod
from kupi.core.models import Product, PriceQuote


class BaseConnector(ABC):
    """
    Interfaz común para todos los conectores de plataforma.
    Cada conector (Rappi, Uber Eats, DiDi) implementa estos dos métodos.
    La capa de pricing/ solo usa esta interfaz - no importa nada específico de plataforma.
    """

    @abstractmethod
    def fetch_menu(self, store_id: str, lat: float, lng: float) -> list[Product]:
        """
        Devuelve el catálogo completo de productos de una tienda.
        Usado para indexado periódico (cada 12-24h).
        """
        ...

    @abstractmethod
    def fetch_price(self, store_id: str, product: Product, lat: float, lng: float) -> PriceQuote:
        """
        Cotiza el precio final real de un producto: precio + envío + cuotas.
        Llamado en tiempo real cuando el usuario hace una búsqueda.
        """
        ...
