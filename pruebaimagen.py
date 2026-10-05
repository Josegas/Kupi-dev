import json
from kupi.connectors.ubereats.connector import _build_session, _BASE_URL
from kupi.core.config import DEFAULT_LAT, DEFAULT_LNG

# McDonald's Culiacán
STORE_ID = "dd6ea249-d885-464f-a73d-8e67e62068c7"

session = _build_session(DEFAULT_LAT, DEFAULT_LNG)
body = {"storeUuid": STORE_ID, "diningMode": "DELIVERY", "time": {"asap": True}, "cbType": "EATER_ENDORSED"}
resp = session.post(f"{_BASE_URL}/getStoreV1?localeCode=mx", json=body, impersonate="chrome120")
data = resp.json()

catalog_map = data["data"]["catalogSectionsMap"]

for section_uuid, subsections in catalog_map.items():
    for subsection in subsections:
        items = (
            subsection.get("payload", {})
            .get("standardItemsPayload", {})
            .get("catalogItems", [])
        )
        for item in items:
            promo = item.get("promoInfo")
            purchase = item.get("purchaseInfo")
            if promo or (purchase and purchase != {}):
                print(f"\n--- {item['title']} ---")
                print(f"  price: ${item.get('price', 0) / 100:.2f}")
                print(f"  priceTagline: {item.get('priceTagline', {}).get('text')}")
                print(f"  promoInfo: {json.dumps(promo, ensure_ascii=False)}")
                print(f"  purchaseInfo: {json.dumps(purchase, ensure_ascii=False)[:300]}")
