import json

with open("uber_menu.json", "r", encoding="utf-8") as f:
    data = json.load(f)

store = data["data"]

def peek(key, max_chars=1500):
    val = store.get(key)
    text = json.dumps(val, indent=2, ensure_ascii=False)
    print(f"\n===== {key} =====")
    print(text[:max_chars])
    if len(text) > max_chars:
        print(f"... [truncado, total {len(text)} caracteres]")

# Candidatos para encontrar productos
peek("catalogSectionsMap")
peek("sections")
peek("subsectionsMap")

# Candidatos para encontrar delivery fee
peek("fareBadge")
peek("storeInfoMetadata")
peek("etaRange")

