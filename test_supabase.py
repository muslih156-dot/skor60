
import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
print(f"Supabase connected to {SUPABASE_URL}")

# Insert TEST_GITHUB
data = {
    "match_id": "TEST_GITHUB",
    "home_team": "GitHub",
    "away_team": "Supabase",
    "league": "Test Koneksi",
    "minute": 60,
    "score": "0-0",
    "status": "TEST KONEKSI - Bisa dihapus lagi | ⚠️ TEST - Hati-hati"
}

res = supabase.table("matches").upsert(data, on_conflict="match_id").execute()
print(f"Inserted TEST_GITHUB: {res.data}")

# Baca balik
res2 = supabase.table("matches").select("*").eq("match_id", "TEST_GITHUB").execute()
print(f"Verify TEST_GITHUB ada: {len(res2.data)} row - {res2.data}")

print("Done - Sekarang cek Supabase Table Editor, harusnya ada TEST_GITHUB. Kalau ada, berarti GitHub KONEK 100%! Hapus lagi di Table Editor > Delete kalau sudah yakin.")
