import json
import urllib.parse
from curl_cffi import requests

session = requests.Session()

# ⚠️ Cookies frescas integradas
cookie_string = (
    "uev2.id.session_v2=e1f14642-4845-419a-985a-bc3c6124d4c0; "
    "uev2.ts.session_v2=1790290286723; "
    "uev2.id.xp=5a7ea349-4c27-4dfd-ae81-9ce0c2af9c45; "
    "dId=9024e98f-34aa-4482-ba2b-e5ae47754373; "
    "uev2.id.session=cb56f5e2-abf6-4945-8eeb-2d0907ec9cd5; "
    "uev2.ts.session=1790290286725; "
    '_ua={"session_id":"40c666ca-5484-4a63-90d5-47c94b33ba70","session_time_ms":1790290286792}; '
    "uev2.diningMode=DELIVERY; "
    "uev2.loc=%7B%22address%22%3A%7B%22address1%22%3A%22Plaza%20Forum%20Culiac%C3%A1n%22%2C%22address2%22%3A%22Jose%20Diego%20Valadez%201676%2C%20ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%2C%2080000%20Culiac%C3%A1n%2C%20SIN%22%2C%22aptOrSuite%22%3A%22%22%2C%22eaterFormattedAddress%22%3A%22Jose%20Diego%20Valadez%201676%2C%20ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%2C%2080000%20Culiac%C3%A1n%2C%20SIN%2C%20MX%22%2C%22subtitle%22%3A%22Jose%20Diego%20Valadez%201676%2C%20ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%2C%2080000%20Culiac%C3%A1n%2C%20SIN%22%2C%22title%22%3A%22Plaza%20Forum%20Culiac%C3%A1n%22%2C%22uuid%22%3A%22%22%7D%2C%22latitude%22%3A24.8143484%2C%22longitude%22%3A-107.4005298%2C%22reference%22%3A%224e0cd9b3-d6c0-db52-95d5-0e721677bdf1%22%2C%22referenceType%22%3A%22uber_places%22%2C%22type%22%3A%22uber_places%22%2C%22addressComponents%22%3A%7B%22city%22%3A%22ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%22%2C%22countryCode%22%3A%22MX%22%2C%22firstLevelSubdivisionCode%22%3A%22SIN%22%2C%22postalCode%22%3A%2280000%22%7D%2C%22categories%22%3A%5B%22DEPARTMENT_STORE%22%2C%22SHOPS_AND_SERVICES%22%2C%22place%22%5D%2C%22originType%22%3A%22user_autocomplete%22%2C%22source%22%3A%22rev_geo_reference%22%2C%22userState%22%3A%22Unknown%22%7D; "
    "marketing_vistor_id=a9302e03-a13f-4bf1-89fe-d0333af0d60c; "
    "jwt-session=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InNsYXRlLWV4cGlyZXMtYXQiOjE3OTAyOTIwODY4NzJ9LCJpYXQiOjE3OTAyOTAyODcsImV4cCI6MTc5MDM3NjY4N30.lrDiZkxCth_74q01k_x9kQowKVaqUfEWI5RY4qT1HMU; "
    "__cf_bm=wU_npN_iD.I8yFvfP0.UtD_cQJTYFY8pKuzVKvK9l2s-1790290286.6630714-1.0.1.1-qcnazf2_Z7v7rnyLjNOrTq9yFTf7DY47ROqbPwcCctIFcHI7vw5qPyvvESfCEEIHlbea22wMiLHQrRV91fJcnjRZ_n5qjy1FrK9CtllsoQBmZ6k68dPkP9yb5iU46eF3; "
    "uev2.gg=true; "
    "u-cookie-prefs=eyJ2ZXJzaW9uIjoxMDAsImRhdGUiOjE3OTAyOTAyOTAxNzgsImNvb2tpZUNhdGVnb3JpZXMiOlsiZXNzZW50aWFsIl0sImltcGxpY2l0IjpmYWxzZX0%3D; "
    "uev2.gg=false; "
    'mp_adec770be288b16d9008c964acfba5c2_mixpanel=%7B%22distinct_id%22%3A%20%22a9302e03-a13f-4bf1-89fe-d0333af0d60c%22%2C%22%24device_id%22%3A%20%221a0d59de92e9d6-09ebf2b0492e3f8-14462c68-1aeaa0-1a0d59de92f1464%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.ubereats.com%2Fmx%2Fstore%2Flittle-caesars-humaya%2FeTseruB3RNCHRM8j9U_sUA%3FdiningMode%3DDELIVERY%26surfaceName%3D%22%2C%22%24initial_referring_domain%22%3A%20%22www.ubereats.com%22%2C%22%24user_id%22%3A%20%22a9302e03-a13f-4bf1-89fe-d0333af0d60c%22%7D; '
    "_cc=AQGBTSqHprB4XLJf3Brj6UzA; "
    "udi-dd-aia=vQT4cTLiENaHUK+iS8zuRwhdOoV28/TJVXbv/qGRroPxThQDW+uw5XfxXoL9HVzBPO0VSUYOtwvkQ2VIZG3/cF1oDjTPcNlQtL9MJtjvJsPglIHRvNRBFR/insnOp7ekXYxVOpeGbLWPH798mdc1EdKz7o1biYk7Dv5BzaTwDvYcYbXGr6km4blnWTvjtTOa08pqqq/hGC6oRxMBZkGy2mbuTeGX82tVjpBIPLvCL6zm3GIWs0cAZDDNWuU6pWmvpf30cB9q5/GoI1SE17jzNV/ioHZO4LDOiTF59pdrVS4pJrxOinUlvVRDOek8WDEVcIDuwlwTPGMeCYH0PdXEK25nsOUG/OoKyCRrcpBeocboAcKOf8eog77mGuEQ5kuLI3OIlfYZLe0XmNuToj8K/w==vi7GMmaRG1GBN/aLEI2aBw==pFaJCMtc5S+92e/i+IuiP8jYcGtU7ZVm5T7jXuLqFEc=; "
    'rateLimiterCookieSession={"rateLimitingID":"1801e6ef-1e84-43a8-a21d-968ed744206e"}; '
    "_iidt=JOpMoRwpGjkLPstmgOy+C+FAl3xLcFkULbUPNlzgm76GcRZL2HP7GGoergploDAJ/mYenW8qJva5YTApeL5zZ8TpCKiCl6eli2PM9b4=; "
    "_vid_t=9EkCb+YfjWg3++puhmvkrx6oeKjv8Zs1J6heK5PSL35YRwl64J8LwIIAsXh9u+n1x9yZ+IgGgQghwV8Oy8gpbvffmSwMpIvisbTFw/g=; "
    "udi-dd-fjs=gISbgpKFfdC1BL21TC6CxUcjX6lPbdIu7711LofCrDfVJC4b83qo0F71nN+8aZev2YLTKFeBiwkqOuxshZty1sPoUSY22yS8/bafy0sdFhsEPDVBYkNGT1lWxwTNNmpJMvm+Q7dTPx5S/wswJgbaQMplXLn4ee96H+gGZfVHWKhSASykEOUJFwbP1KFX5GGqRSs7J/BzsSKgX8DkMXX8YJIpzGIpIJT02XIyEso+VIeXOgcI5paN22NRUDYbfBXDLDF5PupQ9nTWxHhvYod3cgTb6KlriY9fArRt1goATe0pZZv4tFH0fMjvq85q8kplbxQhr+z3PR3lOK8qaTLQA8itSk3FewyIWsYWiyH92kIn9gUScpRr3OrUXBY5sFwJsxYtmQg4qqaO6vz3FECdqQ==6bDapNtAX30dVQ8xbDjv9ZKZ7GWONmTwWRMd7VIoFMY="
)

