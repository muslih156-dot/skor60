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
                    records = data.get("records", []) or data.get("matches", []) or list(data.values())
                for rec in records:
                    if not isinstance(rec, dict):
                        continue
                    # [FIX] Cuma hitung yang udah SETTLED / final, jangan yang PENDING 0-0
                    status = str(rec.get("settlement_status", "")).upper()
                    if status not in ("SETTLED", "SETTLED_WIN", "SETTLED_LOSE", "VOID"):
                        continue
                    rec_league = str(rec.get("league", "")).lower()
                    if rec_league != league_key:
                        continue
                    score_str = str(rec.get("final_score", "") or rec.get("score", ""))
                    # [FIX] Harus ada final_score yang bener, bukan 0-0 entry
                    if "-" not in score_str:
                        continue
                    try:
                        a, b = score_str.replace(" ", "").split("-")[:2]
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
