from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Product:
    product_id: str
    name: str
    price: float          # precio con descuento activo
    real_price: float     # precio sin descuento
    description: str = ""
    image_url: str = ""
    # Campos extra que Uber Eats necesita para cotizar (no aplican en Rappi/DiDi)
    section_uuid: str = ""
    subsection_uuid: str = ""
    customizations: dict = field(default_factory=dict)
    has_variants: bool = False   # True si el producto tiene opciones obligatorias (tamaño, cantidad)


@dataclass
class CartItemDetail:
    product_id: str
    name: str
    price: float


@dataclass
class PriceQuote:
    platform: str         # "rappi" | "ubereats" | "didi"
    product_price: float
    delivery_fee: Optional[float]   # None = dato no disponible (DiDi fuera de la app)
    service_fee: Optional[float]    # None = dato no disponible (DiDi fuera de la app)
    total: float                    # en DiDi es solo el precio del producto (parcial)
    currency: str = "MXN"
    eta_minutes: Optional[int] = None
    deep_link: str = ""   # URL para abrir la tienda en la app/web de la plataforma
    store_name: str = ""  # nombre de la sucursal en esa plataforma
    store_address: str = ""  # dirección de la sucursal
    variant_label: str = ""  # etiqueta de la variante cotizada, ej. "6 Piezas" o "Precio base"
    is_open: bool = True  # False si el restaurante está cerrado ahora (fuera de horario)
    opens_at: str = ""    # mensaje de apertura si está cerrado, ej. "Abre: 10:00 a.m."
    is_estimate: bool = False  # True si el checkout falló y el total es estimado (sin service fee real)
