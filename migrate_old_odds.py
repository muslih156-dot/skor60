"""
migrate_old_odds.py - SATU KALI JALAN SAJA - V5 MANUAL TANPA API
Benerin semua yang salah kemarin:
- 1.80 (Sim) -> Est bener
- 2.53 (Unknown League salah) -> Est Global 1.71
- 1.25 (Global rumus lama salah) -> Est Global 1.71
- Yang Actual dari API -> diubah juga jadi Est manual, karena kita udah lupakan API

Jalankan: python migrate_old_odds.py
"""

import json
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odds_provider import get_odds_with_fallback

def _safe_float(val, default=0.0):
    try:
        if val is None or val == "":
            return default
        return float(val)
    except:
        return default

def recalc_profit(rec, new_odds):
    try:
        stake = _safe_float(rec.get("stake", rec.get("bet_stake", rec.get("amount", 10))), 10)
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
        print(f"  [profit] gagal hitung ulang: {e}")
    return rec

def main():
    files = glob.glob("data/*.json") + glob.glob("data/**/*.json", recursive=True)
    files = [f for f in files if "scan" not in f.lower() and "metadata" not in f.lower() and "health" not in f.lower()]
    
    print(f"Ketemu {len(files)} file data: {files}")

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
                print(f"Skip {fpath}: format dict tidak dikenal")
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

            # Kalau udah di-fix V5 manual, skip
            if rec.get("odds_migrated_v5_manual") is True:
                total_skipped += 1
                continue

            # [V5] Semua yang BUKAN Est manual yang bener harus dibenerin:
            # - Sim / 1.80 / kosong / 0
            # - 1.25 (rumus lama salah)
            # - 2.53 Unknown League
            # - Actual dari API (kita udah lupakan API, jadi ubah ke Est manual)
            is_wrong = (
                odds_type == "sim" or
                odds_type == "actual" or
                "actual" in odds_source or
                odds_source == "sim" or
                odds_source == "" or
                odds_val == 0 or
                odds_val == 1.80 or
                odds_val == 1.25 or
                odds_val == 2.53 or
                "unknown league" in odds_source
            )

            if not is_wrong:
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
                rec["odds_migrated_from_sim"] = True
                rec["odds_migrated_old_value"] = old_odds
                rec["odds_migrated_v5_manual"] = True

                rec = recalc_profit(rec, new_odds_info["odds"])

                total_migrated += 1
                changed_in_file += 1
                print(f"  [OK] {home} vs {away} | {league} | {old_odds} -> {new_odds_info['odds']} ({new_odds_info['source']})")
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
            print(f" -> Disimpan {fpath}: {changed_in_file} record diubah")

    print("\n=== SELESAI MIGRASI V5 MANUAL ===")
    print(f"Total dicek: {total_checked}")
    print(f"Total dimigrasi / dibenerin: {total_migrated}")
    print(f"Total di-skip (udah Est manual bener): {total_skipped}")
    print("Sekarang semua MANUAL, nggak ada lagi API / Actual / 401.")

if __name__ == "__main__":
    main()
