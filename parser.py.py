"""
parser.py
Modul parsing status, waktu pertandingan (clock), skor, penentuan trading day WITA,
dan deteksi kandidat untuk TRADING BOLA MENIT 60 – LAST GOAL SYSTEM.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from config import (
    ENTRY_MINUTE_MAX,
    ENTRY_MINUTE_MIN,
    REQUIRED_ENTRY_AWAY_SCORE,
    REQUIRED_ENTRY_HOME_SCORE,
    REQUIRED_PERIOD,
    TIMEZONE_NAME,
    TRADING_DAY_CUTOFF_HOUR,
    classify_league_slug,
)

WITA_TZ = ZoneInfo(TIMEZONE_NAME)

# Pemetaan status resmi ESPN ke kategori standar yang wajib dikenali
STATUS_MAP: Dict[str, str] = {
    "STATUS_SCHEDULED": "Scheduled",
    "STATUS_TBD": "Scheduled",
    "STATUS_FIRST_HALF": "First Half",
    "STATUS_HALFTIME": "Halftime",
    "STATUS_SECOND_HALF": "Second Half",
    "STATUS_IN_PROGRESS": "Live",
    "STATUS_OVERTIME": "Extra Time",
    "STATUS_EXTRA_TIME": "Extra Time",
    "STATUS_END_OF_EXTRATIME": "Extra Time",
    "STATUS_SHOOTOUT": "Penalties",
    "STATUS_PENALTIES": "Penalties",
    "STATUS_FULL_TIME": "Final",
    "STATUS_FINAL": "Final",
    "STATUS_FINAL_AET": "Final",
    "STATUS_FINAL_AGT": "Final",
    "STATUS_FINAL_PEN": "Final",
    "STATUS_POSTPONED": "Postponed",
    "STATUS_CANCELED": "Cancelled",
    "STATUS_CANCELLED": "Cancelled",
    "STATUS_ABANDONED": "Abandoned",
    "STATUS_SUSPENDED": "Suspended",
    "STATUS_DELAYED": "Suspended",
    "STATUS_RAIN_DELAY": "Suspended",
}


def compute_trading_day(dt_utc: datetime) -> str:
    """
    Menghitung tanggal Trading Day berdasarkan aturan Cut-Off 12:00 WITA (Asia/Makassar).
    - Jika waktu lokal WITA < 12:00 -> Trading day = tanggal hari sebelumnya.
    - Jika waktu lokal WITA >= 12:00 -> Trading day = tanggal hari tersebut.
    """
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    dt_wita = dt_utc.astimezone(WITA_TZ)
    if dt_wita.hour < TRADING_DAY_CUTOFF_HOUR:
        trading_date = (dt_wita - timedelta(days=1)).date()
    else:
        trading_date = dt_wita.date()
    return trading_date.isoformat()


def format_iso_utc_and_wita(dt_utc: datetime) -> Tuple[str, str]:
    """Mengonversi datetime ke format string ISO 8601 untuk UTC dan WITA."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    utc_str = dt_utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wita_str = dt_utc.astimezone(WITA_TZ).isoformat()
    return utc_str, wita_str


