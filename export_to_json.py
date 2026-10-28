
import os, json, requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    url = SUPABASE_URL.rstrip("/") + "/rest/v1/matches?select=*&order=created_at.desc&limit=200"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    r = requests.get(url, headers=headers, timeout=15)
    print(f"Export REST {r.status_code} len {len(r.text)}")
    data = r.json() if r.status_code == 200 else []
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Exported {len(data)} matches")
except Exception as e:
    print(f"Export error {e}")
    import traceback
    traceback.print_exc()
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w") as f:
        json.dump([], f)
