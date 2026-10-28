
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
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def already_sent(match_id):
    if not supabase:
        return False
    try:
        res = supabase.table("matches").select("match_id").eq("match_id", str(match_id)).execute()
        return len(res.data) > 0
    except:
        return False

def save_to_supabase(match_id, home, away, league, minute, status_text):
    if not supabase:
        return
    try:
        data = {
            "match_id": str(match_id),
            "home_team": home,
            "away_team": away,
            "league": league,
            "minute": minute,
            "score": "0-0",
            "status": status_text,
            "shots_total": 0,
            "dangerous_attacks": 0,
            "sot_total": 0,
            "xg": 0
        }
        supabase.table("matches").upsert(data, on_conflict="match_id").execute()
        print(f"Saved {match_id} {home} vs {away} Menit {minute} to Supabase")
    except Exception as e:
        print(f"Supabase save error: {e}")

def parse_clock_to_minute(clock_str):
    # ESPN clock format: "60:00" or "60'" or "60"
    try:
        if not clock_str:
            return 0
        clock_str = str(clock_str).strip().replace("'", "").replace('"', "")
        if ":" in clock_str:
            parts = clock_str.split(":")
            return int(parts[0])
        # Handle "60" or "45+2"
        if "+" in clock_str:
            return int(clock_str.split("+")[0])
        return int(float(clock_str))
    except:
        return 0

def fetch_espn_live():
    # ESPN free API - tidak diblokir Cloudflare, work dari GitHub Actions
    # Source: https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard【176882637611043416†L10-L13】
    urls = [
        "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard",
        "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
        "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard",
    ]
    all_events = []
    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            print(f"Try ESPN {url} -> Status {r.status_code} len {len(r.text)}")
            if r.status_code != 200:
                continue
            data = r.json()
            events = data.get("events", [])
            print(f"ESPN {url} -> {len(events)} events")
            all_events.extend(events)
        except Exception as e:
            print(f"ESPN error {url}: {e}")
            continue
    # Deduplicate by id
    seen = {}
    for ev in all_events:
        seen[ev.get("id")] = ev
    print(f"Total unique events from ESPN: {len(seen)}")
    return list(seen.values())

def cek_menit_60_espn():
    try:
        events = fetch_espn_live()
        print(f"Total live events dari ESPN: {len(events)}")
        out = []
        debug_00 = 0
        debug_inprogress = 0
        for ev in events:
            try:
                comp = ev.get("competitions", [{}])[0]
                status = comp.get("status", {})
                type_name = status.get("type", {}).get("name", "")  # STATUS_IN_PROGRESS
                state = status.get("type", {}).get("state", "")  # in
                clock = status.get("displayClock", "") or status.get("clock", "") or ""
                minute = parse_clock_to_minute(clock)
                # Kalau tidak ada clock, coba period + time elapsed
                if minute == 0:
                    # Kadang minute di status.type.detail
                    detail = status.get("type", {}).get("detail", "") or status.get("type", {}).get("shortDetail", "")
                    # detail contoh: "60'" 
                    minute = parse_clock_to_minute(detail)

                competitors = comp.get("competitors", [])
                if len(competitors) < 2:
                    continue
                home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
                away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})
                hs = int(home.get("score", 0) or 0)
                aws = int(away.get("score", 0) or 0)
                home_name = home.get("team", {}).get("displayName", "Home")
                away_name = away.get("team", {}).get("displayName", "Away")
                league = ev.get("league", {}).get("name") or comp.get("league", {}).get("name") or ev.get("competitions", [{}])[0].get("tournament", {}).get("name", "") or "ESPN"
                # Untuk all scoreboard, league name ada di ev["league"]
                if not league or league == "ESPN":
                    league = ev.get("leagues", [{}])[0].get("name") if ev.get("leagues") else comp.get("type", {}).get("abbreviation", "Soccer")

                is_in_progress = "IN_PROGRESS" in type_name or state == "in"
                if is_in_progress:
                    debug_inprogress += 1

                if hs == 0 and aws == 0:
                    debug_00 += 1

                if is_in_progress and 55 <= minute <= 68 and hs == 0 and aws == 0:
                    out.append({
                        "id": ev.get("id"),
                        "home": home_name,
                        "away": away_name,
                        "league": league,
                        "minute": minute
                    })
            except Exception as e:
                print(f"Parse error event {ev.get('id')}: {e}")
                continue
        print(f"Debug: {debug_inprogress} in-progress, {debug_00} matches 0-0 any minute")
        return out
    except Exception as e:
        print(f"Error cek_menit_60_espn: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    print(f"Phase 1 - ESPN FREE API - {datetime.now()}")
    matches = cek_menit_60_espn()
    print(f"Found {len(matches)} match di jendela 55-68 ESPN")
    for m in matches:
        if already_sent(m["id"]):
            print(f"Skip {m['id']} sudah pernah dikirim")
            continue
        save_to_supabase(m["id"], m["home"], m["away"], m["league"], m["minute"], "AKTIF")
        pesan = f"""⚽ <b>TRADING BOLA MENIT 60 - LAST GOAL SYSTEM - 0-0</b>

🏟️ {m['home']} vs {m['away']}
🏆 {m['league']}
⏱️ Menit {m['minute']}

📊 AKTIF 🔥 Menit 60 masih 0-0 - Potensi Last Goal!

ID: {m['id']}"""
        ok = send_telegram(pesan)
        print(f"Telegram sent {m['id']}: {ok}")
    print("Done Phase 1 ESPN")
