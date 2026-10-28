
import os, json, requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def load_local():
    for p in ["data/matches.json", "matches.json"]:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
    return []

try:
    print("Trying Supabase REST...")
    url = SUPABASE_URL.rstrip("/") + "/rest/v1/matches?select=*&order=created_at.desc&limit=200"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    r = requests.get(url, headers=headers, timeout=10)
    print(f"Supabase REST {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        os.makedirs("data", exist_ok=True)
        with open("data/matches.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"✅ Exported {len(data)} from Supabase")
    else:
        raise Exception(f"Supabase returned {r.status_code}")
except Exception as e:
    print(f"Supabase export failed {e} - using local JSON fallback (from check_once.py)")
    local_data = load_local()
    os.makedirs("data", exist_ok=True)
    # Kalau local kosong, bikin []
    if not local_data:
        print("Local JSON also empty - creating []")
        with open("data/matches.json", "w") as f:
            json.dump([], f)
    else:
        print(f"✅ Using local JSON fallback {len(local_data)} matches - already saved by check_once.py")
        # Already saved, keep it
