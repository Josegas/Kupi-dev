import json
import uuid
from curl_cffi import requests

session = requests.Session()

cookie_string = (
    "uev2.id.session_v2=62ec2a53-3210-434b-9157-621431afd64a; "
    "uev2.ts.session_v2=1790288077869; "
    "uev2.id.xp=c977704c-dff8-41b4-8d3e-c9d8772d9f2d; "
    "dId=f644975e-7144-4d0e-84e5-f029b8c9ce37; "
    "uev2.id.session=c251796d-2506-438f-b4f1-f9105fd7c487; "
    "uev2.ts.session=1790288077871; "
    '_ua={"session_id":"cc0fb10f-753d-487f-a76e-fac7122a4f9d","session_time_ms":1790288077952}; '
    "uev2.diningMode=DELIVERY; "
    "uev2.loc=%7B%22address%22%3A%7B%22address1%22%3A%22Plaza%20Forum%20Culiac%C3%A1n%22%2C%22address2%22%3A%22Jose%20Diego%20Valadez%201676%2C%20ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%2C%2080000%20Culiac%C3%A1n%2C%20SIN%22%2C%22aptOrSuite%22%3A%22%22%2C%22eaterFormattedAddress%22%3A%22Jose%20Diego%20Valadez%201676%2C%20ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%2C%2080000%20Culiac%C3%A1n%2C%20SIN%2C%20MX%22%2C%22subtitle%22%3A%22Jose%20Diego%20Valadez%201676%2C%20ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%2C%2080000%20Culiac%C3%A1n%2C%20SIN%22%2C%22title%22%3A%22Plaza%20Forum%20Culiac%C3%A1n%22%2C%22uuid%22%3A%22%22%7D%2C%22latitude%22%3A24.8143484%2C%22longitude%22%3A-107.4005298%2C%22reference%22%3A%224e0cd9b3-d6c0-db52-95d5-0e721677bdf1%22%2C%22referenceType%22%3A%22uber_places%22%2C%22type%22%3A%22uber_places%22%2C%22addressComponents%22%3A%7B%22city%22%3A%22ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%22%2C%22countryCode%22%3A%22MX%22%2C%22firstLevelSubdivisionCode%22%3A%22SIN%22%2C%22postalCode%22%3A%2280000%22%7D%2C%22categories%22%3A%5B%22DEPARTMENT_STORE%22%2C%22SHOPS_AND_SERVICES%22%2C%22place%22%5D%2C%22originType%22%3A%22user_autocomplete%22%2C%22source%22%3A%22rev_geo_reference%22%2C%22userState%22%3A%22Unknown%22%7D; "
    "marketing_vistor_id=219e6d67-5663-414a-b89e-12dcc3baf4b4; "
    "uev2.gg=true; "
    "u-cookie-prefs=eyJ2ZXJzaW9uIjoxMDAsImRhdGUiOjE3OTAyODgwODEyNDYsImNvb2tpZUNhdGVnb3JpZXMiOlsiZXNzZW50aWFsIl0sImltcGxpY2l0IjpmYWxzZX0%3D; "
    "uev2.gg=false; "
    "_cc=AU5%2Brq%2FHCq7UDJrDcQJ9EnHe; "
    "udi-dd-aia=sw/CSKTFXFdft6LZYgB00zGgNA8sVUzhjh4TUxOnq4ABX++iFPOuDIjLbN+fWuzqbcXsUVNyOJ/eITrHs9Xu4gUFgikaPaYhfJriqWg684/DzCv20+FaudLhItGa3wteXAulBkQVfuvbvAeXX1QU5f9mL/YQTJUtZyEIuVR5PNqvxswL423vK0FkcFEP9Cec5lG+DANPnKY9KFb2DP1Uz5fmTw4j3UeazpCqF+LaseczslRE8RvrD62txfLVuXs46Wms34gTBgma/Km74AOrnDYb8MzqbY7OEnwD2bX72LsgFg2wmJ/7ILb+KWut6J5cOBubm9nifGpf8XGos3BRByUduaTxvH15pM3xsCpf1m0WwHoRfgZ6OBFHmDvm+IkXlHgXNoGVxhYf/SmClQE2+w==pcWBmCiiDG+5+C8We7DZuw==P4WVkiVBk4GIkhTeR0Qz7vGrGWTvk6dCFskz5wN/uKA=; "
    'rateLimiterCookieSession={"rateLimitingID":"a6aaf0ae-ba3b-4a2f-8198-e3ec596d1444"}; '
    "_iidt=qkXcZbsK5DzZqAjd1rj0xmhFRM2ToH4b5+fEEdKZkn1jyg8RKQCHxfDIB0APD1uYKwB3T0xj+cZHuP8QdXEj4/eAQI61vuNFR+KlcWc=; "
    "_vid_t=NJ/UZLYi9+DY7Kvq931Hy5yV8IjZ3sIfhIrtcop7JUGDgRhEPHKzx7YTEKOjbDXFxgcrumd4/y75qK7NyQj89rW3gUS8sv8cAcKcs+U=; "
    "udi-dd-fjs=DpOFUYxOsGgzwcnuoMfcZyL5JOVnoErGeREdEu1nqOL+knInqUiuaPis5+39gcSj7e6rdvuu5TdIxatwgo6CZZ4kdbiDM8fNHoNpLOC7/AGw/ZCP7b/7SuS8vkFOrZuLnz+NOSNj9vZSCN3mlpP6dkWX7oMOsLhQDUE/FT21VUs3iP+YJLX69zShO60OGu15SLWEOEOuV/3m4boMwr6eIyy+Wrbo6VngLEs1cz6/qn3RxqknfBwIhj3P/dv5Hs56wY/WDd+xY7s3WZldQOH6I9P+2HwMleTWLbOhxwuOFOaxQoitie5OdPTklNxZ1yGwBIF4xvZleemGQXyM/v06hyuHdKocug+6KNwFNpbQcTHypSJeNpAJzzMfbiKn09KOHv05k77HucoOATRc3Iw/CA==y/SzoN+RdXhWIjfvs4aT8WHyqrS0pqbXeF8BCUOzSaY=; "
    "uev2.unregisteredUserUuid=1b4975d7-9602-4e93-bf66-0bfb66637d0c; "
    "uev2.unregisteredUserType=DOMAIN_UNCONSTRAINED; "
    "uev2.gosid=GOSID-c025416f-900f-4b00-8a1b-3f55084e88b6; "
    "uev2.do=a1259af6-743a-49c8-addd-0ee428bde1e6; "
    "__cf_bm=0mRjrXCDXBjFCNSyxCLmu2B.BqLdJakMN1u9EHeAzBw-1790289944.9577606-1.0.1.1-3lahKg3eLe2vs8I53Kjdg1XyI2F3vU03IiXd3MzjHNL_PJKmBpBVc44UPNURuRlGKpeYPwPzuBHIDdZyOzj1Y7cxfPXpbiCTouqJWyw8gMizvi0.bcU53xjQSDX1XjPt; "
    "jwt-session=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InNsYXRlLWV4cGlyZXMtYXQiOjE3OTAyOTE3NDU0MjB9LCJpYXQiOjE3OTAyODgwNzksImV4cCI6MTc5MDM3NDQ3OX0.mHDaVH5v8mVtyh7TxYSFRnegF5FOpBKqgZnzNfNStdo; "
    'mp_adec770be288b16d9008c964acfba5c2_mixpanel=%7B%22distinct_id%22%3A%20%22219e6d67-5663-414a-b89e-12dcc3baf4b4%22%2C%22%24device_id%22%3A%20%221a0d57c34801b5-0006f55588212d-14462c68-1aeaa0-1a0d57c348123fb%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.ubereats.com%2Fmx%2Fstore%2Flittle-caesars-humaya%2FeTseruB3RNCHRM8j9U_sUA%3FdiningMode%3DDELIVERY%26surfaceName%3D%22%2C%22%24initial_referring_domain%22%3A%20%22www.ubereats.com%22%2C%22%24user_id%22%3A%20%22219e6d67-5663-414a-b89e-12dcc3baf4b4%22%7D'
)

