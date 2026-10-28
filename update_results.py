
import os
import requests
from supabase import create_client
from datetime import datetime

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_final_score(match_id):
    try:
        url = f"https://api.sofascore.com/api/v1/event/{match_id}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        j = r.json()
        event = j.get("event", {})
        home = event.get("homeScore", {}).get("current", 0)
        away = event.get("awayScore", {}).get("current", 0)
        status = event.get("status", {}).get("type")  # finished
        return home, away, status
    except Exception as e:
        print(f"Error fetch {match_id}: {e}")
        return None, None, None

def update_results():
    print(f"Phase 2 - Update final scores - {datetime.now()}")
    # Ambil semua match yang belum ada final_score
    res = supabase.table("matches").select("*").is_("final_score_home", "null").limit(20).execute()
    matches = res.data
    print(f"Found {len(matches)} matches to update")
    for m in matches:
        match_id = m["match_id"]
        # Jangan update kalau masih baru (kurang dari 2 jam)
        home, away, status = get_final_score(match_id)
        if home is None:
            continue
        if status != "finished":
            print(f"{match_id} belum selesai: {status}")
            continue
        
        goal_after = (home + away) > 0
        final_status = f"{home}-{away}"
        print(f"Updating {match_id}: {final_status} goal_after={goal_after}")
        
        supabase.table("matches").update({
            "final_score_home": home,
            "final_score_away": away,
            "goal_after_60": goal_after,
            "final_status": final_status
        }).eq("match_id", match_id).execute()
    print("Done Phase 2")

if __name__ == "__main__":
    update_results()
