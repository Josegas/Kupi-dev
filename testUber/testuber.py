from curl_cffi import requests

cookie_string = (
    "dId=d91c5fcc-2b14-4f15-916f-6b5be6a0c585; "
    "marketing_vistor_id=36c631fa-7341-4266-980b-8617b565add1; "
    "u-cookie-prefs=eyJ2ZXJzaW9uIjoxMDAsImRhdGUiOjE3Nzk3NjAxNzYzMjgsImNvb2tpZUNhdGVnb3JpZXMiOlsiZXNzZW50aWFsIl0sImltcGxpY2l0IjpmYWxzZX0%3D; "
    "uev2.gg=false; _cc=AZXQSukz%2FgiJtbGKjr4Bd%2Bj0; "
    "cf_clearance=YKnszH2eM2A9FX5fzyUUWdgjT.jvFV_42oQS4wm4vMc-1790051451-1.2.1.1-Ik0SP6T83GaosaZZJb_qTo7S6kzXM0aewDy7vwtjk0CxQ22NcIwnBzMWXpvIewlYCtVPaWeoeVZO_ojmG_LDfI5_6VurZfCccismbnl1QvyZ.duljilULVyuRnE.BJH2PpGVA3dQsHznwON3i0lICrdFNOvE33QufTtyYayyYqHXEY2aH0hLh5My0cEK8Sn_E7IlVd53ZiT0YG83alZ9CH0N0k.GCV.ojhqlSr59jOFqC8P98n8KMNiVPup1m1AjSErpLkfvl_.DXDoUyEHqQH_LdG_V4B.VYgQzkf_8GkYCmm_6bQ98UdnOLrosI0vVDHeODIierP_rzZOCKbrPhObBKk9GSmXlZYc4d6MiGsY; "
    "uev2.loc=%7B%22address%22%3A%7B%22address1%22%3A%22Plaza%20Forum%20Culiac%C3%A1n%22%2C%22address2%22%3A%22Jose%20Diego%20Valadez%201676%2C%20ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%2C%2080000%20Culiac%C3%A1n%2C%20SIN%22%2C%22aptOrSuite%22%3A%22%22%2C%22eaterFormattedAddress%22%3A%22Jose%20Diego%20Valadez%201676%2C%20ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%2C%2080000%20Culiac%C3%A1n%2C%20SIN%2C%20MX%22%2C%22subtitle%22%3A%22Jose%20Diego%20Valadez%201676%2C%20ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%2C%2080000%20Culiac%C3%A1n%2C%20SIN%22%2C%22title%22%3A%22Plaza%20Forum%20Culiac%C3%A1n%22%2C%22uuid%22%3A%22%22%7D%2C%22latitude%22%3A24.8143484%2C%22longitude%22%3A-107.4005298%2C%22reference%22%3A%224e0cd9b3-d6c0-db52-95d5-0e721677bdf1%22%2C%22referenceType%22%3A%22uber_places%22%2C%22type%22%3A%22uber_places%22%2C%22addressComponents%22%3A%7B%22city%22%3A%22ZC%20Desarrollo%20Urbano%20Tres%20R%C3%ADos%22%2C%22countryCode%22%3A%22MX%22%2C%22firstLevelSubdivisionCode%22%3A%22SIN%22%2C%22postalCode%22%3A%2280000%22%7D%2C%22categories%22%3A%5B%22DEPARTMENT_STORE%22%2C%22SHOPS_AND_SERVICES%22%2C%22place%22%5D%2C%22originType%22%3A%22user_autocomplete%22%2C%22source%22%3A%22manual_auto_complete%22%2C%22userState%22%3A%22Unknown%22%2C%22residenceType%22%3A%22%22%7D; "
    "uev2.diningMode=DELIVERY; "
    "g_state={\"i_l\":0,\"i_ll\":1790191493098,\"i_b\":\"J6/ItvjWqboOseZ3BoOG8AtHKlaVNxPh8oPlcpwsu8U\",\"i_e\":{\"enable_itp_optimization\":24},\"i_et\":1790191493098}; "
    "uev2.id.xp=d24d3f1b-5a44-4090-a17e-06397a8e3e83; "
    "_ua={\"session_id\":\"c89bd9ab-0543-4cb0-96b5-f242b3b1d65a\",\"session_time_ms\":1790212092123}; "
    "uev2.gg=true; "
    "mp_adec770be288b16d9008c964acfba5c2_mixpanel=%7B%22distinct_id%22%3A%20%2236c631fa-7341-4266-980b-8617b565add1%22%2C%22%24device_id%22%3A%20%2219e61f91e061574-08eeb676b927cf8-1f462c69-384000-19e61f91e071cb9%22%2C%22%24search_engine%22%3A%20%22google%22%2C%22%24initial_referrer%22%3A%22https%3A%2F%2Fwww.google.com%2F%22%2C%22%24initial_referring_domain%22%3A%22www.google.com%22%2C%22%24user_id%22%3A%2236c631fa-7341-4266-980b-8617b565add1%22%7D; "
    "udi-dd-aia=pQReZERA6iUCejwg/a0Q/V6NMt5dTZkmDsVgRGej+8/Cs90JYaLuiugbhN8JuXEWbLhPs34zJ3droP0fFA9ST53QQj2+V6tmyOpN2AivRx7kohNVzmpolsA3kY87o6enZESEKx0fP0RKVYQYP/OJ03KEXrH5Ix6m42/+A/lkKYC3JMVSg19S//iD6nMZQNjnDZ60UGsLVS8rsVO6dk6eGr1J1QsCRyZpCNrbh2AvKnbn6CTICZ7dvPK/QecZNs+IeEUoShqFPXsfI7gnjkwdVSoMVc8sHgpAVrXMhaJZFUKB1rzdZyP2isHlbzq963FWT/7U7eOaTk3USqvTf8n8CZONQFt1bSN+6cqkFIVJN1WFYBAsANzSlvdaelesrevv+hUGuzGj/LpHQFT+5PjYyw==LozYN9goVP7ZF0RgiZsHsw==Zt9D/0yaJgVwv19wBhfCo3tUHa0dcE4frTPDRcU7Sy8=; "
    "rateLimiterCookieSession={\"rateLimitingID\":\"3adb5c36-8360-4202-b6d3-89d70903ce16\"}; "
    "_iidt=lJnoQCHY5/baa4feestXM79P3yHcmU4cICWsLzL5W2g/e6gwutJmxzlpkSyudsZ8yFrQ1duyzfZUwRhrD3tu4MaT2Pdd8hI1Utuh4gs=; "
    "_vid_t=udQvuKOJgddOIUgszzbqSKeb2HVI6P76Qj4L5NqJfEeSRqBA4hcYs7OXDR1/E5LIThCvo/2ttF33KcDyj5wIOfavqofumH2gym7TijU=; "
    "uev2.id.session_v2=5ba02731-5c5b-4979-aab0-f6e72b0cbc4d; "
    "uev2.ts.session_v2=1790217907598; "
    "uev2.id.session=dca279df-821d-4105-abd3-3bf2e0780cf0; "
    "uev2.ts.session=1790217907600; "
    "udi-dd-fjs=rXp3kyHBgdskoKNTV9NhZpYULBXmmNVfxL5hu9cH7mgrMCdvrOXBliaAKa2+uEXwmF2xNNpqpHNp6FZS+9ZL0qLD0m5/NIeyeM+MIfjEHz8PQ2RvyzgsVlOmr+AQq33UhjT8nJPT+a1LhuPF2vOReSr/qD4M0twm3IH0B8UvU2Youa4vTUdg31SXZko2+UeneY480VCxUhbjHXDB+WDFqFyLszrvFjRiRx0vNRMKPZkKMcQNnXb8lFC7qjPrO2htbnivXGn/6vYW2hZS9HD/uuLJe4hYjJWunuxJfAG3P76yETQ7MVEeeIW7cEkw/Gel0CM9j4pF3jYBz1Gr9x7fO3hrZHHg9OpDong0K9qNgfMkF+t9181z6ajvphRH4E/OcLUhPcAKwl/c/8WWnfeCpw==2n+nVKdJBr7hWH5DH+V9BnG35CxC7v17g3HrarT5T0I=; "
    "jwt-session=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InNsYXRlLWV4cGlyZXMtYXQiOjE3OTAyMTk3MDc4NjF9LCJpYXQiOjE3OTAxODk4ODYsImV4cCI6MTc5MDI3NjI4Nn0.WjT_28WkYjU4tqJBt8ecnzBNmamZ6ZzEO3hQZvt1Qh8; "
    "__cf_bm=AONfArVbJci.qwCZfzOe_BtWMK9apt3A_PmieThLdyE-1790217907.557346-1.0.1.1-s6Fpo_ZIvHkezdF2jKhvdnQNAS9OjdGsYJU2rPNsVr5RGyawWfd0R2uHMTkE5AC04Ilce3Uj23GNS7CHiXcpiofFv8nHd0CNykHpX8izFBr9fC1ryG.PxDJ2sEf4Fv3."
)