for cookie in cookie_string.split(";"):
    if "=" in cookie:
        name, value = cookie.strip().split("=", 1)
        session.cookies.set(name, value, domain=".ubereats.com")

headers = {
    "content-type": "application/json; charset=UTF-8",
    "x-csrf-token": "x",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "origin": "https://www.ubereats.com",
    "referer": "https://www.ubereats.com/",
    "x-uber-ciid": str(uuid.uuid4()),
    "x-uber-client-gitref": "011b596870e43572c6a96f425d2d6288f0ab49f4",
    "x-uber-request-id": str(uuid.uuid4()),
    "x-uber-session-id": str(uuid.uuid4()),
    "x-uber-device-location-latitude": "24.8143484",
    "x-uber-device-location-longitude": "-107.4005298",
    "x-uber-target-location-latitude": "24.8143484",
    "x-uber-target-location-longitude": "-107.4005298",
}

# --- SIN warmup, directo al PASO 1 ---
STORE_UUID = "793b1eae-e077-44d0-8744-cf23f54fec50"
SECTION_UUID = "560fca74-ae69-5dc1-8616-c342ec1836d3"
SUBSECTION_UUID = "ca531a8f-9ebd-5971-bbc1-9ff5c47d7736"
ITEM_UUID = "ea8fedb8-b710-40e1-b5b4-b53cd00a8c12"
ITEM_PRICE = 18900
ITEM_TITLE = "Combo Crazy Puffs"

