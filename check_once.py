import os
import requests
from datetime import datetime
from supabase import create_client

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase connected")

def send_telegram(pesan):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": pesan, "parse_mode": "HTML"}
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except:
        return False

def save_to_supabase(match_id, home, away, league, minute, status_text, stats):
    if not supabase:
        return
    try:
        ts = int(stats.get("Total shots", {}).get("home", 0) or 0) + int(stats.get("Total shots", {}).get("away", 0) or 0)
        da = int(stats.get("Dangerous attacks", {}).get("home", 0) or 0) + int(stats.get("Dangerous attacks", {}).get("away", 0) or 0)
        sot = int(stats.get("Shots on target", {}).get("home", 0) or 0) + int(stats.get("Shots on target", {}).get("away", 0) or 0)
        try:
            xg = float(stats.get("Expected goals", {}).get("home", 0) or 0) + float(stats.get("Expected goals", {}).get("away", 0) or 0)
        except:
            xg = 0

        data = {
            "match_id": str(match_id),
            "home_team": home,
            "away_team": away,
            "league": league,
            "minute": minute,
            "score": "0-0",
            "status": status_text,
            "shots_total": ts,
            "dangerous_attacks": da,
            "sot_total": sot,
            "xg": xg
        }
        supabase.table("matches").upsert(data, on_conflict="match_id").execute()
        print(f"Saved {match_id} to Supabase")
    except Exception as e:
        print(f"Supabase save error: {e}")

def cek_menit_60():
    try:
        url = "https://api.sofascore.com/api/v1/sport/football/events/live"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data = r.json()
        out = []
        for ev in data.get("events", []):
            minute = ev.get("time", {}).get("minute", 0)
            hs = ev.get("homeScore", {}).get("current", 0)
            aws = ev.get("awayScore", {}).get("current", 0)
            status = ev.get("status", {}).get("type")
            if status == "inprogress" and 59 <= minute <= 62 and hs == 0 and aws == 0:
                out.append({
                    "id": ev["id"],
                    "home": ev["homeTeam"]["name"],
                    "away": ev["awayTeam"]["name"],
                    "league": ev["tournament"]["name"],
                    "minute": minute
                })
        return out
    except Exception as e:
        print(f"Error: {e}")
        return []

def get_stats(event_id):
    try:
        url = f"https://api.sofascore.com/api/v1/event/{event_id}/statistics"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()
        stats = {}
        for g in data.get("statistics", []):
            for s in g.get("groups", []):
                for it in s.get("statisticsItems", []):
                    if it["name"] in ["Total shots", "Shots on target", "Dangerous attacks", "Expected goals"]:
                        stats[it["name"]] = {"home": it.get("homeValue", 0), "away": it.get("awayValue", 0)}
        return stats
    except:
        return {}

def analisa(stats):
    ts = int(stats.get("Total shots", {}).get("home", 0) or 0) + int(stats.get("Total shots", {}).get("away", 0) or 0)
    da = int(stats.get("Dangerous attacks", {}).get("home", 0) or 0) + int(stats.get("Dangerous attacks", {}).get("away", 0) or 0)
    sot = int(stats.get("Shots on target", {}).get("home", 0) or 0) + int(stats.get("Shots on target", {}).get("away", 0) or 0)
    if ts >= 12 and da >= 45 and sot >= 3:
        return f"AKTIF 🔥 Shots {ts} DA {da} SoT {sot}", "AKTIF"
    elif ts <= 6 and da <= 25:
        return f"PASIF 🥶 Shots {ts} DA {da} SoT {sot}", "PASIF"
    else:
        return f"SEDANG 😐 Shots {ts} DA {da} SoT {sot}", "SEDANG"

if __name__ == "__main__":
    print(f"Phase 1 - Check menit 60 + Save to Supabase - {datetime.now()}")
    matches = cek_menit_60()
    print(f"Found {len(matches)} match")
    for m in matches:
        stats = get_stats(m["id"])
        analisa_text, status_simple = analisa(stats)
        # 1. Simpan ke database dulu
        save_to_supabase(m["id"], m["home"], m["away"], m["league"], m["minute"], status_simple, stats)
        # 2. Baru kirim Telegram
        pesan = f"""⚽ <b>MENIT 60 - 0-0</b>

🏟️ {m['home']} vs {m['away']}
🏆 {m['league']}
⏱️ Menit {m['minute']}

📊 {analisa_text}

💾 Saved to DB Level 5

ID: {m['id']}"""
        send_telegram(pesan)
    print("Done Phase 1")