cookies_dict = {}
for cookie in cookie_string.split(";"):
  if "=" in cookie:
    name, value = cookie.strip().split("=", 1)
    cookies_dict[name] = value

headers = {
    "content-type": "application/json; charset=UTF-8",
    "x-csrf-token": "x",
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like"
        " Gecko) Chrome/153.0.0.0 Safari/537.36"
    ),
    "origin": "https://www.ubereats.com",
    "referer": "https://www.ubereats.com/",
}

body = {
    "storeUuid": "793b1eae-e077-44d0-8744-cf23f54fec50",
    "diningMode": "DELIVERY",
    "time": {"asap": True},
    "cbType": "EATER_ENDORSED",
}

print("Enviando petición a Uber Eats con impersonación de navegador...")

# Usamos impersonate="chrome120" para burlar la seguridad de Cloudflare
resp = requests.post(
    "https://www.ubereats.com/_p/api/getStoreV1?localeCode=mx",
    json=body,
    headers=headers,
    cookies=cookies_dict,
    impersonate="chrome120",
)

print(f"Status Code: {resp.status_code}")

try:
  data = resp.json()
  print("¡Éxito rotundo! Menú obtenido:")
  print(list(data.keys()) if isinstance(data, dict) else data)
except Exception:
  print("Respuesta recibida:")
  print(resp.text[:400])

  # Muestra las categorías o secciones del menú
store_data = data.get("data", {})
# Dependiendo de la estructura exacta de Uber, exploramos los catálogos:
print("Estructura interna lista para parsear.")

import json

# ... (todo tu código anterior hasta recibir resp y data) ...

data = resp.json()

# Vamos a guardar el JSON completo en un archivo de texto para explorarlo con calma en VS Code
with open("uber_menu.json", "w", encoding="utf-8") as f:
  json.dump(data, f, ensure_ascii=False, indent=4)

print("¡Menú guardado en 'uber_menu.json'! Puedes abrirlo en VS Code.")

# Intentemos explorar un poco la estructura de 'data'
inner_data = data.get("data", {})
print("Llaves dentro de 'data':", list(inner_data.keys()))