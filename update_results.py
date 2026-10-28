
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
        if r.status_code != 200:
            return None, None, None
        j = r.json()
        event = j.get("event", {})
        home = event.get("homeScore", {}).get("current")
        away = event.get("awayScore", {}).get("current")
        status = event.get("status", {}).get("type")
        if home is None or away is None:
            return None, None, None
        return home, away, status
    except Exception as e:
        print(f"Error fetch {match_id}: {e}")
        return None, None, None

def update_results():
    print(f"Phase 2 - Update final scores - {datetime.now()}")
    try:
        # Ambil 20 data terbaru yang final_score_home masih kosong
        res = supabase.table("matches").select("*").order("created_at", desc=True).limit(30).execute()
        all_matches = res.data
        to_update = [m for m in all_matches if m.get("final_score_home") is None]
        to_update = to_update[:20]
        print(f"Found {len(to_update)} matches to update from {len(all_matches)} total")
        
        for m in to_update:
            match_id = m["match_id"]
            home, away, status = get_final_score(match_id)
            if home is None:
                print(f"Skip {match_id}: no data")
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
    except Exception as e:
        print(f"Phase 2 error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    update_results()