create_body = {
    "isMulticart": True,
    "shoppingCartItems": [{
        "uuid": ITEM_UUID,
        "storeUuid": STORE_UUID,
        "sectionUuid": SECTION_UUID,
        "subsectionUuid": SUBSECTION_UUID,
        "price": ITEM_PRICE,
        "title": ITEM_TITLE,
        "quantity": 1,
        "customizations": {
            "850cd4e9-70e6-4f72-adcd-38fc5b7cf3ad+0": [
                {"uuid": "d0b25f43-19bb-4245-9229-3fc5331508d2", "price": 0, "quantity": 1, "title": "Pizza Pepperoni", "defaultQuantity": 0, "customizationMeta": {"title": "Combo Crazy Puffs", "isPickOne": False}},
                {"uuid": "9e6b951b-7d55-48d7-81bf-509335a7674e", "price": 0, "quantity": 1, "title": "Elige tu Crazy Puff favorito", "defaultQuantity": 0, "customizationMeta": {"title": "Combo Crazy Puffs", "isPickOne": False}}
            ],
            "850cd4e9-70e6-4f72-adcd-38fc5b7cf3ad+0,9e6b951b-7d55-48d7-81bf-509335a7674e,3105b9df-6e9f-439e-96eb-8f4dd73bf024+0": [
                {"uuid": "e0d68b45-3d53-4145-8f22-380af5f831e7", "price": 0, "quantity": 1, "title": "Pepperoni", "defaultQuantity": 0, "customizationMeta": {"title": "Elige tu Crazy Puffs favorito", "isPickOne": False}}
            ]
        },
        "imageURL": "",
        "specialInstructions": "",
        "itemId": None
    }],
    "useCredits": True,
    "extraPaymentProfiles": [],
    "promotionOptions": {"autoApplyPromotionUUIDs": [], "selectedPromotionInstanceUUIDs": [], "skipApplyingPromotion": False},
    "deliveryTime": {"asap": True},
    "deliveryType": "ASAP",
    "currencyCode": "MXN",
    "interactionType": "door_to_door",
    "checkMultipleDraftOrdersCap": True,
    "actionMeta": {"isQuickAdd": False, "numClicks": 1},
    "businessDetails": {}
}

resp1 = session.post(
    "https://www.ubereats.com/_p/api/createDraftOrderV2?localeCode=mx",
    json=create_body, headers=headers, impersonate="chrome120",
)
print("PASO 1 -", resp1.status_code)
print(json.dumps(resp1.json(), indent=2, ensure_ascii=False)[:1000])