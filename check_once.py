
import os
import requests
from datetime import datetime
from supabase import create_client

# Coba pakai cloudscraper kalau ada, fallback ke requests
try:
    import cloudscraper
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome','platform': 'windows','mobile': False})
    print("CloudScraper loaded - Cloudflare bypass ON")
except:
    scraper = requests
    print("CloudScraper not found, using requests")

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

def already_sent(match_id):
    if not supabase:
        return False
    try:
        res = supabase.table("matches").select("match_id").eq("match_id", str(match_id)).execute()
        return len(res.data) > 0
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

def fetch_live_events():
    # Endpoint 1: Sofascore via CloudScraper
    endpoints = [
        "https://www.sofascore.com/api/v1/sport/football/events/live",
        "https://api.sofascore.com/api/v1/sport/football/events/live",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.sofascore.com/",
        "Accept": "application/json",
    }
    for url in endpoints:
        try:
            r = scraper.get(url, headers=headers, timeout=20)
            print(f"Try {url} -> Status {r.status_code} len {len(r.text)}")
            if r.status_code != 200:
                continue
            if "<!DOCTYPE" in r.text[:100]:
                print(f"Still Cloudflare HTML di {url}")
                continue
            data = r.json()
            events = data.get("events", [])
            print(f"Success {url} -> {len(events)} events")
            if len(events) > 0:
                return events
        except Exception as e:
            print(f"Error {url}: {e}")
            continue

    # Fallback: ESPN API (tidak diblokir Cloudflare, selalu 200)
    print("Fallback ke ESPN API...")
    try:
        # ESPN scoreboard - ambil semua liga
        espn_url = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"
        r = requests.get(espn_url, timeout=10)
        if r.status_code == 200:
            print(f"ESPN fallback -> {len(r.text)} len (struktur beda, jadi 0 untuk Sofascore format)")
    except Exception as e:
        print(f"ESPN error: {e}")

    return []

def cek_menit_60():
    try:
        events = fetch_live_events()
        print(f"Total live events dari Sofascore: {len(events)}")
        out = []
        debug_00 = 0
        for ev in events:
            minute = ev.get("time", {}).get("minute", 0) or 0
            hs = ev.get("homeScore", {}).get("current", 0)
            aws = ev.get("awayScore", {}).get("current", 0)
            status = ev.get("status", {}).get("type")
            if hs == 0 and aws == 0:
                debug_00 += 1
            league = ev.get("tournament", {}).get("name", "")
            category = ev.get("tournament", {}).get("category", {}).get("name", "")
            if status == "inprogress" and 55 <= minute <= 68 and hs == 0 and aws == 0:
                low = (league + " " + category).lower()
                if "women" in low or "u19" in low or "u21" in low or "u17" in low:
                    continue
                out.append({
                    "id": ev["id"],
                    "home": ev["homeTeam"]["name"],
                    "away": ev["awayTeam"]["name"],
                    "league": league,
                    "minute": minute
                })
        print(f"Debug: {debug_00} matches currently 0-0 live (any minute)")
        return out
    except Exception as e:
        print(f"Error cek_menit_60: {e}")
        return []

def get_stats(event_id):
    try:
        headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.sofascore.com/"}
        url = f"https://api.sofascore.com/api/v1/event/{event_id}/statistics"
        r = scraper.get(url, headers=headers, timeout=15)
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
    print(f"Phase 1 - Check menit 60 FIX v3 CloudScraper - {datetime.now()}")
    matches = cek_menit_60()
    print(f"Found {len(matches)} match di jendela 55-68")
    for m in matches:
        if already_sent(m["id"]):
            print(f"Skip {m['id']} sudah pernah dikirim")
            continue
        stats = get_stats(m["id"])
        analisa_text, status_simple = analisa(stats)
        save_to_supabase(m["id"], m["home"], m["away"], m["league"], m["minute"], status_simple, stats)
        pesan = f"""⚽ <b>TRADING BOLA MENIT 60 - LAST GOAL SYSTEM - 0-0</b>

🏟️ {m['home']} vs {m['away']}
🏆 {m['league']}
⏱️ Menit {m['minute']}

📊 {analisa_text}

ID: {m['id']}"""
        ok = send_telegram(pesan)
        print(f"Telegram sent {m['id']}: {ok}")
    print("Done Phase 1 FIX v3")