for cookie in cookie_string.split(";"):
    if "=" in cookie:
        name, value = cookie.strip().split("=", 1)
        session.cookies.set(name, value, domain=".ubereats.com")

STORE_UUID = "793b1eae-e077-44d0-8744-cf23f54fec50"
SECTION_UUID = "560fca74-ae69-5dc1-8616-c342ec1836d3"
SUBSECTION_UUID = "0379a62a-1156-4ddb-a09a-7e1dc45d5dfb"
ITEM_UUID = "ea8fedb8-b710-40e1-b5b4-b53cd00a8c12"
ITEM_PRICE = 18900
ITEM_TITLE = "Combo Crazy Puffs"

modctx = json.dumps({
    "storeUuid": STORE_UUID,
    "sectionUuid": SECTION_UUID,
    "subsectionUuid": SUBSECTION_UUID,
    "itemUuid": ITEM_UUID,
    "showSeeDetailsCTA": True
})
referer = (
    f"https://www.ubereats.com/mx/store/little-caesars-humaya/eTseruB3RNCHRM8j9U_sUA"
    f"?diningMode=DELIVERY&mod=quickView&modctx={urllib.parse.quote(urllib.parse.quote(modctx))}"
)

headers = {
    "accept": "*/*",
    "accept-language": "es-419,es;q=0.5",
    "content-type": "application/json",
    "origin": "https://www.ubereats.com",
    "priority": "u=1, i",
    "referer": referer,
    "sec-ch-ua": '"Brave";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "sec-gpc": "1",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "x-csrf-token": "x",
    "x-uber-client-gitref": "1732c3b88979083c69bf194084b10b1d475ff81d",
    "x-uber-device-location-latitude": "24.8143484",
    "x-uber-device-location-longitude": "-107.4005298",
    "x-uber-target-location-latitude": "24.8143484",
    "x-uber-target-location-longitude": "-107.4005298",
}

