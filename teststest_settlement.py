"""
tests/test_settlement.py
Unit tests untuk validasi WIN, LOSE, PENDING saat menit 90 LIVE, VOID, perhitungan profit,
konflik skor scoreboard vs detail, dan koreksi hasil resmi provider (Test 4, 5, 6, 8, 9, 13, 14).
"""

from database import TradingDatabase
from parser import parse_full_event
from settlement import calculate_profit, validate_final_result
from tests.test_parser import _build_mock_espn_event


def _create_sample_entry_record(tmp_path) -> dict:
    db = TradingDatabase(
        db_path=tmp_path / "test.db",
        matches_json_path=tmp_path / "matches.json",
    )
    ev_entry = _build_mock_espn_event(display_clock="60'", home_score="0", away_score="0")
    parsed_entry = parse_full_event(ev_entry)
    rec, _ = db.insert_candidate_idempotent(parsed_entry)
    return rec


def test_4_settlement_win(tmp_path):
    """Test 4 – Entry: 60', 0-0. Final: 1-0 -> Expected: WIN."""
    rec = _create_sample_entry_record(tmp_path)
    ev_ft = _build_mock_espn_event(
        status_name="STATUS_FULL_TIME",
        state="post",
        completed=True,
        display_clock="90'",
        home_score="1",
        away_score="0",
    )
    parsed_ft = parse_full_event(ev_ft)
    settled = validate_final_result(rec, scoreboard_match=parsed_ft)
    assert settled["result"] == "WIN"
    assert settled["settlement_status"] == "SETTLED"
    assert settled["final_score"] == "1-0"
    assert settled["simulated_profit"] == 40_000


def test_5_settlement_lose(tmp_path):
    """Test 5 – Entry: 60', 0-0. Final: 0-0 -> Expected: LOSE."""
    rec = _create_sample_entry_record(tmp_path)
    ev_ft = _build_mock_espn_event(
        status_name="STATUS_FULL_TIME",
        state="post",
        completed=True,
        display_clock="90'",
        home_score="0",
        away_score="0",
    )
    parsed_ft = parse_full_event(ev_ft)
    settled = validate_final_result(rec, scoreboard_match=parsed_ft)
    assert settled["result"] == "LOSE"
    assert settled["settlement_status"] == "SETTLED"
    assert settled["final_score"] == "0-0"
    assert settled["simulated_profit"] == -50_000


def test_6_belum_final_menit_90_live(tmp_path):
    """Test 6 – Entry: 60', 0-0. Current: 90', 0-0, Status: LIVE -> Expected: PENDING."""
    rec = _create_sample_entry_record(tmp_path)
    ev_90 = _build_mock_espn_event(
        status_name="STATUS_SECOND_HALF",
        state="in",
        completed=False,
        display_clock="90'+3'",
        home_score="0",
        away_score="0",
    )
    parsed_90 = parse_full_event(ev_90)
    updated = validate_final_result(rec, scoreboard_match=parsed_90)
    assert updated["result"] == "PENDING"
    assert updated["settlement_status"] == "PENDING"


def test_8_status_abandoned_void(tmp_path):
    """Test 8 – Status: Abandoned -> Expected: VOID."""
    rec = _create_sample_entry_record(tmp_path)
    ev_aban = _build_mock_espn_event(
        status_name="STATUS_ABANDONED",
        state="post",
        completed=False,
        display_clock="75'",
        home_score="0",
        away_score="0",
    )
    parsed_aban = parse_full_event(ev_aban)
    updated = validate_final_result(rec, scoreboard_match=parsed_aban)
    assert updated["result"] == "VOID"
    assert updated["settlement_status"] == "VOID"
    assert updated["profit"] == 0


def test_9_perhitungan_profit():
    """
    Test 9 – Stake: Rp50.000, Odds: 1.80.
    WIN: +Rp40.000, LOSE: -Rp50.000, VOID: Rp0.
    """
    win_p = calculate_profit("WIN", stake=50_000, odds_entry=1.80)
    lose_p = calculate_profit("LOSE", stake=50_000, odds_entry=1.80)
    void_p = calculate_profit("VOID", stake=50_000, odds_entry=1.80)

    assert win_p["profit"] == 40_000
    assert lose_p["profit"] == -50_000
    assert void_p["profit"] == 0


def test_13_konflik_skor_scoreboard_vs_detail(tmp_path):
    """
    Test 13 – Scoreboard dan match detail berbeda.
    Expected: REVIEW, tidak langsung settlement.
    """
    rec = _create_sample_entry_record(tmp_path)
    ev_sb = _build_mock_espn_event(
        status_name="STATUS_FULL_TIME",
        state="post",
        completed=True,
        home_score="1",
        away_score="0",
    )
    ev_dt = _build_mock_espn_event(
        status_name="STATUS_FULL_TIME",
        state="post",
        completed=True,
        home_score="0",
        away_score="0",
    )
    parsed_sb = parse_full_event(ev_sb)
    parsed_dt = parse_full_event(ev_dt)

    updated = validate_final_result(rec, scoreboard_match=parsed_sb, detail_match=parsed_dt)
    assert updated["settlement_status"] == "REVIEW"
    assert updated["result"] == "DATA UNVERIFIED"
    assert len(updated["revision_history"]) == 1


def test_14_koreksi_hasil_provider(tmp_path):
    """
    Test 14 – Final score berubah akibat koreksi resmi provider.
    Expected: Revision history tercatat, profit lama tidak dihapus tanpa audit.
    """
    rec = _create_sample_entry_record(tmp_path)
    ev_ft_initial = _build_mock_espn_event(
        status_name="STATUS_FULL_TIME",
        state="post",
        completed=True,
        home_score="1",
        away_score="0",
    )
    settled_1 = validate_final_result(rec, scoreboard_match=parse_full_event(ev_ft_initial))
    assert settled_1["result"] == "WIN"
    assert settled_1["profit"] == 40_000

    # Provider melakukan koreksi resmi menjadi 0-0 (misal gol dianulir pasca-laga)
    ev_ft_corrected = _build_mock_espn_event(
        status_name="STATUS_FULL_TIME",
        state="post",
        completed=True,
        home_score="0",
        away_score="0",
    )
    settled_2 = validate_final_result(settled_1, scoreboard_match=parse_full_event(ev_ft_corrected))
    assert settled_2["result"] == "LOSE"
    assert settled_2["profit"] == -50_000
    assert len(settled_2["revision_history"]) == 1
    rev = settled_2["revision_history"][0]
    assert rev["reason"] == "PROVIDER_OFFICIAL_SCORE_CORRECTION"
    assert rev["old_result"] == "WIN"
    assert rev["new_result"] == "LOSE"
    assert rev["old_profit"] == 40_000
