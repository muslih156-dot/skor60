"""
odds_provider.py - V3 FIX FINAL
Sistem Odds Tanpa 1.80 Sim
Urutan: 1. Actual dari The Odds API -> 2. Est dari History Liga (hanya SETTLED) -> 3. Est Global
FIX V3:
- Unknown League langsung ke Global, jangan hitung 292 match campur aduk
- History Liga cuma hitung match SETTLED yang ada final_score, jangan hitung PENDING 0-0
"""

import os
import json
import glob
import math
import requests

# API Key dari GitHub Secrets / env
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/soccer/odds"

# Cache biar nggak boros request
_odds_cache = {}

def _safe_float(val, default=0.0):
    try:
        if val is None or val == "":
            return default
        return float(val)
    except:
        return default

def _get_lambda_to_odds_over05(lam):
    """
    Rumus Poisson: P(Over 0.5) = 1 - exp(-lam)
    Odds = 1 / P
    lam = rata-rata total gol per match di liga itu
    """
    try:
        lam = float(lam)
        if lam <= 0:
            lam = 2.45
        p_over = 1 - math.exp(-lam)
        if p_over <= 0.05:
            p_over = 0.05
        if p_over >= 0.95:
            p_over = 0.95
        odds = 1 / p_over
        # Batas wajar untuk Over 0.5 After 60': 1.25 - 2.80
        odds = max(1.25, min(2.80, odds))
        return round(odds, 2)
    except:
        return 1.62

def _estimate_lambda_from_league_history(league_name):
    """
    HITUNG MANUAL TANPA API: Baca database kita sendiri
    FIX V3: Cuma hitung match yang UDAH SELESAI (SETTLED), jangan hitung yang masih 0-0 / PENDING.
    Kalau league-nya Unknown League, JANGAN dipakai, langsung ke Global.
    """
    try:
        league_key = str(league_name or "").lower().strip()
        # [FIX] Kalau Unknown, langsung skip, jangan ngitung 292 match campur aduk
        if league_key in ("", "unknown league", "unknown", "none"):
            return None, 0

        total_goals = 0
        total_matches = 0
        for fpath in glob.glob("data/*.json") + glob.glob("data/**/*.json", recursive=True):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                records = []
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict):
                    # Coba semua key yang mungkin
                    if isinstance(data.get("records"), list):
                        records = data.get("records", [])
                    elif isinstance(data.get("matches"), list):
                        records = data.get("matches", [])
                    elif isinstance(data.get("data"), list):
                        records = data.get("data", [])
                    else:
                        continue
                for rec in records:
                    if not isinstance(rec, dict):
                        continue
                    # [FIX] Cuma hitung yang udah SETTLED / final, jangan yang PENDING 0-0
                    status = str(rec.get("settlement_status", "")).upper()
                    if status not in ("SETTLED", "SETTLED_WIN", "SETTLED_LOSE", "VOID"):
                        continue
                    rec_league = str(rec.get("league", "")).lower().strip()
                    if rec_league != league_key:
                        continue
                    score_str = str(rec.get("final_score", "") or rec.get("current_score", "") or rec.get("score", ""))
                    # [FIX] Harus ada final_score yang bener, bukan 0-0 entry
                    if "-" not in score_str:
                        continue
                    try:
                        # Ambil format "2-1" atau "2 - 1"
                        clean = score_str.replace(" ", "").split("|")[0].strip()
                        a, b = clean.split("-")[:2]
                        total_goals += int(a) + int(b)
                        total_matches += 1
                    except:
                        pass
            except:
                continue
        if total_matches >= 5:
            lam = total_goals / total_matches
            return max(1.2, min(4.0, lam)), total_matches
        return None, total_matches
    except Exception as e:
        print(f"[odds] gagal baca history liga: {e}")
        return None, 0

def _get_actual_odds_from_api(home_team, away_team, league_name):
    """
    Ambil odds Actual dari The Odds API
    Return None kalau gagal / key salah / kuota habis / match nggak ketemu
    """
    if not ODDS_API_KEY:
        print("[odds] ODDS_API_KEY kosong, skip API")
        return None

    # Cache key biar nggak request berkali-kali untuk match yang sama
    cache_key = f"{home_team}|{away_team}".lower()
    if cache_key in _odds_cache:
        return _odds_cache[cache_key]

    try:
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "eu",
            "markets": "totals",
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }
        resp = requests.get(ODDS_API_URL, params=params, timeout=15)
        if resp.status_code == 401:
            print("[odds] API gagal / kuota habis (HTTP Error 401: Unauthorized), pakai hitung manual Liga")
            return None
        if resp.status_code == 429:
            print("[odds] API kuota habis (429), pakai hitung manual Liga")
            return None
        if resp.status_code != 200:
            print(f"[odds] API gagal status {resp.status_code}, pakai hitung manual Liga")
            return None

        data = resp.json()
        home_low = str(home_team or "").lower().strip()
        away_low = str(away_team or "").lower().strip()

        for match in data:
            api_home = str(match.get("home_team", "")).lower().strip()
            api_away = str(match.get("away_team", "")).lower().strip()
            # Cocokin nama tim, boleh kebalik / sebagian
            if (home_low in api_home or api_home in home_low) and (away_low in api_away or api_away in away_low):
                # Cari market totals Over 0.5
                for bookmaker in match.get("bookmakers", []):
                    for market in bookmaker.get("markets", []):
                        if market.get("key") == "totals":
                            for outcome in market.get("outcomes", []):
                                if outcome.get("name") == "Over" and _safe_float(outcome.get("point"), 99) == 0.5:
                                    odds_val = _safe_float(outcome.get("price"), 0)
                                    if odds_val > 1.01:
                                        result = {"odds": round(odds_val, 2), "source": f"Actual - {bookmaker.get('title','API')}", "type": "Actual"}
                                        _odds_cache[cache_key] = result
                                        return result
        # Match nggak ketemu di API
        _odds_cache[cache_key] = None
        return None
    except Exception as e:
        print(f"[odds] API error: {e}, pakai hitung manual Liga")
        return None

def get_odds_with_fallback(home_team, away_team, league_name):
    """
    FUNGSI UTAMA - DIPAKAI check_once.py DAN migrate_old_odds.py
    TIDAK PERNAH return None, selalu ada odds.
    Urutan:
    1. Actual dari API
    2. Est dari History Liga (kalau liga dikenal + ada minimal 5 match SETTLED)
    3. Est Global (lam = 2.45 -> odds 1.62)
    """
    # 1. Coba Actual
    actual = _get_actual_odds_from_api(home_team, away_team, league_name)
    if actual:
        return actual

    # 2. Coba Est dari Liga
    lam, count = _estimate_lambda_from_league_history(league_name)
    if lam is not None and count >= 5:
        odds = _get_lambda_to_odds_over05(lam)
        return {
            "odds": odds,
            "source": f"Est - Liga {league_name} ({count} match, lam={lam:.1f})",
            "type": "Est"
        }

    # 3. Fallback Global - lam rata-rata dunia 2.45
    odds_global = _get_lambda_to_odds_over05(2.45)
    return {
        "odds": odds_global,
        "source": "Est - Global",
        "type": "Est"
    }
