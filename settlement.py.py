"""
settlement.py
Modul validasi hasil akhir (WIN / LOSE / VOID / PENDING / REVIEW),
perhitungan profit aktual vs simulasi, pencatatan snapshot skor,
deteksi koreksi skor provider, dan audit trail.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config import DEFAULT_STAKE, SIMULATED_ODDS
from parser import format_iso_utc_and_wita


def calculate_profit(
    result: str,
    stake: int = DEFAULT_STAKE,
    odds_entry: Optional[float] = None,
    simulated_odds: float = SIMULATED_ODDS,
) -> Dict[str, Any]:
    """
    Menghitung profit bersih (Net Profit) dan kontribusi ROI menggunakan decimal odds.
    Memisahkan perhitungan SIMULATED PERFORMANCE (odds 1.80) dan ACTUAL ODDS PERFORMANCE.
    Rumus:
      WIN  -> Net Profit = Stake * (Odds - 1)
      LOSE -> Net Profit = -Stake
      VOID -> Net Profit = 0
      PENDING / DATA UNVERIFIED -> Net Profit = 0 (belum disettle)
    """
    norm_res = (result or "PENDING").strip().upper()
    has_actual_odds = (
        odds_entry is not None
        and isinstance(odds_entry, (int, float))
        and float(odds_entry) > 1.0
    )

    # 1. Perhitungan Simulasi (menggunakan simulated_odds = 1.80)
    if norm_res == "WIN":
        sim_profit = int(round(stake * (simulated_odds - 1.0)))
        sim_roi = round(((simulated_odds - 1.0) * 100.0), 2)
    elif norm_res == "LOSE":
        sim_profit = -int(stake)
        sim_roi = -100.0
    elif norm_res == "VOID":
        sim_profit = 0
        sim_roi = 0.0
    else:
        sim_profit = 0
        sim_roi = 0.0

    # 2. Perhitungan Aktual (hanya jika odds_entry aktual benar-benar tercatat saat entry)
    actual_profit: Optional[int] = None
    actual_roi: Optional[float] = None
    if has_actual_odds:
        act_odds = float(odds_entry)
        if norm_res == "WIN":
            actual_profit = int(round(stake * (act_odds - 1.0)))
            actual_roi = round(((act_odds - 1.0) * 100.0), 2)
        elif norm_res == "LOSE":
            actual_profit = -int(stake)
            actual_roi = -100.0
        elif norm_res == "VOID":
            actual_profit = 0
            actual_roi = 0.0
        else:
            actual_profit = 0
            actual_roi = 0.0

    return {
        "stake": int(stake),
        "simulated_odds": float(simulated_odds),
        "simulated_profit": sim_profit,
        "simulated_roi_contribution": sim_roi,
        "has_actual_odds": has_actual_odds,
        "actual_odds": float(odds_entry) if has_actual_odds else None,
        "actual_profit": actual_profit,
        "actual_roi_contribution": actual_roi,
        # Field `profit` dan `roi_contribution` utama mengikuti simulasi dengan label eksplisit
        # jika actual_odds tidak tersedia, atau actual_profit jika tersedia.
        "profit": actual_profit if has_actual_odds else sim_profit,
        "roi_contribution": actual_roi if has_actual_odds else sim_roi,
    }


def _determine_regulation_score(
    parsed_match: Dict[str, Any],
    events_list: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[int], Optional[int], bool]:
    """
    Menentukan skor akhir pada waktu normal (90 menit + injury time, tanpa Extra Time / Penalties).
    Mengembalikan: (home_score, away_score, is_verified_regulation).
    """
    status = parsed_match.get("status") or {}
    score = parsed_match.get("score") or {}

    if not score.get("score_valid", False):
        return None, None, False

    ended_in_aet_or_pen = status.get("ended_in_extra_time_or_pen", False)
    if not ended_in_aet_or_pen:
        return score.get("home_score"), score.get("away_score"), True

    # Jika pertandingan berakhir di Extra Time / Penalties, cek linescores babak 1 + 2
    reg_home = score.get("regulation_home_score")
    reg_away = score.get("regulation_away_score")
    if reg_home is not None and reg_away is not None:
        return reg_home, reg_away, True

    return None, None, False


def validate_final_result(
    existing_record: Dict[str, Any],
    scoreboard_match: Optional[Dict[str, Any]] = None,
    detail_match: Optional[Dict[str, Any]] = None,
    events_list: Optional[List[Dict[str, Any]]] = None,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Memvalidasi perkembangan skor dan menentukan settlement pertandingan secara ketat:
    - Tidak menggunakan minute >= 90, umur pertandingan > 120 menit, hilangnya pertandingan
      dari scoreboard, atau error API sebagai bukti final.
    - Memeriksa konflik antara scoreboard dan match detail. Jika bertentangan, tandai REVIEW
      dan DATA UNVERIFIED.
    - Mencatat snapshot skor dan event gol (atau perubahan skor dengan penanda
      GOAL EVENT TIME APPROXIMATE jika event gol resmi tidak tersedia).
    - Jika skor akhir resmi berubah akibat koreksi provider setelah SETTLED, catat ke
      revision_history tanpa menghapus histori lama.
    """
    now_dt = now_utc or datetime.now(timezone.utc)
    now_utc_str, now_wita_str = format_iso_utc_and_wita(now_dt)

    record = dict(existing_record)
    snapshots: List[Dict[str, Any]] = list(record.get("snapshots") or [])
    goal_events: List[Dict[str, Any]] = list(record.get("goal_events") or [])
    revision_history: List[Dict[str, Any]] = list(record.get("revision_history") or [])

    # 1. Jika baik scoreboard maupun detail tidak tersedia (misal API gagal / hilang dari scoreboard)
    if scoreboard_match is None and detail_match is None:
        # Jangan pernah menganggap selesai hanya karena hilang dari scoreboard atau API gagal
        if record.get("settlement_status") not in ("SETTLED", "VOID"):
            record["settlement_status"] = "PENDING"
            if record.get("result") not in ("WIN", "LOSE", "VOID"):
                record["result"] = "PENDING"
        record["updated_at"] = now_utc_str
        return record

    # 2. Deteksi konflik data antara scoreboard dan match detail
    if scoreboard_match is not None and detail_match is not None:
        sb_score = (scoreboard_match.get("score") or {}).get("formatted_score")
        dt_score = (detail_match.get("score") or {}).get("formatted_score")
        sb_status = (scoreboard_match.get("status") or {}).get("canonical_status")
        dt_status = (detail_match.get("status") or {}).get("canonical_status")

        # Konflik kritis jika keduanya mengklaim skor berbeda atau salah satu Final tapi skor beda
        if (
            sb_score
            and dt_score
            and sb_score != dt_score
            and (sb_status == "Final" or dt_status == "Final")
        ):
            revision_history.append({
                "timestamp_utc": now_utc_str,
                "reason": "CONFLICT_SCOREBOARD_VS_DETAIL",
                "scoreboard_status": sb_status,
                "scoreboard_score": sb_score,
                "detail_status": dt_status,
                "detail_score": dt_score,
                "previous_result": record.get("result"),
            })
            record["settlement_status"] = "REVIEW"
            record["result"] = "DATA UNVERIFIED"
            record["verification_status"] = "CONFLICT_DETECTED"
            record["revision_history"] = revision_history
            record["updated_at"] = now_utc_str
            return record

    # Pilih sumber observasi paling lengkap (prioritaskan detail_match jika valid, lalu scoreboard_match)
    active_obs = detail_match if (detail_match and detail_match.get("score", {}).get("score_valid")) else scoreboard_match
    if not active_obs or not active_obs.get("score", {}).get("score_valid"):
        return record

    status_info = active_obs["status"]
    clock_info = active_obs["clock"]
    score_info = active_obs["score"]

    new_score_str = score_info["formatted_score"]
    old_score_str = record.get("current_score") or record.get("score_at_entry") or "0-0"
    obs_minute = clock_info.get("minute")
    obs_clock_disp = clock_info.get("display_clock") or (f"{obs_minute}'" if obs_minute is not None else status_info["canonical_status"])

    # 3. Simpan snapshot jika skor berubah atau status berubah
    last_snap = snapshots[-1] if snapshots else None
    should_add_snapshot = (
        last_snap is None
        or last_snap.get("score") != new_score_str
        or last_snap.get("match_status") != status_info["canonical_status"]
    )

    if should_add_snapshot:
        note = "STATUS UPDATE"
        if new_score_str != old_score_str:
            note = "GOAL DETECTED"
        elif status_info["is_final"]:
            note = "MATCH FINISHED"
        snapshots.append({
            "timestamp_utc": now_utc_str,
            "timestamp_wita": now_wita_str,
            "clock": obs_clock_disp,
            "minute": obs_minute,
            "score": new_score_str,
            "match_status": status_info["canonical_status"],
            "note": note,
        })

    # 4. Perbarui daftar event gol
    incoming_events = events_list if events_list is not None else active_obs.get("goal_events", [])
    if incoming_events:
        goal_events = incoming_events
    elif new_score_str != old_score_str and not status_info.get("is_extra_time_or_pen", False):
        # Ketika API tidak menyediakan event gol resmi, gunakan perubahan skor antar-snapshot
        # dan tandai GOAL EVENT TIME APPROXIMATE (jangan mengarang menit gol).
        approx_Already_logged = any(
            g.get("score_after") == new_score_str and g.get("time_approximate")
            for g in goal_events
        )
        if not approx_Already_logged:
            goal_events.append({
                "observed_at_utc": now_utc_str,
                "observed_at_wita": now_wita_str,
                "minute": obs_minute,
                "clock_display": obs_clock_disp,
                "previous_score": old_score_str,
                "score_after": new_score_str,
                "team": "UNKNOWN_FROM_SNAPSHOT_DIFF",
                "time_approximate": True,
                "note": "GOAL EVENT TIME APPROXIMATE",
                "source": "SCORE_SNAPSHOT_DIFFERENCE",
            })

    record["current_score"] = new_score_str
    record["match_status"] = status_info["canonical_status"]
    record["snapshots"] = snapshots
    record["goal_events"] = goal_events
    record["updated_at"] = now_utc_str

    # 5. Evaluasi Status Settlement
    # A. Jika pertandingan berada di Extra Time atau Penalties (belum Final atau sedang jalan)
    if status_info.get("is_extra_time_or_pen", False) and not status_info.get("is_final", False):
        # Waktu normal (90') sudah lewat. Jika pada akhir waktu normal skor diketahui 0-0
        # atau sudah ada gol di waktu normal, kita tetap tunggu status resmi atau linescore waktu normal.
        reg_h, reg_a, reg_ok = _determine_regulation_score(active_obs, goal_events)
        if reg_ok and reg_h is not None and reg_a is not None:
            record["final_score"] = f"{reg_h}-{reg_a}"
            new_result = "WIN" if (reg_h + reg_a) >= 1 else "LOSE"
            record["result"] = new_result
            record["settlement_status"] = "SETTLED"
            record["verification_status"] = "VERIFIED_REGULATION_LINESCORE"
            record["last_verified_at"] = now_utc_str
        else:
            record["settlement_status"] = "PENDING"
            record["result"] = "PENDING"
            record["verification_status"] = "AWAITING_REGULATION_CONFIRMATION"

    # B. Jika pertandingan Abandoned, Postponed, Cancelled, atau Suspended
    elif status_info.get("is_void_candidate", False):
        prev_result = record.get("result")
        if prev_result in ("WIN", "LOSE") and prev_result != "VOID":
            revision_history.append({
                "timestamp_utc": now_utc_str,
                "reason": f"MATCH_STATUS_CHANGED_TO_{status_info['canonical_status'].upper()}",
                "old_result": prev_result,
                "new_result": "VOID",
                "old_profit": record.get("profit"),
            })
        record["settlement_status"] = "VOID"
        record["result"] = "VOID"
        record["verification_status"] = f"VOID_{status_info['canonical_status'].upper()}"
        record["last_verified_at"] = now_utc_str

    # C. Jika pertandingan berstatus FINAL resmi dari provider
    elif status_info.get("is_final", False):
        reg_h, reg_a, reg_ok = _determine_regulation_score(active_obs, goal_events)
        if not reg_ok or reg_h is None or reg_a is None:
            record["settlement_status"] = "REVIEW"
            record["result"] = "DATA UNVERIFIED"
            record["verification_status"] = "UNVERIFIED_AET_REGULATION_SCORE"
        else:
            official_final_score = f"{reg_h}-{reg_a}"
            total_goals = reg_h + reg_a
            # Karena skor saat entry wajib 0-0, total_goals >= 1 berarti minimal 1 gol tercipta setelah entry
            new_result = "WIN" if total_goals >= 1 else "LOSE"

            # Cek apakah terjadi koreksi hasil resmi setelah sebelumnya sudah SETTLED
            prev_settlement = record.get("settlement_status")
            prev_final_score = record.get("final_score")
            prev_result = record.get("result")
            if (
                prev_settlement == "SETTLED"
                and (prev_final_score is not None and prev_final_score != official_final_score or prev_result != new_result)
            ):
                revision_history.append({
                    "timestamp_utc": now_utc_str,
                    "reason": "PROVIDER_OFFICIAL_SCORE_CORRECTION",
                    "old_final_score": prev_final_score,
                    "new_final_score": official_final_score,
                    "old_result": prev_result,
                    "new_result": new_result,
                    "old_profit": record.get("profit"),
                    "old_simulated_profit": record.get("simulated_profit"),
                })

            record["final_score"] = official_final_score
            record["result"] = new_result
            record["settlement_status"] = "SETTLED"
            record["verification_status"] = "VERIFIED_OFFICIAL_FINAL"
            record["last_verified_at"] = now_utc_str

    # D. Jika status belum FINAL resmi (walaupun menit >= 90), wajib tetap PENDING
    else:
        record["settlement_status"] = "PENDING"
        record["result"] = "PENDING"
        record["verification_status"] = "IN_PROGRESS_PENDING_FINAL"

    # 6. Hitung ulang profit dan ROI berdasarkan hasil tervalidasi
    profit_info = calculate_profit(
        result=record["result"],
        stake=int(record.get("stake") or DEFAULT_STAKE),
        odds_entry=record.get("odds_entry"),
        simulated_odds=float(record.get("simulated_odds") or SIMULATED_ODDS),
    )
    record["profit"] = profit_info["profit"]
    record["roi_contribution"] = profit_info["roi_contribution"]
    record["simulated_profit"] = profit_info["simulated_profit"]
    record["simulated_roi_contribution"] = profit_info["simulated_roi_contribution"]
    record["actual_profit"] = profit_info["actual_profit"]
    record["actual_roi_contribution"] = profit_info["actual_roi_contribution"]
    record["revision_history"] = revision_history

    return record


