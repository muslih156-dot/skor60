"""
migrate_old_odds.py - V7 FIX Dashboard Live masih Actual + Profit Rp0
- Target SEMUA file termasuk file live dashboard (data/*.json root)
- Profit dihitung dari kolom Result (WIN/LOSE), bukan dari settlement_status
- Paksa Actual -> Est manual
"""

import json
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odds_provider import get_odds_with_fallback

FALLBACK_STAKE = 50000  # Stake bapak Rp50.000, sesuai log V6 kemarin

def _safe_float(val, default=0.0):
    try:
        if val is None or val == "":
            return default
        return float(val)
    except:
        return default

def recalc_profit_v7(rec, new_odds):
    # [FIX V7] Hitung dari Result, jangan dari settlement_status
    # Karena di file live, settlement_status masih PENDING tapi Result udah WIN
    try:
        stake = _safe_float(rec.get("stake", rec.get("bet_stake", rec.get("amount", 0))), 0)
        if stake <= 0:
            stake = FALLBACK_STAKE
            rec["stake"] = stake
        result = str(rec.get("result", rec.get("outcome", ""))).upper()
        if "WIN" in result:
            profit = round(stake * (new_odds - 1), 2)
            rec["profit"] = profit
            rec["pnl"] = profit
            rec["p_l"] = profit
        elif "LOSE" in result:
            profit = round(-stake, 2)
            rec["profit"] = profit
            rec["pnl"] = profit
            rec["p_l"] = profit
        elif "VOID" in result or "REFUND" in result or "DRAW" in result:
            rec["profit"] = 0
            rec["pnl"] = 0
            rec["p_l"] = 0
    except Exception as e:
        print(f"  [profit] gagal: {e}")
    return rec

def main():
    # [FIX] Ambil SEMUA file, termasuk file root data/ yang dibaca dashboard
    files = glob.glob("data/*.json") + glob.glob("data/**/*.json", recursive=True)
    files = [f for f in files if "scan" not in f.lower() and "metadata" not in f.lower() and "health" not in f.lower()]
    print(f"Ketemu {len(files)} file: {files}")
    total_checked = 0
    total_migrated = 0
    total_skipped = 0
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            continue
        records = None
        records_key = None
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            for k in ["records", "matches", "data", "trades"]:
                if k in data and isinstance(data[k], list):
                    records = data[k]
                    records_key = k
                    break
            if records is None:
                continue
        else:
            continue
        changed = 0
        for rec in records:
            if not isinstance(rec, dict):
                continue
            total_checked += 1
            odds_type = str(rec.get("odds_entry_type", "") or "").lower()
            odds_source = str(rec.get("odds_source", "") or "").lower()
            odds_val = _safe_float(rec.get("odds_entry", rec.get("odds", 0)), 0)
            profit_val = _safe_float(rec.get("profit", rec.get("pnl", 0)), 0)
            result = str(rec.get("result", "")).upper()

            # Harus dibenerin kalau masih Actual ATAU Profit 0 padahal udah WIN/LOSE
            is_actual = odds_type == "actual" or "actual" in odds_source
            is_profit_zero = (profit_val == 0 and result in ("WIN", "LOSE"))
            is_old = odds_type == "sim" or odds_val in (0, 1.80, 1.25, 2.53)
            if not (is_actual or is_profit_zero or is_old):
                total_skipped += 1
                continue
            # Kalau udah V7 dan udah bener, skip biar nggak keulang
            if rec.get("odds_migrated_v7_fixed") is True and not is_profit_zero:
                total_skipped += 1
                continue

            home = rec.get("home_team", "") or rec.get("home", "")
            away = rec.get("away_team", "") or rec.get("away", "")
            league = rec.get("league", "Unknown League") or "Unknown League"
            try:
                info = get_odds_with_fallback(home, away, league)
                old = odds_val
                rec["odds_entry"] = info["odds"]
                rec["odds"] = info["odds"]
                rec["odds_source"] = info["source"]
                rec["odds_entry_type"] = info["type"]
                rec["odds_migrated_v7_fixed"] = True
                rec = recalc_profit_v7(rec, info["odds"])
                total_migrated += 1
                changed += 1
                print(f"  [OK] {home} vs {away} | {old} -> {info['odds']} ({info['source']}) | Profit: {rec.get('profit')} | Result: {result}")
            except Exception as e:
                print(f"  [GAGAL] {home} vs {away}: {e}")
        if changed > 0:
            if records_key:
                data[records_key] = records
                out_data = data
            else:
                out_data = records
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(out_data, f, indent=2, ensure_ascii=False)
            print(f" -> Disimpan {fpath}: {changed} diubah")
    print(f"\n=== SELESAI V7 ===\nDicek: {total_checked} | Dibenerin: {total_migrated} | Skip: {total_skipped}")

if __name__ == "__main__":
    main()