create_body = {
    "isMulticart": True,
    "shoppingCartItems": [{
        "uuid": ITEM_UUID,
        "shoppingCartItemUuid": "46e06e5a-9e46-40d1-87d7-744c4ede954c",
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
        "imageURL": "https://tb-static.uber.com/prod/image-proc/processed_images/6f0e6fea0f34ec180bf1aa86b19c790b/c67fc65e9b4e16a553eb7574fba090f1.jpeg",
        "specialInstructions": "",
        "itemId": None
    }],
    "useCredits": True,
    "extraPaymentProfiles": [],
    "promotionOptions": {
        "autoApplyPromotionUUIDs": [],
        "selectedPromotionInstanceUUIDs": [],
        "skipApplyingPromotion": False
    },
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
data1 = resp1.json()
print(json.dumps(data1, indent=2, ensure_ascii=False)[:1500])

if data1.get("status") == "success":
    draft_order_uuid = data1["data"]["draftOrder"]["uuid"]
    print(f"\ndraftOrderUUID obtenido: {draft_order_uuid}")

    checkout_body = {
        "draftOrderUUID": draft_order_uuid,
        "isGroupOrder": False,
        "webGiftingPersonalizationEnabled": True,
        "clientFeaturesData": {
            "paymentSelectionContext": {"value": '{"deviceContext":{"thirdPartyApplications":[]}}'}
        },
        "payloadTypes": [
            "canonicalProductStorePickerPayload", "total", "subtotal", "fareBreakdown",
            "paymentProfilesEligibility", "requestUtensilPayload", "versionMetadata"
        ]
    }

    resp2 = session.post(
        "https://www.ubereats.com/_p/api/getCheckoutPresentationV1?localeCode=mx",
        json=checkout_body, headers=headers, impersonate="chrome120",
    )
    print("\nPASO 2 -", resp2.status_code)
    data2 = resp2.json()

    if data2.get("status") == "success":
        charges = data2["data"]["checkoutPayloads"]["fareBreakdown"]["charges"]
        for charge in charges:
            print(f"{charge['title']['text']}: {charge['value']['text']}")
    else:
        print(json.dumps(data2, indent=2, ensure_ascii=False)[:1500])