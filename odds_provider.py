"""
odds_provider.py - V5 FINAL - MANUAL SEMUA, TANPA ODDS API
Lupakan The Odds API. Semua odds dihitung manual dari history kita sendiri.

Rumus:
- Kita entry menit 60, sisa waktu ~32 menit (30 + injury)
- lam_sisa = lam_full * (32 / 90) = lam_full * 0.355
- P(Over 0.5) = 1 - exp(-lam_sisa)
- Odds = 1 / P

Contoh:
lam_full 2.45 (Global) -> lam_sisa 0.87 -> P 58% -> Odds 1.71
lam_full 2.80 (Liga gol banyak) -> lam_sisa 0.99 -> P 63% -> Odds 1.59
lam_full 1.80 (Liga gol dikit) -> lam_sisa 0.64 -> P 47% -> Odds 2.12
"""

import json
import glob
import math

def _get_lambda_to_odds_over05(lam):
    """
    lam = rata-rata total gol per match full 90 menit di liga itu
    Output = odds Over 0.5 untuk sisa 30 menit (menit 60 ke atas)
    """
    try:
        lam = float(lam)
        if lam <= 0:
            lam = 2.45
        # Sisa waktu menit 60 -> 90+ = ~32 menit
        lam_remaining = lam * 0.355
        p_over = 1 - math.exp(-lam_remaining)
        if p_over <= 0.10:
            p_over = 0.10
        if p_over >= 0.90:
            p_over = 0.90
        odds = 1 / p_over
        # Batas wajar Over 0.5 After 60': 1.35 - 2.20
        odds = max(1.35, min(2.20, odds))
        return round(odds, 2)
    except:
        return 1.71

def _estimate_lambda_from_league_history(league_name):
    """
    Hitung lam dari database kita sendiri.
    Cuma hitung match yang UDAH SETTLED + ada final_score.
    Jangan hitung yang masih PENDING 0-0, nanti lam-nya kekecilan.
    Kalau liga Unknown, langsung return None -> ke Global.
    """
    try:
        league_key = str(league_name or "").lower().strip()
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
                    status = str(rec.get("settlement_status", "")).upper()
                    if status not in ("SETTLED", "SETTLED_WIN", "SETTLED_LOSE", "VOID"):
                        continue
                    rec_league = str(rec.get("league", "")).lower().strip()
                    if rec_league != league_key:
                        continue
                    score_str = str(rec.get("final_score", "") or rec.get("current_score", "") or rec.get("score", ""))
                    if "-" not in score_str:
                        continue
                    try:
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

def get_odds_with_fallback(home_team, away_team, league_name):
    """
    FUNGSI UTAMA - DIPAKAI check_once.py DAN migrate_old_odds.py
    MANUAL 100%, TIDAK PERNAH KE API, TIDAK PERNAH return None.

    Urutan:
        1. Est dari History Liga (kalau liga dikenal + minimal 5 match SETTLED)
        2. Est Global (lam = 2.45 -> odds 1.71)
    """
    # 1. Coba Est dari Liga
    lam, count = _estimate_lambda_from_league_history(league_name)
    if lam is not None and count >= 5:
        odds = _get_lambda_to_odds_over05(lam)
        return {
            "odds": odds,
            "source": f"Est - Liga {league_name} ({count} match, lam={lam:.1f})",
            "type": "Est"
        }

    # 2. Fallback Global - lam rata-rata dunia 2.45
    odds_global = _get_lambda_to_odds_over05(2.45)
    return {
        "odds": odds_global,
        "source": "Est - Global",
        "type": "Est"
    }
