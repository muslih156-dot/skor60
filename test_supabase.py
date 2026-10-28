
import os, requests, sys

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print(f"URL: {SUPABASE_URL}")
print(f"KEY prefix: {SUPABASE_KEY[:20]}... len {len(SUPABASE_KEY) if SUPABASE_KEY else 0}")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ SUPABASE_URL atau KEY kosong di GitHub Secrets!")
    sys.exit(1)

url = SUPABASE_URL.rstrip("/") + "/rest/v1/matches"
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

data = {
    "match_id": "TEST_GITHUB_DEBUG",
    "home_team": "GitHub",
    "away_team": "Supabase",
    "league": "Test Koneksi REST DEBUG",
    "minute": 60,
    "score": "0-0",
    "status": "TEST DEBUG - Bisa dihapus"
}

print(f"POST {url}")
try:
    r = requests.post(url, headers=headers, json=data, timeout=20)
    print(f"INSERT status: {r.status_code}")
    print(f"INSERT response: {r.text[:1000]}")
    print(f"INSERT headers: {dict(r.headers)}")
    
    if r.status_code not in [200,201,204]:
        print(f"❌ INSERT GAGAL - status {r.status_code}")
        # Jangan exit dulu, coba GET
    else:
        print("✅ INSERT BERHASIL")

    # Verify
    verify_url = SUPABASE_URL.rstrip("/") + "/rest/v1/matches?match_id=eq.TEST_GITHUB_DEBUG&select=*"
    print(f"GET {verify_url}")
    r2 = requests.get(verify_url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}, timeout=15)
    print(f"VERIFY status: {r2.status_code}")
    print(f"VERIFY body: {r2.text[:2000]}")
    
    if "TEST_GITHUB_DEBUG" in r2.text and r2.status_code == 200:
        print("✅✅✅ VERIFY OK - GitHub KONEK 100%! Tabel ada datanya!")
    else:
        print("❌ VERIFY GAGAL - Data tidak ada di Supabase")
        print("Cek: 1) SUPABASE_KEY kamu pakai sb_secret atau service_role? 2) Tabel matches ada kolom score/status?")
        # Fail workflow biar kelihatan merah
        if r.status_code >= 400:
            sys.exit(1)

except Exception as e:
    print(f"❌ EXCEPTION: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
