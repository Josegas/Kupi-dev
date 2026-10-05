import json

with open("uber_menu.json", "r", encoding="utf-8") as f:
    data = json.load(f)

text = json.dumps(data, ensure_ascii=False)

# Buscamos cualquier mención de "fee" o "delivery" con contexto
import re
for match in re.finditer(r'.{40}(fee|Fee|delivery.{0,10}[Cc]ost|envio|envío).{40}', text):
    print(match.group())
    print("---")