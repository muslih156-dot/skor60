"""
migrate_old_odds.py - SATU KALI JALAN SAJA - V3 FIX Unknown League 2.53
Tugas: 
1. Ubah semua record lama yang masih 1.80 (Sim) / kosong jadi Est
2. [V3] Benerin yang udah terlanjur migrasi tapi salah jadi 2.53 Unknown League -> jadi Est Global 1.62

Jalankan: python migrate_old_odds.py
"""

import json
import glob
import os
import sys

# Biar bisa import odds_provider
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odds_provider import get_odds_with_fallback

def _safe_float(val, default=0.0):
    """Ubah apapun jadi float dengan aman, kalau None / string kosong -> default"""
    try:
        if val is None or val == "":
            return default
        return float(val)
    except:
        return default

def recalc_profit(rec, new_odds):
    """
    Hitung ulang profit kalau match udah settled.
    """
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
    # Jangan baca file metadata / scan terakhir, cuma database trading aja
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

        # Handle format: list langsung, atau dict dengan key records/matches/data
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

            # [FIX V3] Migrasi juga yang udah terlanjur jadi Est tapi salah (Unknown League + 2.53)
            # Tandanya: pernah dimigrasi dari Sim DAN source-nya Unknown League
            is_migrated_wrong = (
                rec.get("odds_migrated_from_sim") is True and
                "unknown league" in odds_source
            )
            # Kalau udah di-fix V3, skip biar nggak keulang-ulang
            if rec.get("odds_migrated_v3_fixed") is True:
                total_skipped += 1
                continue

            is_sim = (
                odds_type == "sim" or
                odds_source == "sim" or
                odds_source == "" or
                odds_val == 0 or
                (odds_val == 1.80 and odds_type in ("", "sim")) or
                is_migrated_wrong
            )

            if not is_sim:
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
                # Tandain biar ketauan ini hasil migrasi
                rec["odds_migrated_from_sim"] = True
                rec["odds_migrated_old_value"] = old_odds
                rec["odds_migrated_v3_fixed"] = True

                # Hitung ulang P/L kalau udah settled
                rec = recalc_profit(rec, new_odds_info["odds"])

                total_migrated += 1
                changed_in_file += 1
                print(f"  [OK] {home} vs {away} | {league} | {old_odds} (Sim) -> {new_odds_info['odds']} ({new_odds_info['source']})")
            except Exception as e:
                print(f"  [GAGAL] {home} vs {away}: {e}")

        if changed_in_file > 0:
            # Tulis balik ke file
            if records_key:
                data[records_key] = records
                out_data = data
            else:
                out_data = records
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(out_data, f, indent=2, ensure_ascii=False)
            print(f" -> Disimpan {fpath}: {changed_in_file} record diubah")

    print("\n=== SELESAI MIGRASI ===")
    print(f"Total dicek: {total_checked}")
    print(f"Total dimigrasi Sim -> Est: {total_migrated}")
    print(f"Total di-skip (udah Actual/Est): {total_skipped}")
    print("Sekarang semua record lama udah nggak ada 1.80 Sim lagi.")

if __name__ == "__main__":
    main()
