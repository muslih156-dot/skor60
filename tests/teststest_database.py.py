"""
tests/test_database.py
Unit tests untuk menguji deduplikasi idempotent (Test 10), integritas database,
dan ketetapan trading_day saat pertandingan berubah menjadi FT pada hari berikutnya.
"""

from datetime import datetime, timezone

from database import TradingDatabase
from parser import parse_full_event
from settlement import validate_final_result
from tests.test_parser import _build_mock_espn_event


def test_10_deduplikasi_scan_10_kali(tmp_path):
    """
    Test 10 – Scan pertandingan yang sama 10 kali.
    Expected: Hanya satu record trading, stake dan profit tidak tergandakan.
    """
    db = TradingDatabase(
        db_path=tmp_path / "test_dedup.db",
        matches_json_path=tmp_path / "matches.json",
    )
    ev = _build_mock_espn_event(match_id="401999888", display_clock="62'", home_score="0", away_score="0")
    parsed = parse_full_event(ev)

    created_flags = []
    for _ in range(10):
        _, created = db.insert_candidate_idempotent(parsed, stake=50_000)
        created_flags.append(created)

    assert created_flags[0] is True
    assert all(flag is False for flag in created_flags[1:])

    all_matches = db.get_all_matches()
    assert len(all_matches) == 1
    assert all_matches[0]["match_id"] == "401999888"
    assert all_matches[0]["stake"] == 50_000


def test_trading_day_tidak_berubah_saat_ft(tmp_path):
    """
    Memastikan hasil tetap berada pada trading day saat ENTRY meskipun
    pertandingan baru selesai setelah melewati batas pergantian waktu.
    """
    db = TradingDatabase(
        db_path=tmp_path / "test_td.db",
        matches_json_path=tmp_path / "matches.json",
    )
    ev_entry = _build_mock_espn_event(match_id="401777666", display_clock="61'", home_score="0", away_score="0")
    parsed_entry = parse_full_event(ev_entry)

    # Entry pada 29 Oktober 2026 pukul 11:30 WITA (03:30 UTC) -> Trading day = 2026-10-28
    dt_entry = datetime(2026, 10, 29, 3, 30, 0, tzinfo=timezone.utc)
    rec, _ = db.insert_candidate_idempotent(parsed_entry, detected_dt_utc=dt_entry)
    assert rec["trading_day"] == "2026-10-28"

    # Pertandingan selesai pukul 12:15 WITA (04:15 UTC) yang sudah masuk trading day 2026-10-29
    dt_ft = datetime(2026, 10, 29, 4, 15, 0, tzinfo=timezone.utc)
    ev_ft = _build_mock_espn_event(
        match_id="401777666",
        status_name="STATUS_FULL_TIME",
        state="post",
        completed=True,
        home_score="1",
        away_score="0",
    )
    settled = validate_final_result(rec, scoreboard_match=parse_full_event(ev_ft), now_utc=dt_ft)
    saved = db.update_existing_record(settled)

    assert saved["trading_day"] == "2026-10-28"
    assert saved["result"] == "WIN"