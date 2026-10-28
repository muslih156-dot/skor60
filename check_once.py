
import os, requests
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
        print(f"Saved {match_id} {home} vs {away} Menit {minute}")
    except Exception as e:
        print(f"Supabase save error: {e}")

def parse_clock(clock_str, detail_str=""):
    # ESPN bisa: "60:00", "60'", "60", "HT", "45+2", "90+3"
    try:
        s = (clock_str or detail_str or "").strip()
        if not s:
            return 0
        if "HT" in s.upper():
            return 45
        if "FT" in s.upper():
            return 90
        s = s.replace("'", "").replace('"', "").replace("’", "")
        if ":" in s:
            return int(s.split(":")[0])
        if "+" in s:
            return int(s.split("+")[0])
        # angka murni
        return int(float(s))
    except:
        return 0

def fetch_espn():
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
    try:
        r = requests.get(url, timeout=15)
        print(f"ESPN {url} -> {r.status_code} len {len(r.text)}")
        data = r.json()
        events = data.get("events", [])
        print(f"Total events dari ESPN: {len(events)}")
        return events
    except Exception as e:
        print(f"ESPN error: {e}")
        return []

def cek():
    events = fetch_espn()
    out = []
    inprog_list = []
    for ev in events:
        try:
            comp = ev.get("competitions", [{}])[0]
            status = comp.get("status", {})
            type_name = status.get("type", {}).get("name", "")
            state = status.get("type", {}).get("state", "")
            clock = status.get("displayClock", "") or status.get("clock", "") or ""
            detail = status.get("type", {}).get("shortDetail", "") or status.get("type", {}).get("detail", "") or ""
            minute = parse_clock(clock, detail)
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue
            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
            hs = int(home.get("score", 0) or 0)
            aws = int(away.get("score", 0) or 0)
            home_name = home.get("team", {}).get("displayName", "Home")
            away_name = away.get("team", {}).get("displayName", "Away")
            league = ev.get("leagues", [{}])[0].get("name") if ev.get("leagues") else "Soccer"

            is_live = "IN_PROGRESS" in type_name or state == "in"
            if is_live:
                inprog_list.append(f"{home_name} {hs}-{aws} {away_name} Menit {minute} ({clock}/{detail}) {league}")
                if 55 <= minute <= 68 and hs == 0 and aws == 0:
                    out.append({"id": ev.get("id"), "home": home_name, "away": away_name, "league": league, "minute": minute})
        except Exception as e:
            print(f"Parse error: {e}")
            continue
    print(f"--- {len(inprog_list)} IN-PROGRESS sekarang jam 00:09 WITA ---")
    for line in inprog_list[:20]:
        print(line)
    print(f"--- end list ---")
    return out

if __name__ == "__main__":
    print(f"Phase 1 - ESPN V5 DETAIL 00:09 WITA - {datetime.now()}")
    matches = cek()
    print(f"Found {len(matches)} match di jendela 55-68")
    for m in matches:
        if already_sent(m["id"]):
            print(f"Skip {m['id']} sudah ada")
            continue
        save_to_supabase(m["id"], m["home"], m["away"], m["league"], m["minute"], "AKTIF")
        pesan = f"""⚽ <b>TRADING BOLA MENIT 60 - 0-0</b>

🏟️ {m['home']} vs {m['away']}
🏆 {m['league']}
⏱️ Menit {m['minute']}

📊 AKTIF 🔥 Potensi Last Goal!

ID: {m['id']}"""
        ok = send_telegram(pesan)
        print(f"Telegram {m['id']}: {ok}")
    print("Done V5")
