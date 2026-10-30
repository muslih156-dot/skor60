"""
tests/test_parser.py
Unit tests untuk menguji fungsi parsing status, waktu, skor, deteksi kandidat,
cut-off trading day 12:00 WITA, dan penanganan kegagalan API (Test 1, 2, 3, 7, 11, 12).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from espn_client import fetch_live_match
from parser import (
    compute_trading_day,
    detect_candidate,
    parse_full_event,
    parse_match_clock,
    parse_match_status,
)


def _build_mock_espn_event(
    match_id: str = "401500001",
    status_name: str = "STATUS_SECOND_HALF",
    state: str = "in",
    period: int = 2,
    completed: bool = False,
    display_clock: str = "60'",
    home_score: str = "0",
    away_score: str = "0",
    league_slug: str = "eng.1",
) -> dict:
    return {
        "id": match_id,
        "date": "2026-10-29T12:00:00Z",
        "league": {"slug": league_slug, "name": "English Premier League"},
        "status": {
            "clock": 3600.0,
            "displayClock": display_clock,
            "period": period,
            "type": {
                "name": status_name,
                "state": state,
                "completed": completed,
                "detail": display_clock,
            },
        },
        "competitions": [
            {
                "id": match_id,
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": home_score,
                        "team": {"displayName": "Arsenal"},
                    },
                    {
                        "homeAway": "away",
                        "score": away_score,
                        "team": {"displayName": "Chelsea"},
                    },
                ],
            }
        ],
    }


def test_1_deteksi_kandidat_valid():
    """Test 1 – Input: LIVE, menit 60, skor 0-0 -> Expected: CANDIDATE."""
    ev = _build_mock_espn_event(display_clock="60'", home_score="0", away_score="0")
    parsed = parse_full_event(ev)
    res = detect_candidate(parsed)
    assert res["is_candidate"] is True
    assert res["decision"] == "CANDIDATE"
    assert res["minute_detected"] == 60
    assert res["score_at_entry"] == "0-0"


def test_2_di_luar_window_menit_59():
    """Test 2 – Input: LIVE, menit 59, skor 0-0 -> Expected: NOT CANDIDATE."""
    ev = _build_mock_espn_event(display_clock="59'", home_score="0", away_score="0")
    parsed = parse_full_event(ev)
    res = detect_candidate(parsed)
    assert res["is_candidate"] is False
    assert res["decision"] == "NOT CANDIDATE"


def test_3_skor_sudah_berubah_1_0():
    """Test 3 – Input: LIVE, menit 63, skor 1-0 -> Expected: NOT CANDIDATE."""
    ev = _build_mock_espn_event(display_clock="63'", home_score="1", away_score="0")
    parsed = parse_full_event(ev)
    res = detect_candidate(parsed)
    assert res["is_candidate"] is False
    assert res["decision"] == "NOT CANDIDATE"


def test_7_extra_time_tidak_otomatis_ft():
    """Test 7 – Status: Extra Time -> Expected: Tidak otomatis dianggap FT."""
    ev = _build_mock_espn_event(
        status_name="STATUS_EXTRA_TIME",
        state="in",
        period=3,
        completed=False,
        display_clock="105'",
    )
    status_info = parse_match_status(ev)
    assert status_info["canonical_status"] == "Extra Time"
    assert status_info["is_final"] is False


def test_11_cutoff_wita_12_00():
    """
    Test 11 – Cut off WITA:
    - 29 Oktober 2026 pukul 08:55 WITA (00:55 UTC) -> Trading day 28 Oktober 2026.
    - 29 Oktober 2026 pukul 12:00 WITA (04:00 UTC) -> Trading day 29 Oktober 2026.
    """
    dt_before_cutoff = datetime(2026, 10, 29, 0, 55, 0, tzinfo=timezone.utc)  # 08:55 WITA
    dt_at_cutoff = datetime(2026, 10, 29, 4, 0, 0, tzinfo=timezone.utc)       # 12:00 WITA

    assert compute_trading_day(dt_before_cutoff) == "2026-10-28"
    assert compute_trading_day(dt_at_cutoff) == "2026-10-29"


def test_12_api_gagal_403_atau_timeout():
    """
    Test 12 – API gagal (HTTP 403 atau timeout).
    Expected: ERROR LOGGED, tidak membuat kandidat palsu.
    """
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_session.get.return_value = mock_response

    with patch("espn_client.API_MAX_RETRIES", 1):
        res = fetch_live_match(leagues=["eng.1"], session=mock_session)

    assert res["source_status"] == "CRITICAL_ALL_ENDPOINTS_FAILED"
    assert res["endpoints_failed"] == 2
    assert len(res["matches"]) == 0
    assert all(log["http_status"] == 403 and log["ok"] is False for log in res["endpoint_logs"])


def test_clock_tidak_menambah_45_otomatis():
    """Memastikan parser menolak clock babak kedua yang me-reset ke <45 tanpa menambah 45 otomatis."""
    ev = _build_mock_espn_event(period=2, display_clock="16'")
    clock_info = parse_match_clock(ev)
    assert clock_info["is_non_cumulative_clock"] is True
    assert clock_info["clock_valid"] is False
