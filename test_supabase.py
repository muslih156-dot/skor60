
import os, requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print(f"Testing REST API - URL: {SUPABASE_URL}")

url = SUPABASE_URL.rstrip("/") + "/rest/v1/matches"
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

data = {
    "match_id": "TEST_GITHUB",
    "home_team": "GitHub",
    "away_team": "Supabase",
    "league": "Test Koneksi REST",
    "minute": 60,
    "score": "0-0",
    "status": "TEST KONEKSI REST - Bisa dihapus | ⚠️ TEST"
}

try:
    r = requests.post(url, headers=headers, json=data, timeout=15)
    print(f"INSERT {r.status_code} {r.text[:500]}")
    if r.status_code in [200,201,204]:
        print("✅ INSERT BERHASIL via REST!")

    verify_url = SUPABASE_URL.rstrip("/") + "/rest/v1/matches?match_id=eq.TEST_GITHUB&select=*"
    r2 = requests.get(verify_url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}, timeout=10)
    print(f"VERIFY {r2.status_code} {r2.text[:1000]}")
    if "TEST_GITHUB" in r2.text:
        print("✅ VERIFY OK - GitHub KONEK 100% via REST!")
    else:
        print("❌ VERIFY GAGAL")
except Exception as e:
    print(f"ERROR {e}")
    import traceback
    traceback.print_exc()