def audit_result(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Melakukan verifikasi integritas pada satu record pertandingan dan menghasilkan
    penjelasan audit yang transparan mengenai mengapa pertandingan dinyatakan
    WIN, LOSE, VOID, PENDING, atau DATA UNVERIFIED.
    """
    issues: List[str] = []
    match_id = record.get("match_id", "UNKNOWN")
    entry_score = record.get("score_at_entry")
    entry_min = record.get("minute_detected")
    result = record.get("result")
    settlement_status = record.get("settlement_status")
    final_score = record.get("final_score")
    match_status = record.get("match_status")

    if entry_score != "0-0":
        issues.append(f"Invalid entry score '{entry_score}' (expected '0-0').")
    if entry_min is None or not (60 <= int(entry_min) <= 66):
        issues.append(f"Entry minute '{entry_min}' outside valid window 60-66.")

    explanation = ""
    if result == "WIN":
        if match_status != "Final" and record.get("verification_status") != "VERIFIED_REGULATION_LINESCORE":
            issues.append("Result marked WIN without Final status or verified regulation linescore.")
        explanation = (
            f"Pertandingan {match_id} masuk pada menit {entry_min}' dengan skor {entry_score}. "
            f"Status resmi mencapai {match_status} dengan skor akhir waktu normal {final_score}. "
            f"Minimal 1 gol tercipta setelah waktu entry sehingga dinyatakan WIN."
        )
    elif result == "LOSE":
        if final_score != "0-0":
            issues.append(f"Result marked LOSE but final_score is '{final_score}'.")
        explanation = (
            f"Pertandingan {match_id} masuk pada menit {entry_min}' dengan skor {entry_score}. "
            f"Hingga status resmi {match_status}, skor akhir waktu normal tetap {final_score} "
            f"(tidak ada gol setelah entry) sehingga dinyatakan LOSE."
        )
    elif result == "VOID":
        explanation = (
            f"Pertandingan {match_id} berstatus {match_status} (dibatalkan/ditunda/dihentikan). "
            f"Taruhan dinyatakan VOID dengan pengembalian modal penuh (Profit Rp0)."
        )
    elif result == "DATA UNVERIFIED" or settlement_status == "REVIEW":
        explanation = (
            f"Pertandingan {match_id} ditandai REVIEW / DATA UNVERIFIED karena terdapat konflik data "
            f"antar-endpoint atau rincian skor waktu normal belum dapat diverifikasi."
        )
    else:
        explanation = (
            f"Pertandingan {match_id} masih berstatus {match_status} (Skor saat ini: {record.get('current_score')}). "
            f"Menunggu status Final resmi dari provider (PENDING)."
        )

    return {
        "match_id": match_id,
        "audit_passed": len(issues) == 0,
        "issues": issues,
        "explanation": explanation,
        "revision_count": len(record.get("revision_history") or []),
    }