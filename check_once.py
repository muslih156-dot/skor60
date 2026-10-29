
import os, json, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

WITA = timezone(timedelta(hours=8))
DATA_DIR = Path("data")
MATCHES_FILE = DATA_DIR / "matches.json"
ARCHIVE_DIR = DATA_DIR / "archive"

def now_wita():
    return datetime.now(WITA)

def load_matches():
    if MATCHES_FILE.exists():
        try:
            with open(MATCHES_FILE,'r',encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_matches(matches):
    DATA_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True, parents=True)
    with open(MATCHES_FILE,'w',encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    # Archive
    arch_file = ARCHIVE_DIR / "all_time.json"
    with open(arch_file,'w',encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    # Also save to root for Streamlit fallback
    with open("matches.json",'w',encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    with open("all_time.json",'w',encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

def cek_menit_60():
    try:
        url = "https://api.sofascore.com/api/v1/sport/football/events/live"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
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
                    "league": ev["tournament"].get("slug",""),
                })
        return out
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    print(f"Scan {now_wita()} - RESET MODE mulai dari 0")
    existing = load_matches()
    print(f"Existing: {len(existing)} match")
    # Keep only last 20 if any, but if resetting, this will be 0
    new_matches = cek_menit_60()
    print(f"Found {len(new_matches)} new 0-0 at 60'")
    for nm in new_matches:
        if nm["id"] not in [str(m.get("match_id")) for m in existing]:
            existing.append({
                "match_id": nm["id"],
                "home_team": nm["home"],
                "away_team": nm["away"],
                "league": nm["league"],
                "minute": 60,
                "score": "0-0",
                "score_deteksi": "0-0",
                "live_score": "0-0",
                "final_score": None,
                "is_ft": False,
                "result": "LIVE",
                "created_at": now_wita().isoformat(),
                "odds": 1.8
            })
    save_matches(existing[-50:])
    print(f"Saved {len(existing)} total")
