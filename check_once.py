"""
check_once.py - V7 FINAL - MANUAL 100%, TANPA ODDS API
Jalan tiap 5 menit via GitHub Actions.
Tugas:
1. Ambil live score dari ESPN (gratis, tanpa key)
2. Filter: Menit 60-70, Skor masih 0-0, Belum pernah di-entry
3. Kasih odds MANUAL dari odds_provider.py (Est - Liga / Est - Global)
4. Simpan ke data/archive/daily/YYYY-MM-DD.json + data/latest.json (buat dashboard)
5. Settlement: Kalau match udah Final, hitung WIN/LOSE + Profit dari Result

TIDAK ADA LAGI: ODDS_API_KEY, The Odds API, Actual, 401
"""

import os
import json
import glob
import sys
from datetime import datetime, timezone, timedelta
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odds_provider import get_odds_with_fallback

# ============ CONFIG ============
try:
    from config import DEFAULT_STAKE, MIN_ENTRY_MINUTE, MAX_ENTRY_MINUTE
except:
    DEFAULT_STAKE = 50000
    MIN_ENTRY_MINUTE = 60
    MAX_ENTRY_MINUTE = 70

# ESPN Scoreboard - Gratis, tanpa key
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
# Liga yang di-scan, biar nggak kebanyakan
ESPN_LEAGUES = [
    "eng.1", "esp.1", "ita.1", "ger.1", "fra.1",
    "eng.2", "esp.2", "ita.2", "ger.2",
    "bra.1", "mex.1", "usa.1", "ned.1", "por.1", "bel.1",
    "jpn.1", "kor.1", "aus.1", "arg.1",
]

DATA_DIR = "data"
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive", "daily")
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# WIB = UTC+7
WIB = timezone(timedelta(hours=7))

def _safe_float(v, d=0.0):
    try:
        if v is None or v == "":
            return d
        return float(v)
    except:
        return d

def _today_str():
    return datetime.now(WIB).strftime("%Y-%m-%d")

