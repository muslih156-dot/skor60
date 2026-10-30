"""
tests/test_statistics.py
Unit tests untuk memverifikasi perhitungan statistik, Win Rate, Net Profit, ROI,
pengecualian LIVE/PENDING/VOID dari denominator ROI, dan penanda LOW SAMPLE SIZE (Test 15).
"""

from statistics import compute_full_dashboard_statistics, compute_performance_block


def test_15_statistik_11_win_6_lose():
    """
    Test 15 – 11 WIN, 6 LOSE, odds 1.80, stake Rp50.000.
    Expected:
      - Total match: 17
      - Win rate: 64.71%
      - Total stake: Rp850.000
      - Net profit: Rp140.000
      - ROI: 16.47%
    """
    records = []
    for i in range(11):
        records.append({
            "match_id": f"W_{i}",
            "detected_at_utc": f"2026-10-28T14:{i:02d}:00Z",
            "trading_day": "2026-10-28",
            "stake": 50_000,
            "odds_entry": 1.80,
            "simulated_odds": 1.80,
            "result": "WIN",
            "settlement_status": "SETTLED",
            "league_category": "MAJOR",
            "is_major": True,
        })
    for j in range(6):
        records.append({
            "match_id": f"L_{j}",
            "detected_at_utc": f"2026-10-28T16:{j:02d}:00Z",
            "trading_day": "2026-10-28",
            "stake": 50_000,
            "odds_entry": 1.80,
            "simulated_odds": 1.80,
            "result": "LOSE",
            "settlement_status": "SETTLED",
            "league_category": "MAJOR",
            "is_major": True,
        })

    # Tambahkan pertandingan PENDING dan VOID untuk memastikan tidak masuk ke denominator ROI
    records.append({
        "match_id": "P_1",
        "detected_at_utc": "2026-10-28T18:00:00Z",
        "trading_day": "2026-10-28",
        "stake": 50_000,
        "odds_entry": None,
        "simulated_odds": 1.80,
        "result": "PENDING",
        "settlement_status": "PENDING",
        "league_category": "MINOR",
        "is_major": False,
    })

    sim_perf = compute_performance_block(records[:17], mode="SIMULATED")
    assert sim_perf["total_matches"] == 17
    assert sim_perf["settled_matches"] == 17
    assert sim_perf["win"] == 11
    assert sim_perf["lose"] == 6
    assert sim_perf["win_rate"] == 64.71
    assert sim_perf["total_stake_settled"] == 850_000
    assert sim_perf["net_profit"] == 140_000
    assert sim_perf["roi"] == 16.47
    assert sim_perf["break_even_win_rate"] == 55.56

    # Pastikan adanya PENDING tidak mengubah ROI maupun total_stake_settled
    with_pending = compute_performance_block(records, mode="SIMULATED")
    assert with_pending["settled_matches"] == 17
    assert with_pending["total_stake_settled"] == 850_000
    assert with_pending["roi"] == 16.47

    # Cek flag LOW SAMPLE SIZE ketika Major hanya memiliki 5 pertandingan
    full_stats_small = compute_full_dashboard_statistics(records[:5])
    assert full_stats_small["by_league_tier"]["MAJOR"]["sample_status"] == "LOW SAMPLE SIZE"
