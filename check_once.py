
import os, json, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WITA = timezone(timedelta(hours=8))

DATA_DIR = Path("data")
MATCHES_FILE = DATA_DIR / "matches.json"
ARCHIVE_DIR = DATA_DIR / "archive"

def wita_now():
    return datetime.now(WITA)

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

def load_matches():
    if MATCHES_FILE.exists():
        try:
            with open(MATCHES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_matches(matches):
    DATA_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True, parents=True)
    with open(MATCHES_FILE, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    all_time_file = ARCHIVE_DIR / "all_time.json"
    all_matches = []
    if all_time_file.exists():
        try:
            with open(all_time_file, 'r', encoding='utf-8') as f:
                all_matches = json.load(f)
        except:
            all_matches = []
    seen = {str(m.get("match_id")): m for m in all_matches}
    for m in matches:
        mid = str(m.get("match_id"))
        if mid not in seen:
            seen[mid] = m
        else:
            # Preserve score_deteksi
            old = seen[mid]
            if old.get("score_deteksi"):
                m["score_deteksi"] = old["score_deteksi"]
            seen[mid].update(m)
    with open(all_time_file, 'w', encoding='utf-8') as f:
        json.dump(list(seen.values()), f, indent=2, ensure_ascii=False)

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
            if status == "inprogress" and 60 <= minute <= 66 and hs == 0 and aws == 0:
                out.append({
                    "id": str(ev["id"]),
                    "home": ev["homeTeam"]["name"],
                    "away": ev["awayTeam"]["name"],
                    "league": ev["tournament"]["name"],
                    "league_slug": ev["tournament"].get("slug",""),
                    "minute": minute,
                })
        return out
    except Exception as e:
        print(f"Error: {e}")
        return []

def get_live_score(event_id):
    try:
        url = f"https://api.sofascore.com/api/v1/event/{event_id}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()
        ev = data.get("event", {})
        hs = ev.get("homeScore", {}).get("current", 0)
        aws = ev.get("awayScore", {}).get("current", 0)
        minute = ev.get("time", {}).get("minute", 0)
        status_type = ev.get("status", {}).get("type", "")
        status_desc = ev.get("status", {}).get("description", "")
        is_ft = status_type == "finished" or "FT" in status_desc or "Ended" in status_desc
        return {"score": f"{hs}-{aws}", "minute": minute, "is_ft": is_ft}
    except:
        return None

def get_stats(event_id):
    try:
        url = f"https://api.sofascore.com/api/v1/event/{event_id}/statistics"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()
        stats = {}
        for g in data.get("statistics", []):
            for s in g.get("groups", []):
                for it in s.get("statisticsItems", []):
                    if it["name"] in ["Total shots", "Shots on target", "Dangerous attacks"]:
                        stats[it["name"]] = {"home": it.get("homeValue", 0), "away": it.get("awayValue", 0)}
        return stats
    except:
        return {}

def analisa(stats):
    ts = int(stats.get("Total shots", {}).get("home", 0) or 0) + int(stats.get("Total shots", {}).get("away", 0) or 0)
    da = int(stats.get("Dangerous attacks", {}).get("home", 0) or 0) + int(stats.get("Dangerous attacks", {}).get("away", 0) or 0)
    sot = int(stats.get("Shots on target", {}).get("home", 0) or 0) + int(stats.get("Shots on target", {}).get("away", 0) or 0)
    if ts >= 12 and da >= 45 and sot >= 3:
        return f"AKTIF 🔥", ts, da, sot
    elif ts <= 6 and da <= 25:
        return f"PASIF 🥶", ts, da, sot
    else:
        return f"SEDANG 😐", ts, da, sot

if __name__ == "__main__":
    print(f"Check menit 60 - {wita_now()}")
    existing = load_matches()
    # Update existing
    for m in existing:
        if not m.get("is_ft"):
            live = get_live_score(m.get("match_id"))
            if live:
                m["live_score"] = live["score"]
                m["is_ft"] = live["is_ft"]
                if live["is_ft"]:
                    m["final_score"] = live["score"]
                    try:
                        hg, ag = map(int, live["score"].split("-"))
                        total = hg+ag
                        m["result"] = "WIN" if total>0 else "LOSE"
                    except:
                        pass
    # Scan new
    new_matches = cek_menit_60()
    existing_ids = set(str(m.get("match_id")) for m in existing)
    for nm in new_matches:
        if nm["id"] not in existing_ids:
            stats = get_stats(nm["id"])
            status_text, ts, da, sot = analisa(stats)
            match_data = {
                "match_id": nm["id"],
                "home_team": nm["home"],
                "away_team": nm["away"],
                "league": nm["league"],
                "league_slug": nm["league_slug"],
                "minute": nm["minute"],
                "minute_deteksi": nm["minute"],
                "score": "0-0",
                "score_deteksi": "0-0",
                "live_score": "0-0",
                "final_score": None,
                "status": status_text,
                "shots": ts,
                "da": da,
                "sot": sot,
                "created_at": wita_now().isoformat(),
                "is_ft": False,
                "result": "LIVE",
                "odds": round(1.46 + (da % 40) / 100, 2)
            }
            existing.append(match_data)
            send_telegram(f"⚽ MENIT 60 - 0-0\n{nm['home']} vs {nm['away']}\n{nm['league']} - Menit {nm['minute']}\n{status_text}")
    save_matches(existing[-100:])
    print("Done")
