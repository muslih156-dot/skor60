"""
statistics.py
Modul analisis kuantitatif dan evaluasi kualitas strategi untuk
TRADING BOLA MENIT 60 – LAST GOAL SYSTEM.
Memisahkan secara ketat SIMULATED PERFORMANCE (odds 1.80) dan ACTUAL ODDS PERFORMANCE,
menghitung ROI, Break-Even WR, Wilson Confidence Interval (95%), Expected Value (EV),
Maximum Drawdown, Profit Factor, Winning/Losing Streak, dan performa per klasifikasi liga.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from config import (
    DEFAULT_STAKE,
    MIN_SAMPLE_SIZE_RELIABLE,
    SIMULATED_ODDS,
    WILSON_Z_SCORE_95,
)


def wilson_confidence_interval(
    wins: int,
    settled_total: int,
    z: float = WILSON_Z_SCORE_95,
) -> Tuple[float, float]:
    """
    Menghitung 95% Confidence Interval Wilson untuk Win Rate (dalam persentase 0-100).
    """
    if settled_total <= 0:
        return 0.0, 0.0
    n = float(settled_total)
    p = float(wins) / n
    z2 = z * z
    denom = 1.0 + (z2 / n)
    center = (p + (z2 / (2.0 * n))) / denom
    spread = (z * math.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))) / denom
    lower = max(0.0, (center - spread) * 100.0)
    upper = min(100.0, (center + spread) * 100.0)
    return round(lower, 2), round(upper, 2)


def calculate_streaks_and_drawdown(
    settled_records_chronological: List[Dict[str, Any]],
    profit_key: str = "simulated_profit",
) -> Dict[str, Any]:
    """
    Menghitung Longest Winning Streak, Longest Losing Streak, Maximum Drawdown (IDR),
    dan Profit Factor berdasarkan urutan kronologis pertandingan yang telah selesai (WIN/LOSE).
    """
    max_win_streak = 0
    max_lose_streak = 0
    cur_win_streak = 0
    cur_lose_streak = 0

    cumulative_profit = 0
    peak_profit = 0
    max_drawdown = 0
    gross_profit = 0
    gross_loss = 0

    for rec in settled_records_chronological:
        res = str(rec.get("result") or "").upper()
        pnl = int(rec.get(profit_key) or 0)

        if res == "WIN":
            cur_win_streak += 1
            cur_lose_streak = 0
            if cur_win_streak > max_win_streak:
                max_win_streak = cur_win_streak
            if pnl > 0:
                gross_profit += pnl
        elif res == "LOSE":
            cur_lose_streak += 1
            cur_win_streak = 0
            if cur_lose_streak > max_lose_streak:
                max_lose_streak = cur_lose_streak
            if pnl < 0:
                gross_loss += abs(pnl)
        else:
            continue

        cumulative_profit += pnl
        if cumulative_profit > peak_profit:
            peak_profit = cumulative_profit
        drawdown = peak_profit - cumulative_profit
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    if gross_loss > 0:
        profit_factor: Optional[float] = round(gross_profit / gross_loss, 2)
    elif gross_profit > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0

    return {
        "longest_winning_streak": max_win_streak,
        "longest_losing_streak": max_lose_streak,
        "max_drawdown": max_drawdown,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
    }


def compute_performance_block(
    records: List[Dict[str, Any]],
    mode: str = "SIMULATED",
) -> Dict[str, Any]:
    """
    Menghitung blok metrik performa untuk mode 'SIMULATED' (odds 1.80)
    atau 'ACTUAL' (hanya record dengan odds_entry aktual yang valid).
    PENTING: Pertandingan LIVE, PENDING, VOID, atau DATA UNVERIFIED
    tidak pernah dimasukkan ke denominator ROI maupun Win Rate.
    """
    is_actual = mode.upper() == "ACTUAL"
    if is_actual:
        eligible = [
            r for r in records
            if r.get("odds_entry") is not None and float(r.get("odds_entry") or 0) > 1.0
        ]
    else:
        eligible = list(records)

    total_matches = len(eligible)
    if is_actual and total_matches == 0:
        return {
            "mode": "ACTUAL",
            "available": False,
            "status_label": "ACTUAL ODDS: NOT AVAILABLE",
            "total_matches": 0,
            "settled_matches": 0,
            "win": 0,
            "lose": 0,
            "void": 0,
            "pending": 0,
            "unverified": 0,
            "win_rate": 0.0,
            "net_profit": 0,
            "total_stake_settled": 0,
            "roi": 0.0,
            "average_odds": None,
            "break_even_win_rate": None,
            "expected_value_per_match": None,
            "max_drawdown": 0,
            "longest_winning_streak": 0,
            "longest_losing_streak": 0,
            "profit_factor": 0.0,
            "wilson_ci_95": (0.0, 0.0),
            "sample_size_warning": "NO ACTUAL ODDS RECORDED",
        }

    # Urutkan kronologis dari terlama ke terbaru untuk perhitungan streak & drawdown
    chronological = sorted(
        eligible,
        key=lambda r: (str(r.get("detected_at_utc") or ""), str(r.get("match_id") or "")),
    )

    wins = 0
    losses = 0
    voids = 0
    pendings = 0
    unverified = 0

    total_stake_settled = 0
    net_profit = 0
    odds_sum = 0.0
    settled_chronological: List[Dict[str, Any]] = []

    profit_field = "actual_profit" if is_actual else "simulated_profit"

    for rec in chronological:
        res = str(rec.get("result") or "PENDING").upper()
        stake = int(rec.get("stake") or DEFAULT_STAKE)
        odd_val = float(rec.get("odds_entry") if is_actual else (rec.get("simulated_odds") or SIMULATED_ODDS))

        # Hitung profit secara deterministik
        if res == "WIN":
            wins += 1
            pnl = int(round(stake * (odd_val - 1.0)))
            total_stake_settled += stake
            net_profit += pnl
            odds_sum += odd_val
            rec_copy = dict(rec)
            rec_copy[profit_field] = pnl
            settled_chronological.append(rec_copy)
        elif res == "LOSE":
            losses += 1
            pnl = -stake
            total_stake_settled += stake
            net_profit += pnl
            odds_sum += odd_val
            rec_copy = dict(rec)
            rec_copy[profit_field] = pnl
            settled_chronological.append(rec_copy)
        elif res == "VOID":
            voids += 1
        elif res == "DATA UNVERIFIED" or rec.get("settlement_status") == "REVIEW":
            unverified += 1
        else:
            pendings += 1

    settled_matches = wins + losses
    win_rate = round((wins / settled_matches) * 100.0, 2) if settled_matches > 0 else 0.0
    roi = round((net_profit / total_stake_settled) * 100.0, 2) if total_stake_settled > 0 else 0.0
    avg_odds = round(odds_sum / settled_matches, 4) if settled_matches > 0 else (None if is_actual else SIMULATED_ODDS)
    be_wr = round((1.0 / avg_odds) * 100.0, 2) if (avg_odds and avg_odds > 1.0) else None

    # Perhitungan Expected Value (EV) per transaksi:
    # EV = (P(win) * Stake * (Odds - 1)) - (P(lose) * Stake)
    # Menggunakan estimasi probabilitas empiris p_hat = wins / settled_matches
    # disertai peringatan ketidakpastian statistik jika sampel < 30.
    ev_per_match: Optional[float] = None
    if settled_matches > 0 and avg_odds is not None:
        p_win = wins / settled_matches
        p_lose = 1.0 - p_win
        avg_stake = total_stake_settled / settled_matches
        ev_per_match = round((p_win * avg_stake * (avg_odds - 1.0)) - (p_lose * avg_stake), 2)

    ci_low, ci_high = wilson_confidence_interval(wins, settled_matches)
    streak_dd = calculate_streaks_and_drawdown(settled_chronological, profit_key=profit_field)

    sample_warning = (
        "LOW SAMPLE SIZE"
        if settled_matches < MIN_SAMPLE_SIZE_RELIABLE
        else "SUFFICIENT SAMPLE SIZE"
    )

    return {
        "mode": "ACTUAL" if is_actual else "SIMULATED",
        "available": True,
        "status_label": "ACTUAL ODDS PERFORMANCE" if is_actual else f"SIMULATED PERFORMANCE (ODDS {SIMULATED_ODDS:.2f})",
        "total_matches": total_matches,
        "settled_matches": settled_matches,
        "win": wins,
        "lose": losses,
        "void": voids,
        "pending": pendings,
        "unverified": unverified,
        "win_rate": win_rate,
        "net_profit": net_profit,
        "total_stake_settled": total_stake_settled,
        "roi": roi,
        "average_odds": avg_odds,
        "break_even_win_rate": be_wr,
        "expected_value_per_match": ev_per_match,
        "max_drawdown": streak_dd["max_drawdown"],
        "longest_winning_streak": streak_dd["longest_winning_streak"],
        "longest_losing_streak": streak_dd["longest_losing_streak"],
        "profit_factor": streak_dd["profit_factor"],
        "gross_profit": streak_dd["gross_profit"],
        "gross_loss": streak_dd["gross_loss"],
        "wilson_ci_95": (ci_low, ci_high),
        "sample_size_warning": sample_warning,
    }


def compute_league_tier_breakdown(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Menghitung performa berdasarkan klasifikasi liga: MAJOR, MINOR, dan UNKNOWN.
    Semua angka berasal dari database aktual (tanpa angka hardcode).
    Jika sampel < 30 (misalnya 5 pertandingan), otomatis ditandai 'LOW SAMPLE SIZE'.
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "MAJOR": [],
        "MINOR": [],
        "UNKNOWN": [],
    }
    for rec in records:
        cat = str(rec.get("league_category") or ("MAJOR" if rec.get("is_major") else "UNKNOWN")).upper()
        if cat not in buckets:
            cat = "UNKNOWN"
        buckets[cat].append(rec)

    result: Dict[str, Dict[str, Any]] = {}
    for tier, subset in buckets.items():
        sim_perf = compute_performance_block(subset, mode="SIMULATED")
        act_perf = compute_performance_block(subset, mode="ACTUAL")
        result[tier] = {
            "tier": tier,
            "total_matches": sim_perf["total_matches"],
            "settled_matches": sim_perf["settled_matches"],
            "win": sim_perf["win"],
            "lose": sim_perf["lose"],
            "void": sim_perf["void"],
            "pending": sim_perf["pending"],
            "win_rate": sim_perf["win_rate"],
            "simulated_profit": sim_perf["net_profit"],
            "simulated_roi": sim_perf["roi"],
            "actual_available": act_perf["available"],
            "actual_profit": act_perf["net_profit"] if act_perf["available"] else None,
            "actual_roi": act_perf["roi"] if act_perf["available"] else None,
            "wilson_ci_95": sim_perf["wilson_ci_95"],
            "sample_status": "LOW SAMPLE SIZE" if sim_perf["settled_matches"] < MIN_SAMPLE_SIZE_RELIABLE else "OK",
        }
    return result


def compute_trading_day_summary(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Menghasilkan ringkasan partisi harian berdasarkan cut-off 12:00 WITA.
    Diurutkan dari tanggal trading day terbaru ke terlama.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for rec in records:
        t_day = str(rec.get("trading_day") or "UNKNOWN")
        grouped.setdefault(t_day, []).append(rec)

    summaries: List[Dict[str, Any]] = []
    for t_day in sorted(grouped.keys(), reverse=True):
        day_recs = grouped[t_day]
        sim_block = compute_performance_block(day_recs, mode="SIMULATED")
        act_block = compute_performance_block(day_recs, mode="ACTUAL")
        summaries.append({
            "trading_day": t_day,
            "total_matches": sim_block["total_matches"],
            "settled_matches": sim_block["settled_matches"],
            "win": sim_block["win"],
            "lose": sim_block["lose"],
            "void": sim_block["void"],
            "pending": sim_block["pending"],
            "win_rate": sim_block["win_rate"],
            "simulated_profit": sim_block["net_profit"],
            "simulated_roi": sim_block["roi"],
            "actual_profit": act_block["net_profit"] if act_block["available"] else None,
            "summary_text": f"{sim_block['win']}W - {sim_block['lose']}L",
        })
    return summaries


def compute_full_dashboard_statistics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Mengompilasi seluruh metrik statistik yang dibutuhkan oleh Dashboard dan laporan audit."""
    return {
        "simulated": compute_performance_block(records, mode="SIMULATED"),
        "actual": compute_performance_block(records, mode="ACTUAL"),
        "by_league_tier": compute_league_tier_breakdown(records),
        "by_trading_day": compute_trading_day_summary(records),
    }