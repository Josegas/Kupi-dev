import json

# Cargamos el archivo JSON que acabamos de descargar
with open("uber_menu.json", "r", encoding="utf-8") as f:
  raw_data = json.load(f)

# El menú detallado viene dentro de una cadena de texto en 'metaJson'
meta_json_str = raw_data.get("data", {}).get("metaJson", "{}")
menu_data = json.loads(meta_json_str)

# Extraemos las secciones del menú
menu_sections = (
    menu_data.get("hasMenu", {}).get("hasMenuSection", [])
)

print(
    f"Restaurante: {menu_data.get('name', 'Desconocido')} (Culiacán, Sin.)\n"
)
print("=" * 60)

# Recorremos cada categoría/sección
for section in menu_sections:
  section_name = section.get("name")
  items = section.get("hasMenuItem", [])

  print(f"\n📂 CATEGORÍA: {section_name} ({len(items)} productos)")
  print("-" * 60)

  # Recorremos los platillos de cada sección
  for item in items:
    name = item.get("name")
    description = item.get("description", "Sin descripción")

    # Extraemos el precio del objeto 'offers'
    offer = item.get("offers", {})
    price = offer.get("price", "0.00")
    currency = offer.get("priceCurrency", "MXN")

    print(f"  • {name} - ${price} {currency}")
    print(f"    Desc: {description}")