def parse_match_status(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mengekstrak dan memvalidasi status pertandingan dari payload ESPN.
    Mengenali: Scheduled, First Half, Halftime, Second Half, Live, Extra Time,
    Penalties, Final, Postponed, Cancelled, Suspended, Abandoned.
    """
    if not isinstance(event_data, dict):
        return {
            "canonical_status": "UNKNOWN",
            "raw_status_name": "",
            "state": "unknown",
            "period": 0,
            "completed": False,
            "is_live": False,
            "is_second_half": False,
            "is_final": False,
            "is_extra_time_or_pen": False,
            "ended_in_extra_time_or_pen": False,
            "is_void_candidate": False,
            "is_special_format": False,
        }

    status_obj = event_data.get("status")
    if not isinstance(status_obj, dict):
        comp = (event_data.get("competitions") or [{}])[0]
        status_obj = comp.get("status") if isinstance(comp, dict) else {}
    status_obj = status_obj or {}

    type_obj = status_obj.get("type") if isinstance(status_obj.get("type"), dict) else {}
    raw_name = str(type_obj.get("name") or "").strip().upper()
    state = str(type_obj.get("state") or "").strip().lower()
    detail = str(type_obj.get("detail") or type_obj.get("shortDetail") or "").strip()
    completed = bool(type_obj.get("completed", False))

    try:
        period = int(status_obj.get("period", 0) or 0)
    except (ValueError, TypeError):
        period = 0

    canonical = STATUS_MAP.get(raw_name, "UNKNOWN")

    # Penanganan fallback berdasarkan state & period jika raw_name generik (STATUS_IN_PROGRESS)
    if canonical == "Live":
        if period == 1:
            canonical = "First Half"
        elif period == 2:
            canonical = "Second Half"
        elif period in (3, 4):
            canonical = "Extra Time"
        elif period >= 5:
            canonical = "Penalties"
    elif canonical == "UNKNOWN":
        detail_upper = detail.upper()
        if "POSTPONED" in detail_upper:
            canonical = "Postponed"
        elif "CANCEL" in detail_upper:
            canonical = "Cancelled"
        elif "ABANDON" in detail_upper:
            canonical = "Abandoned"
        elif "SUSPEND" in detail_upper:
            canonical = "Suspended"
        elif state == "pre":
            canonical = "Scheduled"
        elif state == "in":
            if period == 1:
                canonical = "First Half"
            elif period == 2:
                canonical = "Second Half"
            else:
                canonical = "Live"

    # Deteksi apakah kompetisi memiliki format waktu khusus (misal bukan 2x45 menit reguler)
    comp = (event_data.get("competitions") or [{}])[0]
    format_reg_periods = (
        comp.get("format", {}).get("regulation", {}).get("periods")
        if isinstance(comp, dict) and isinstance(comp.get("format"), dict)
        else None
    )
    is_special_format = False
    if format_reg_periods is not None and int(format_reg_periods) != 2:
        is_special_format = True

    ended_in_aet_or_pen = raw_name in ("STATUS_FINAL_AET", "STATUS_FINAL_AGT", "STATUS_FINAL_PEN")
    is_final = (
        canonical == "Final"
        and state == "post"
        and completed is True
    )
    is_live = state == "in" and canonical in ("First Half", "Second Half", "Live", "Extra Time", "Penalties")
    is_second_half = (
        state == "in"
        and period == REQUIRED_PERIOD
        and canonical == "Second Half"
    )
    is_void_candidate = canonical in ("Postponed", "Cancelled", "Abandoned", "Suspended")

    return {
        "canonical_status": canonical,
        "raw_status_name": raw_name,
        "state": state,
        "period": period,
        "completed": completed,
        "detail": detail,
        "is_live": is_live,
        "is_second_half": is_second_half,
        "is_final": is_final,
        "is_extra_time_or_pen": canonical in ("Extra Time", "Penalties"),
        "ended_in_extra_time_or_pen": ended_in_aet_or_pen,
        "is_void_candidate": is_void_candidate,
        "is_special_format": is_special_format,
    }


def parse_match_clock(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mengekstrak menit pertandingan resmi dari field ESPN (displayClock / clock)
    tanpa pernah menambahkan 45 secara otomatis tanpa memeriksa struktur waktu.
    """
    status_obj = event_data.get("status")
    if not isinstance(status_obj, dict):
        comp = (event_data.get("competitions") or [{}])[0]
        status_obj = comp.get("status") if isinstance(comp, dict) else {}
    status_obj = status_obj or {}

    display_clock = str(status_obj.get("displayClock") or "").strip()
    raw_clock = status_obj.get("clock")
    try:
        period = int(status_obj.get("period", 0) or 0)
    except (ValueError, TypeError):
        period = 0

    minute: Optional[int] = None
    stoppage_minute: int = 0
    clock_valid: bool = False
    is_non_cumulative_clock: bool = False

    # 1. Prioritaskan displayClock (contoh: "63'", "45'+2'", "90'+4'", "60:12")
    if display_clock:
        # Cek pola injury time: "45'+2'" atau "90'+3'"
        match_stoppage = re.match(r"^(\d+)\s*'\s*\+\s*(\d+)\s*'?$", display_clock)
        if match_stoppage:
            base_min = int(match_stoppage.group(1))
            stoppage_minute = int(match_stoppage.group(2))
            minute = base_min
            clock_valid = True
        else:
            # Cek pola menit standar: "63'" atau "63:15" atau "63"
            match_std = re.match(r"^(\d+)(?::\d+)?\s*'?$", display_clock)
            if match_std:
                minute = int(match_std.group(1))
                clock_valid = True

    # 2. Fallback ke raw_clock (dalam detik) jika displayClock tidak terparsing
    if not clock_valid and isinstance(raw_clock, (int, float)) and raw_clock >= 0:
        if raw_clock > 0 or period == 1:
            minute = int(raw_clock // 60)
            clock_valid = True

    # 3. Validasi struktur waktu babak kedua:
    # Di ESPN Soccer reguler, babak kedua selalu kumulatif (45' s/d 90').
    # Jika period == 2 tetapi minute < 45 (misal clock me-reset ke 15'), tandai sebagai
    # non-cumulative / format khusus dan JANGAN menambahkan 45 secara buta.
    if clock_valid and period == 2 and minute is not None and minute < 45:
        is_non_cumulative_clock = True

    return {
        "minute": minute,
        "stoppage_minute": stoppage_minute,
        "display_clock": display_clock,
        "raw_clock_seconds": raw_clock,
        "period": period,
        "clock_valid": clock_valid and not is_non_cumulative_clock,
        "is_non_cumulative_clock": is_non_cumulative_clock,
    }


def parse_score(event_data: Dict[str, Any], league_slug_hint: str = "") -> Dict[str, Any]:
    """
    Mengekstrak skor home/away, tim, liga, waktu kickoff, odds entry (jika ada),
    dan skor waktu normal (regulation score) dari payload event ESPN.
    PENTING: Jika field skor hilang, kosong, atau bukan angka valid,
    `score_valid` akan bernilai False agar error API tidak pernah dianggap 0-0.
    """
    if not isinstance(event_data, dict):
        return {"score_valid": False, "error": "Invalid event_data type"}

    competitions = event_data.get("competitions")
    if not isinstance(competitions, list) or not competitions:
        return {"score_valid": False, "error": "Missing competitions array"}

    comp = competitions[0]
    if not isinstance(comp, dict):
        return {"score_valid": False, "error": "Invalid competition object"}

    competitors = comp.get("competitors")
    if not isinstance(competitors, list) or len(competitors) < 2:
        return {"score_valid": False, "error": "Missing competitors"}

    home_comp: Optional[Dict[str, Any]] = None
    away_comp: Optional[Dict[str, Any]] = None
    for c in competitors:
        if not isinstance(c, dict):
            continue
        side = str(c.get("homeAway") or "").strip().lower()
        if side == "home":
            home_comp = c
        elif side == "away":
            away_comp = c

    if not home_comp or not away_comp:
        return {"score_valid": False, "error": "Home or away competitor missing"}

    home_team = str((home_comp.get("team") or {}).get("displayName") or (home_comp.get("team") or {}).get("name") or "").strip()
    away_team = str((away_comp.get("team") or {}).get("displayName") or (away_comp.get("team") or {}).get("name") or "").strip()
    if not home_team or not away_team:
        return {"score_valid": False, "error": "Missing team names"}

    raw_home_score = home_comp.get("score")
    raw_away_score = away_comp.get("score")

    # Validasi ketat: skor tidak boleh None, string kosong, atau boolean
    if (
        raw_home_score is None
        or raw_away_score is None
        or isinstance(raw_home_score, bool)
        or isinstance(raw_away_score, bool)
        or str(raw_home_score).strip() == ""
        or str(raw_away_score).strip() == ""
    ):
        return {
            "score_valid": False,
            "error": "Missing or empty score field",
            "home_team": home_team,
            "away_team": away_team,
        }

    try:
        home_score = int(str(raw_home_score).strip())
        away_score = int(str(raw_away_score).strip())
        if home_score < 0 or away_score < 0:
            raise ValueError("Negative score")
    except (ValueError, TypeError):
        return {
            "score_valid": False,
            "error": f"Non-integer score values: {raw_home_score}-{raw_away_score}",
            "home_team": home_team,
            "away_team": away_team,
        }

    # Ekstraksi skor waktu normal (linescores babak 1 + babak 2) jika tersedia
    regulation_home_score: Optional[int] = None
    regulation_away_score: Optional[int] = None
    home_linescores = home_comp.get("linescores")
    away_linescores = away_comp.get("linescores")
    if (
        isinstance(home_linescores, list)
        and isinstance(away_linescores, list)
        and len(home_linescores) >= 2
        and len(away_linescores) >= 2
    ):
        try:
            h_p1 = int(float(home_linescores[0].get("value", 0)))
            h_p2 = int(float(home_linescores[1].get("value", 0)))
            a_p1 = int(float(away_linescores[0].get("value", 0)))
            a_p2 = int(float(away_linescores[1].get("value", 0)))
            regulation_home_score = h_p1 + h_p2
            regulation_away_score = a_p1 + a_p2
        except (ValueError, TypeError, AttributeError):
            regulation_home_score = None
            regulation_away_score = None

    # Ekstraksi liga & slug
    league_info = event_data.get("league") or comp.get("league") or {}
    league_slug = str(
        league_info.get("slug")
        or event_data.get("_league_slug")
        or league_slug_hint
        or ""
    ).strip().lower()
    league_name = str(
        league_info.get("name")
        or event_data.get("_league_name")
        or league_slug
        or "Unknown League"
    ).strip()

    # Kickoff timestamp
    raw_date = str(event_data.get("date") or comp.get("date") or "").strip()
    try:
        if raw_date.endswith("Z"):
            kickoff_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        else:
            kickoff_dt = datetime.fromisoformat(raw_date)
        if kickoff_dt.tzinfo is None:
            kickoff_dt = kickoff_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        kickoff_dt = datetime.now(timezone.utc)

    kickoff_utc, kickoff_wita = format_iso_utc_and_wita(kickoff_dt)

    # Identitas pertandingan (match_id resmi atau provisional composite ID)
    raw_id = str(event_data.get("id") or comp.get("id") or "").strip()
    is_provisional_id = False
    if raw_id:
        match_id = raw_id
    else:
        is_provisional_id = True
        safe_home = re.sub(r"[^a-z0-9]", "", home_team.lower())
        safe_away = re.sub(r"[^a-z0-9]", "", away_team.lower())
        safe_league = re.sub(r"[^a-z0-9.]", "", league_slug or "unknown")
        match_id = f"PROVISIONAL_{safe_league}_{safe_home}_{safe_away}_{kickoff_utc}"

    # Ekstraksi odds aktual jika benar-benar tersedia untuk Over 0.5 saat skor 0-0
    odds_entry: Optional[float] = None
    odds_source: str = "SIMULATED_DEFAULT"
    odds_list = comp.get("odds")
    if isinstance(odds_list, list) and odds_list:
        for odd_item in odds_list:
            if not isinstance(odd_item, dict):
                continue
            over_under = odd_item.get("overUnder")
            over_odds_val = odd_item.get("overOdds") or odd_item.get("decimalOverOdds")
            provider_name = str((odd_item.get("provider") or {}).get("name") or "ESPN_PROVIDER").strip()
            if over_under is not None and over_odds_val is not None:
                try:
                    ou_float = float(over_under)
                    odd_float = float(over_odds_val)
                    # Hanya terima jika decimal odds valid (> 1.01 dan < 25.0) dan line 0.5
                    if abs(ou_float - 0.5) < 1e-6 and 1.01 < odd_float < 25.0:
                        odds_entry = round(odd_float, 3)
                        odds_source = f"ACTUAL:{provider_name}"
                        break
                except (ValueError, TypeError):
                    continue

    league_category = classify_league_slug(league_slug)

    return {
        "score_valid": True,
        "match_id": match_id,
        "source_event_id": raw_id or match_id,
        "is_provisional_id": is_provisional_id,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "formatted_score": f"{home_score}-{away_score}",
        "regulation_home_score": regulation_home_score,
        "regulation_away_score": regulation_away_score,
        "league": league_name,
        "league_slug": league_slug or "unknown",
        "league_category": league_category,
        "is_major": league_category == "MAJOR",
        "kickoff_utc": kickoff_utc,
        "kickoff_wita": kickoff_wita,
        "odds_entry": odds_entry,
        "odds_source": odds_source,
    }


def extract_goal_events_from_payload(event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Mengekstrak daftar event gol resmi dari payload scoreboard (`competitions[0].details`)
    atau summary (`keyEvents` / `scoringPlays`).
    """
    goals: List[Dict[str, Any]] = []
    if not isinstance(event_data, dict):
        return goals

    comp = (event_data.get("competitions") or [{}])[0]
    details = comp.get("details") if isinstance(comp, dict) else []
    if not isinstance(details, list):
        details = []

    # Coba ambil dari details di scoreboard
    for item in details:
        if not isinstance(item, dict):
            continue
        is_scoring = bool(item.get("scoringPlay", False))
        type_text = str((item.get("type") or {}).get("text") or "").lower()
        if not is_scoring and "goal" not in type_text and "penalty - scored" not in type_text:
            continue
        if "miss" in type_text or "saved" in type_text:
            continue

        clock_disp = str((item.get("clock") or {}).get("displayValue") or "").strip()
        clock_val = (item.get("clock") or {}).get("value")
        minute_val: Optional[int] = None
        if clock_disp:
            m = re.match(r"^(\d+)", clock_disp)
            if m:
                minute_val = int(m.group(1))
        elif isinstance(clock_val, (int, float)):
            minute_val = int(clock_val // 60)

        period_num = int((item.get("period") or {}).get("number", 0) or 0)
        team_id = str((item.get("team") or {}).get("id") or "")
        athletes = item.get("athletesInvolved") or []
        scorer = ""
        if isinstance(athletes, list) and athletes:
            scorer = str(athletes[0].get("displayName") or athletes[0].get("shortName") or "").strip()

        goals.append({
            "minute": minute_val,
            "clock_display": clock_disp or (f"{minute_val}'" if minute_val is not None else "N/A"),
            "period": period_num,
            "team_id": team_id,
            "scorer": scorer,
            "type": str((item.get("type") or {}).get("text") or "Goal"),
            "is_own_goal": bool(item.get("ownGoal", False)),
            "is_penalty": bool(item.get("penaltyKick", False)),
            "time_approximate": False,
            "source": "ESPN_OFFICIAL_DETAIL",
        })

    return goals


def parse_full_event(event_data: Dict[str, Any], league_slug_hint: str = "") -> Dict[str, Any]:
    """Menggabungkan hasil parsing status, waktu, skor, dan event gol menjadi satu objek terpadu."""
    status_info = parse_match_status(event_data)
    clock_info = parse_match_clock(event_data)
    score_info = parse_score(event_data, league_slug_hint=league_slug_hint)
    goal_events = extract_goal_events_from_payload(event_data)

    return {
        "status": status_info,
        "clock": clock_info,
        "score": score_info,
        "goal_events": goal_events,
    }


def detect_candidate(parsed_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Memvalidasi apakah satu pertandingan yang telah diparsing memenuhi seluruh syarat
    kandidat trading:
    1. Status pertandingan LIVE dan berada pada Babak Kedua (Second Half, period == 2).
    2. Pertandingan belum selesai, belum ditunda, belum dibatalkan, dan bukan format waktu khusus.
    3. Menit pertandingan berada pada rentang 60 s/d 66 (inklusif) dan clock valid.
    4. Skor resmi saat deteksi adalah 0-0 (score_valid == True).
    """
    status = parsed_event.get("status") or {}
    clock = parsed_event.get("clock") or {}
    score = parsed_event.get("score") or {}

    reasons: List[str] = []

    if not score.get("score_valid", False):
        reasons.append(f"Invalid score data: {score.get('error', 'unknown')}")

    if not status.get("is_live", False):
        reasons.append(f"Match not live (status={status.get('canonical_status')})")

    if not status.get("is_second_half", False) or status.get("period") != REQUIRED_PERIOD:
        reasons.append(
            f"Not in Second Half (status={status.get('canonical_status')}, period={status.get('period')})"
        )

    if status.get("is_final", False) or status.get("is_void_candidate", False):
        reasons.append(f"Match already finished or voided ({status.get('canonical_status')})")

    if status.get("is_special_format", False) or clock.get("is_non_cumulative_clock", False):
        reasons.append("Special or non-standard match clock format detected")

    minute = clock.get("minute")
    if not clock.get("clock_valid", False) or minute is None:
        reasons.append("Match clock unavailable or unverified")
    elif not (ENTRY_MINUTE_MIN <= minute <= ENTRY_MINUTE_MAX):
        reasons.append(f"Minute {minute} outside target window [{ENTRY_MINUTE_MIN}, {ENTRY_MINUTE_MAX}]")

    if score.get("score_valid", False):
        h_score = score.get("home_score")
        a_score = score.get("away_score")
        if h_score != REQUIRED_ENTRY_HOME_SCORE or a_score != REQUIRED_ENTRY_AWAY_SCORE:
            reasons.append(f"Score is {h_score}-{a_score}, required 0-0")

    is_candidate = len(reasons) == 0
    return {
        "is_candidate": is_candidate,
        "decision": "CANDIDATE" if is_candidate else "NOT CANDIDATE",
        "reasons": reasons,
        "minute_detected": minute,
        "score_at_entry": score.get("formatted_score") if score.get("score_valid") else None,
    }