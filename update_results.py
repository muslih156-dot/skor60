
import json, requests, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

WITA = timezone(timedelta(hours=8))
DATA_FILE = Path("data/matches.json")

def load_matches():
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_matches(matches):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

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
        return {
            "home_score": hs,
            "away_score": aws,
            "score": f"{hs}-{aws}",
            "minute": minute,
            "status_type": status_type,
            "status_desc": status_desc,
            "is_ft": is_ft
        }
    except Exception as e:
        print(f"Error {event_id}: {e}")
        return None

matches = load_matches()
print(f"Loaded {len(matches)} matches")

for m in matches:
    mid = str(m.get("match_id"))
    # Skip if already has real FT that is not 0-0? Actually re-check all that are marked FT but 0-0 to verify
    live = get_live_score(mid)
    if live:
        print(f"{mid}: {m.get('home_team')} vs {m.get('away_team')} - Live {live['score']} FT={live['is_ft']} (old final {m.get('final_score')})")
        # Update if FT or if old final was 0-0 and live has goals
        if live["is_ft"] or live["score"] != "0-0":
            old_final = m.get("final_score")
            m["final_score"] = live["score"]
            m["live_score"] = live["score"]
            m["is_ft"] = live["is_ft"]
            # Recalc WIN/LOSE: detection 0-0 vs FT
            try:
                hg, ag = map(int, live["score"].split("-"))
                total = hg+ag
                m["gol_terjadi"] = total > 0
                m["result"] = "WIN" if total>0 else "LOSE"
                m["result_calc"] = m["result"]
                m["total_gol_setelah"] = total
                print(f"  -> Updated to {live['score']} => {m['result']}")
            except:
                pass
        time.sleep(1)  # be nice to API

save_matches(matches)
print("Done updating")