def _load_today_records():
    """Load record hari ini dari archive"""
    fpath = os.path.join(ARCHIVE_DIR, f"{_today_str()}.json")
    if os.path.exists(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data, fpath
                if isinstance(data, dict) and isinstance(data.get("records"), list):
                    return data["records"], fpath
        except:
            pass
    return [], fpath

def _save_today_records(records, fpath):
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

def _parse_minute(detail):
    """Ubah '64'' atau '60' jadi int 64"""
    try:
        s = str(detail or "").replace("'", "").replace("+", "").strip()
        # Kalau ada 'HT', 'FT', dll
        if not s or not s[0].isdigit():
            return None
        # 90+3 -> ambil 90
        if "+" in str(detail):
            s = str(detail).split("+")[0]
        return int(s)
    except:
        return None

def _fetch_espn_league(league_code):
    """Ambil live score 1 liga dari ESPN"""
    try:
        url = ESPN_URL.format(league=league_code)
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return []
        data = resp.json()
        events = data.get("events", [])
        out = []
        for ev in events:
            try:
                comp = ev.get("competitions", [{}])[0]
                status = comp.get("status", {})
                status_type = status.get("type", {})
                state = status_type.get("state", "")  # in, pre, post
                detail = status.get("displayClock", "") or status_type.get("detail", "")
                home_team = ""
                away_team = ""
                home_score = 0
                away_score = 0
                for team in comp.get("competitors", []):
                    name = team.get("team", {}).get("displayName", "") or team.get("team", {}).get("shortDisplayName", "")
                    score = _safe_float(team.get("score", 0), 0)
                    if team.get("homeAway") == "home":
                        home_team = name
                        home_score = int(score)
                    else:
                        away_team = name
                        away_score = int(score)
                league_name = comp.get("venue", {}).get("fullName", "")  # fallback
                # Nama liga dari events
                league_name = ev.get("league", {}).get("name", "") or league_code
                if not home_team or not away_team:
                    continue
                out.append({
                    "id": str(ev.get("id", "")),
                    "home": home_team,
                    "away": away_team,
                    "home_score": home_score,
                    "away_score": away_score,
                    "minute": _parse_minute(detail),
                    "detail": detail,
                    "state": state,  # in / pre / post
                    "league": league_name,
                    "league_code": league_code,
                })
            except:
                continue
        return out
    except Exception as e:
        print(f"[fetch] {league_code} gagal: {e}")
        return []

def _settle_record(rec, live_match):
    """Update record yang udah Final -> WIN / LOSE + Profit"""
    # Kalau live_match udah post / FT
    if live_match["state"] == "post":
        final_score = f"{live_match['home_score']}-{live_match['away_score']}"
        rec["current_score"] = final_score
        rec["final_score"] = final_score
        rec["score"] = final_score
        # Over 0.5 After 60' itu WIN kalau ada gol SETELAH entry.
        # Entry kita 0-0 di menit 60, jadi WIN kalau final_score BUKAN 0-0.
        # Karena entry_score selalu 0-0, rumusnya simple:
        if final_score != "0-0":
            rec["result"] = "WIN"
            rec["settlement_status"] = "SETTLED"
            profit = round(rec["stake"] * (rec["odds_entry"] - 1), 2)
        else:
            rec["result"] = "LOSE"
            rec["settlement_status"] = "SETTLED"
            profit = round(-rec["stake"], 2)
        rec["profit"] = profit
        rec["pnl"] = profit
        rec["p_l"] = profit
        return True
    else:
        # Masih live, update current score aja
        cur = f"{live_match['home_score']}-{live_match['away_score']}"
        rec["current_score"] = cur
        rec["score"] = cur
        if rec.get("result") in ("", None):
            rec["result"] = "LIVE"
        return False

def main():
    print(f"=== CHECK_ONCE V7 MANUAL - {_today_str()} {datetime.now(WIB).strftime('%H:%M:%S')} WIB ===")
    print(f"Stake: {DEFAULT_STAKE} | Entry menit: {MIN_ENTRY_MINUTE}-{MAX_ENTRY_MINUTE} | Odds: MANUAL (Est)")

    records, fpath = _load_today_records()
    # Index biar gampang cari record lama
    by_id = {str(r.get("match_id", "")): r for r in records if isinstance(r, dict)}
    print(f"Record hari ini sebelum scan: {len(records)}")

    new_entry = 0
    settled = 0

    for league_code in ESPN_LEAGUES:
        matches = _fetch_espn_league(league_code)
        for m in matches:
            mid = m["id"]
            # 1. Kalau udah ada record-nya, update settlement / live score
            if mid in by_id:
                rec = by_id[mid]
                # Kalau udah SETTLED, skip, nggak usah diutak-atik lagi
                if str(rec.get("settlement_status", "")).upper() == "SETTLED":
                    continue
                # Kalau masih LIVE / PENDING, update
                if _settle_record(rec, m):
                    settled += 1
                    print(f"  [SETTLED] {m['home']} vs {m['away']} | Final {m['home_score']}-{m['away_score']} | {rec.get('result')} | Profit {rec.get('profit')}")
                continue

            # 2. Kalau belum ada, cek apakah layak entry?
            # Syarat: state = in (live), menit 60-70, skor masih 0-0
            if m["state"] != "in":
                continue
            if m["minute"] is None:
                continue
            if not (MIN_ENTRY_MINUTE <= m["minute"] <= MAX_ENTRY_MINUTE):
                continue
            if not (m["home_score"] == 0 and m["away_score"] == 0):
                continue

            # 3. LAYAK ENTRY - Kasih odds MANUAL, TANPA API
            odds_info = get_odds_with_fallback(m["home"], m["away"], m["league"])
            # odds_info = {"odds": 1.72, "source": "Est - Global", "type": "Est"}

            rec = {
                "match_id": mid,
                "home_team": m["home"],
                "away_team": m["away"],
                "home": m["home"],
                "away": m["away"],
                "league": m["league"] if m["league"] else "Unknown League",
                "league_code": league_code,
                "badge": "NORMAL",
                "activity": "NORMAL",
                "min_entry": f"{m['minute']}'",
                "entry_minute": m["minute"],
                "entry_score": "0-0",
                "current_score": "0-0",
                "score": "0-0",
                "final_score": "",
                # ODDS MANUAL - TIDAK PERNAH Actual / Sim / 1.80
                "odds_entry": odds_info["odds"],
                "odds": odds_info["odds"],
                "odds_source": odds_info["source"],
                "odds_entry_type": odds_info["type"],  # Selalu "Est"
                "stake": DEFAULT_STAKE,
                "result": "LIVE",
                "settlement_status": "PENDING",
                "profit": 0,
                "pnl": 0,
                "p_l": 0,
                "trading_day": _today_str(),
                "created_at": datetime.now(WIB).isoformat(),
            }
            records.append(rec)
            by_id[mid] = rec
            new_entry += 1
            print(f"  [ENTRY] {m['home']} vs {m['away']} | {m['league']} | Menit {m['minute']}' | 0-0 | Odds {odds_info['odds']} ({odds_info['source']})")

    # Simpan archive hari ini
    _save_today_records(records, fpath)
    print(f" -> Disimpan {fpath}: {len(records)} record")

    # Simpan juga latest.json buat dashboard Tab B baca
    # Dashboard baca file ini, jadi harus sama isinya
    try:
        with open(os.path.join(DATA_DIR, "latest.json"), "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        # Simpan juga all.json buat rekap
        with open(os.path.join(DATA_DIR, "trades.json"), "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  [save latest] gagal: {e}")

    print(f"=== SELESAI ===")
    print(f"Entry baru: {new_entry} | Settled baru: {settled} | Total hari ini: {len(records)}")
    print(f"Semua odds baru: Est manual, tanpa API.")

if __name__ == "__main__":
    main()
