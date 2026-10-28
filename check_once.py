
import os, requests
from datetime import datetime, timedelta
from supabase import create_client

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase connected")

def wita_now():
    # UTC +8
    utc = datetime.utcnow()
    wita = utc + timedelta(hours=8)
    return wita, utc

def send_telegram(pesan):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": pesan, "parse_mode": "HTML"}
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram error {e}")
        return False

def already_sent(mid):
    if not supabase:
        return False
    try:
        res = supabase.table("matches").select("match_id").eq("match_id", str(mid)).execute()
        return len(res.data) > 0
    except:
        return False

def save_to_supabase(mid, home, away, league, minute, status_text):
    if not supabase:
        return
    try:
        data = {
            "match_id": str(mid),
            "home_team": home,
            "away_team": away,
            "league": league,
            "minute": minute,
            "score": "0-0",
            "status": status_text,
        }
        supabase.table("matches").upsert(data, on_conflict="match_id").execute()
        print(f"Saved {mid} {home} vs {away} Menit {minute} {league}")
    except Exception as e:
        print(f"Save error {e}")

def parse_clock(clock_str, detail_str=""):
    try:
        s = (clock_str or detail_str or "").strip()
        if not s:
            return 0
        su = s.upper()
        if "HT" in su:
            return 45
        if "FT" in su or "FINAL" in su:
            return 90
        s = s.replace("'", "").replace('"', "").replace("’", "")
        if ":" in s:
            return int(s.split(":")[0])
        if "+" in s:
            return int(s.split("+")[0])
        return int(float(s))
    except:
        return 0

def fetch_espn_league(league_code, date_str):
    # league_code = all, eng.1, esp.1, ger.1, ita.1, fra.1, etc
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard"
    if date_str:
        url += f"?dates={date_str}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            print(f"ESPN {league_code} {date_str} -> {r.status_code}")
            return []
        j = r.json()
        evs = j.get("events", [])
        print(f"ESPN {league_code} dates={date_str} -> {len(evs)} events")
        return evs
    except Exception as e:
        print(f"ESPN {league_code} error {e}")
        return []

def cek():
    wita, utc = wita_now()
    print(f"WITA NOW: {wita.strftime('%Y-%m-%d %H:%M:%S')} WITA | UTC: {utc.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    # ESPN butuh YYYYMMDD
    date_wita = wita.strftime("%Y%m%d")
    date_wita_yesterday = (wita - timedelta(days=1)).strftime("%Y%m%d")
    date_utc = utc.strftime("%Y%m%d")

    all_events = {}
    leagues = ["all", "eng.1", "eng.2", "esp.1", "ger.1", "ita.1", "fra.1", "uefa.champions", "uefa.europa", "conmebol.libertadores", "mex.1", "usa.1", "bra.1"]
    for lg in leagues:
        for d in [date_wita, date_wita_yesterday, date_utc]:
            evs = fetch_espn_league(lg, d)
            for ev in evs:
                all_events[ev.get("id")] = ev
    print(f"Total UNIQUE events gabungan: {len(all_events)}")

    out = []
    inprog = []
    scheduled = 0
    finished = 0
    for ev in all_events.values():
        try:
            comp = ev.get("competitions", [{}])[0]
            status = comp.get("status", {})
            tname = status.get("type", {}).get("name", "")
            state = status.get("type", {}).get("state", "")
            clock = status.get("displayClock", "") or status.get("clock", "") or ""
            detail = status.get("type", {}).get("shortDetail", "") or status.get("type", {}).get("detail", "") or ""
            minute = parse_clock(clock, detail)
            comps = comp.get("competitors", [])
            if len(comps) < 2:
                continue
            home = next((c for c in comps if c.get("homeAway") == "home"), comps[0])
            away = next((c for c in comps if c.get("homeAway") == "away"), comps[1])
            hs = int(home.get("score", 0) or 0)
            aws = int(away.get("score", 0) or 0)
            hname = home.get("team", {}).get("displayName", "Home")
            aname = away.get("team", {}).get("displayName", "Away")
            league_name = (ev.get("leagues", [{}])[0].get("name") if ev.get("leagues") else comp.get("league", {}).get("name", "Soccer"))

            if "IN_PROGRESS" in tname or state == "in":
                line = f"{hname} {hs}-{aws} {aname} Menit {minute} ({clock}/{detail}) [{tname}/{state}] {league_name}"
                inprog.append((minute, line, ev, hs, aws, hname, aname, league_name))
            elif "PRE" in tname or state == "pre":
                scheduled += 1
            elif "POST" in tname or state == "post":
                finished += 1
        except Exception as e:
            print(f"parse err {e}")
            continue

    inprog_sorted = sorted(inprog, key=lambda x: x[0])
    print(f"--- {len(inprog_sorted)} IN-PROGRESS | {scheduled} SCHEDULED | {finished} FINISHED | WITA {wita.strftime('%H:%M')} ---")
    for minute, line, ev, hs, aws, hname, aname, league_name in inprog_sorted[:30]:
        print(line)
        if 55 <= minute <= 68 and hs == 0 and aws == 0:
            out.append({"id": ev.get("id"), "home": hname, "away": aname, "league": league_name, "minute": minute})

    if len(inprog_sorted) > 30:
        print(f"... dan {len(inprog_sorted)-30} lagi tidak ditampilkan")
    print("--- end list ---")
    return out

if __name__ == "__main__":
    wita, utc = wita_now()
    print(f"Phase 1 - ESPN V6 FIX DATE - WITA {wita} | UTC {utc}")
    matches = cek()
    print(f"Found {len(matches)} match di jendela 55-68 0-0")
    for m in matches:
        if already_sent(m["id"]):
            print(f"Skip {m['id']} sudah ada")
            continue
        save_to_supabase(m["id"], m["home"], m["away"], m["league"], m["minute"], "AKTIF")
        pesan = f"⚽ <b>MENIT 60 - 0-0</b>\n\n🏟️ {m['home']} vs {m['away']}\n🏆 {m['league']}\n⏱️ Menit {m['minute']}\n\nID: {m['id']}"
        send_telegram(pesan)
    print("Done V6")
