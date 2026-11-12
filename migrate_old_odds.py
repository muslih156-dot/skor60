"""
migrate_old_odds.py - V6 FIX Dashboard masih Actual + Profit Rp0
1. Paksa semua (Actual) jadi (Est) manual
2. Benerin Profit Rp0 -> hitung ulang pake stake bener
"""

import json
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odds_provider import get_odds_with_fallback

# Coba ambil stake dari config, kalau gagal pake 10000 (Rp10rb)
try:
    from config import DEFAULT_STAKE
    FALLBACK_STAKE = float(DEFAULT_STAKE) if float(DEFAULT_STAKE) > 0 else 10000
except:
    FALLBACK_STAKE = 10000

def _safe_float(val, default=0.0):
    try:
        if val is None or val == "":
            return default
        return float(val)
    except:
        return default

def recalc_profit(rec, new_odds):
    try:
        # [FIX] Kalau stake 0 / kosong, pake FALLBACK_STAKE
        stake = _safe_float(rec.get("stake", rec.get("bet_stake", rec.get("amount", 0))), 0)
        if stake <= 0:
            stake = FALLBACK_STAKE
            rec["stake"] = stake
        result = str(rec.get("result", rec.get("outcome", rec.get("settlement_result", "")))).upper()
        status = str(rec.get("settlement_status", "")).upper()
        if status not in ("SETTLED", "SETTLED_WIN", "SETTLED_LOSE"):
            if "WIN" not in result and "LOSE" not in result and "VOID" not in result:
                return rec
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
        elif "VOID" in result or "REFUND" in result:
            rec["profit"] = 0
            rec["pnl"] = 0
            rec["p_l"] = 0
    except Exception as e:
        print(f"  [profit] gagal: {e}")
    return rec

def main():
    files = glob.glob("data/*.json") + glob.glob("data/**/*.json", recursive=True)
    files = [f for f in files if "scan" not in f.lower() and "metadata" not in f.lower() and "health" not in f.lower()]
    print(f"Ketemu {len(files)} file, FALLBACK_STAKE={FALLBACK_STAKE}")
    total_checked = 0
    total_migrated = 0
    total_skipped = 0
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Skip {fpath}: {e}")
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
        changed_in_file = 0
        for rec in records:
            if not isinstance(rec, dict):
                continue
            total_checked += 1
            odds_type = str(rec.get("odds_entry_type", "") or "").lower()
            odds_source = str(rec.get("odds_source", "") or "").lower()
            odds_val = _safe_float(rec.get("odds_entry", rec.get("odds", 0)), 0)
            profit_val = _safe_float(rec.get("profit", rec.get("pnl", 0)), 0)
            result = str(rec.get("result", "")).upper()

            # [FIX V6] Harus dibenerin kalau:
            # - Masih Actual (bot lama masih jalan)
            # - ATAU Profit Rp0 padahal udah WIN/LOSE
            is_actual = odds_type == "actual" or "actual" in odds_source
            is_profit_zero_but_settled = (profit_val == 0 and result in ("WIN", "LOSE"))
            # Kalau udah V6 dan profit udah bener, skip
            if rec.get("odds_migrated_v6_fixed") is True and not is_profit_zero_but_settled:
                total_skipped += 1
                continue
            if not is_actual and not is_profit_zero_but_settled:
                # Cek juga yang masih Sim / 1.80 / 1.25 / 2.53 lama
                is_old = odds_type == "sim" or odds_val in (0, 1.80, 1.25, 2.53)
                if not is_old:
                    total_skipped += 1
                    continue

            home = rec.get("home_team", "") or rec.get("home", "")
            away = rec.get("away_team", "") or rec.get("away", "")
            league = rec.get("league", "Unknown League") or "Unknown League"
            try:
                new_odds_info = get_odds_with_fallback(home, away, league)
                old_odds = odds_val
                rec["odds_entry"] = new_odds_info["odds"]
                rec["odds"] = new_odds_info["odds"]
                rec["odds_source"] = new_odds_info["source"]
                rec["odds_entry_type"] = new_odds_info["type"]
                rec["odds_migrated_v6_fixed"] = True
                rec = recalc_profit(rec, new_odds_info["odds"])
                total_migrated += 1
                changed_in_file += 1
                print(f"  [OK] {home} vs {away} | {old_odds} (Actual) -> {new_odds_info['odds']} ({new_odds_info['source']}) | Profit baru: {rec.get('profit')}")
            except Exception as e:
                print(f"  [GAGAL] {home} vs {away}: {e}")
        if changed_in_file > 0:
            if records_key:
                data[records_key] = records
                out_data = data
            else:
                out_data = records
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(out_data, f, indent=2, ensure_ascii=False)
            print(f" -> Disimpan {fpath}: {changed_in_file} diubah")
    print(f"\n=== SELESAI V6 ===\nDicek: {total_checked} | Dibenerin: {total_migrated} | Skip: {total_skipped}")

if __name__ == "__main__":
    main()
