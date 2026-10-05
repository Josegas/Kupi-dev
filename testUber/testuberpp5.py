import json, re

with open("uber_feed.json", "r", encoding="utf-8") as f:  # si la guardaste
    data = json.load(f)

text = json.dumps(data, ensure_ascii=False)
for match in re.finditer(r'.{40}(fee|Fee|delivery.{0,15}price|shipping).{60}', text):
    print(match.group())
    print("---")