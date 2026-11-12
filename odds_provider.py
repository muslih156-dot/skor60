# odds_provider.py - Ambil odds nyata dari The Odds API
import os
import urllib.request
import urllib.parse
import json

API_KEY = os.environ.get("ODDS_API_KEY", "")

def get_live_over_05_odds(home_team, away_team):
    if not API_KEY:
        return None
    try:
        url = (
            "https://api.the-odds-api.com/v4/sports/soccer/odds/?"
            + urllib.parse.urlencode({
                "apiKey": API_KEY,
                "regions": "eu,uk",
                "markets": "totals",
                "oddsFormat": "decimal",
            })
        )
        req = urllib.request.Request(url, headers={"User-Agent": "skor60"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))

        home = str(home_team).lower()
        away = str(away_team).lower()
        for ev in data:
            ev_home = str(ev.get("home_team", "")).lower()
            ev_away = str(ev.get("away_team", "")).lower()
            if home[:5] in ev_home and away[:5] in ev_away:
                for bm in ev.get("bookmakers", []):
                    for m in bm.get("markets", []):
                        if m.get("key") == "totals":
                            for o in m.get("outcomes", []):
                                if o.get("name") == "Over" and float(o.get("point", 99)) == 0.5:
                                    return {"odds": float(o.get("price")), "source": f"Actual - {bm.get('title')}"}
                return None
        return None
    except Exception as e:
        print(f"[odds] gagal ambil odds nyata: {e}")
        return None
