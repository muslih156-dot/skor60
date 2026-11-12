# odds_provider.py - Ambil odds nyata dari The Odds API
# Dipanggil pas scanner deteksi match menit 60' 0-0
import os
import urllib.request
import urllib.parse
import json

API_KEY = os.environ.get("ODDS_API_KEY", "")

def get_live_over_05_odds(home_team, away_team):
    """
    Coba ambil odds Over 0.5 / Totals dari The Odds API.
    Kalau gagal / nggak ada (liga kecil), return None -> dashboard balik ke (Sim)
    """
    if not API_KEY:
        return None
    try:
        # The Odds API: soccer = semua liga sepakbola
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

        # Cari match yang namanya mirip
        home = home_team.lower()
        away = away_team.lower()
        for ev in data:
            ev_home = str(ev.get("home_team", "")).lower()
            ev_away = str(ev.get("away_team", "")).lower()
            if home[:5] in ev_home and away[:5] in ev_away:
                # Ambil bookmaker pertama yang ada totals
                for bm in ev.get("bookmakers", []):
                    for m in bm.get("markets", []):
                        if m.get("key") == "totals":
                            for o in m.get("outcomes", []):
                                # Over 0.5
                                if o.get("name") == "Over" and float(o.get("point", 99)) == 0.5:
                                    return {
                                        "odds": float(o.get("price")),
                                        "source": f"Actual - {bm.get('title')}",
                                        "bookmaker": bm.get("title"),
                                    }
                # Kalau cuma ada Over 2.5 pre-match, kita pakai sebagai referensi
                # tapi jangan dipaksa jadi Over 0.5 live
                return None
        return None
    except Exception as e:
        print(f"[odds] gagal ambil odds nyata: {e}")
        return None
