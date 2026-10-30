"""
check_once.py
Skrip eksekusi siklus tunggal untuk TRADING BOLA MENIT 60 – LAST GOAL SYSTEM.
Dijalankan oleh GitHub Actions setiap 5 menit atau melalui pemicu manual.
Tugas:
1. Memindai pertandingan live dari ESPN ALL dan ESPN MULTI LEAGUE.
2. Mendeteksi kandidat baru pada menit 60–66 dengan skor 0-0 (secara idempotent).
3. Memantau dan memperbarui status pertandingan yang masih PENDING / LIVE.
4. Melakukan validasi settlement akhir (WIN/LOSE/VOID/REVIEW) menggunakan scoreboard + summary detail.
5. Menyimpan metadata kesehatan sistem dan arsip JSON.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict

import requests

from config import DEFAULT_STAKE
from database import TradingDatabase, save_scan_metadata
from espn_client import fetch_live_match, fetch_match_detail, fetch_match_events
from parser import detect_candidate, format_iso_utc_and_wita
from settlement import audit_result, validate_final_result


def run_scan_cycle() -> Dict[str, Any]:
    """Menjalankan satu siklus penuh pemindaian, deteksi kandidat, dan settlement."""
    db = TradingDatabase()
    session = requests.Session()
    cycle_start = datetime.now(timezone.utc)
    cycle_utc_str, cycle_wita_str = format_iso_utc_and_wita(cycle_start)

    # 1. Ambil data scoreboard dari ESPN
    scan_res = fetch_live_match(session=session)
    scoreboard_map: Dict[str, Dict[str, Any]] = {}
    for parsed_match in scan_res["matches"]:
        m_id = parsed_match["score"]["match_id"]
        scoreboard_map[m_id] = parsed_match

    new_candidates_count = 0
    existing_candidates_skipped = 0
    live_matches_seen = 0

    # 2. Evaluasi setiap pertandingan yang berhasil diparsing untuk deteksi kandidat
    for parsed_match in scan_res["matches"]:
        if parsed_match["status"].get("is_live", False):
            live_matches_seen += 1

        cand_eval = detect_candidate(parsed_match)
        if cand_eval["is_candidate"]:
            _, created = db.insert_candidate_idempotent(
                parsed_match=parsed_match,
                detected_dt_utc=cycle_start,
                stake=DEFAULT_STAKE,
            )
            if created:
                new_candidates_count += 1
            else:
                existing_candidates_skipped += 1

    # 3. Pembaruan & Settlement untuk seluruh pertandingan yang masih PENDING / REVIEW
    pending_records = db.get_pending_matches()
    updated_count = 0
    settled_this_cycle = 0
    review_flagged_count = 0

    for rec in pending_records:
        match_id = rec["match_id"]
        league_slug = rec.get("league_slug") or "all"
        sb_match = scoreboard_map.get(match_id)

        # Ambil detail pertandingan apabila:
        # a) Pertandingan sudah tidak muncul di scoreboard, ATAU
        # b) Scoreboard menunjukkan pertandingan sudah selesai / void / ada perubahan skor
        detail_match = None
        events_list = None
        need_detail = (
            sb_match is None
            or sb_match["status"].get("is_final", False)
            or sb_match["status"].get("is_void_candidate", False)
            or sb_match["score"].get("formatted_score") != rec.get("current_score")
        )

        if need_detail and not str(match_id).startswith("PROVISIONAL_"):
            detail_res = fetch_match_detail(match_id, league_slug=league_slug, session=session)
            if detail_res["ok"] and detail_res["parsed"]:
                detail_match = detail_res["parsed"]
                events_list = fetch_match_events(
                    match_id=match_id,
                    league_slug=league_slug,
                    summary_payload=detail_res["raw_summary"],
                    session=session,
                )

        updated_rec = validate_final_result(
            existing_record=rec,
            scoreboard_match=sb_match,
            detail_match=detail_match,
            events_list=events_list,
            now_utc=datetime.now(timezone.utc),
        )

        audit_info = audit_result(updated_rec)
        updated_rec["audit_explanation"] = audit_info["explanation"]
        updated_rec["audit_passed"] = audit_info["audit_passed"]

        db.update_existing_record(updated_rec)
        updated_count += 1

        if updated_rec["settlement_status"] in ("SETTLED", "VOID"):
            settled_this_cycle += 1
        elif updated_rec["settlement_status"] == "REVIEW":
            review_flagged_count += 1

    # 4. Simpan metadata scan terakhir
    meta_summary = {
        "scan_timestamp_utc": cycle_utc_str,
        "scan_timestamp_wita": cycle_wita_str,
        "source_status": scan_res["source_status"],
        "endpoints_queried": scan_res["endpoints_queried"],
        "endpoints_succeeded": scan_res["endpoints_succeeded"],
        "endpoints_failed": scan_res["endpoints_failed"],
        "raw_events_received": scan_res["raw_events_received"],
        "unique_events_count": scan_res["unique_events_count"],
        "matches_processed": scan_res["matches_processed"],
        "matches_failed_parsing": scan_res["matches_failed_parsing"],
        "live_matches_seen": live_matches_seen,
        "new_candidates_detected": new_candidates_count,
        "existing_candidates_skipped": existing_candidates_skipped,
        "pending_matches_checked": len(pending_records),
        "matches_settled_this_cycle": settled_this_cycle,
        "matches_flagged_review": review_flagged_count,
        "endpoint_logs": scan_res["endpoint_logs"],
    }
    save_scan_metadata(meta_summary)
    return meta_summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run single scan & settlement cycle for TRADING BOLA MENIT 60."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print cycle summary in JSON format.",
    )
    args = parser.parse_args()

    summary = run_scan_cycle()
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(
            f"[{summary['scan_timestamp_wita']}] Status={summary['source_status']} | "
            f"Processed={summary['matches_processed']} | Live={summary['live_matches_seen']} | "
            f"NewCandidates={summary['new_candidates_detected']} | "
            f"Settled={summary['matches_settled_this_cycle']}"
        )

    # Jika seluruh endpoint gagal total, kembalikan kode keluar non-zero untuk visibilitas log
    if summary["source_status"] == "CRITICAL_ALL_ENDPOINTS_FAILED":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())