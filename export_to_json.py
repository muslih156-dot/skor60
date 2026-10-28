
import os, json
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    res = supabase.table("matches").select("*").order("created_at", desc=True).limit(200).execute()
    data = res.data
    # Tulis ke file JSON
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Exported {len(data)} matches to data/matches.json")
except Exception as e:
    print(f"Export error: {e}")
    # Buat file kosong biar gak error
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w") as f:
        json.dump([], f)
