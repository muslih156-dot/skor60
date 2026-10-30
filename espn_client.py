"""
espn_client.py
Klien HTTP tangguh untuk mengambil data pertandingan dari ESPN API.
Dilengkapi deduplikasi ESPN ALL + ESPN MULTI LEAGUE, retry dengan exponential backoff,
pencatatan metrik kesehatan API, serta isolasi error agar kegagalan jaringan
tidak pernah menghasilkan skor atau kandidat palsu.
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import (
    ACTIVE_SCAN_LEAGUES,
    API_BACKOFF_BASE_SECONDS,
    API_MAX_RETRIES,
    API_TIMEOUT_SECONDS,
    ERROR_LOG_PATH,
    ESPN_ALL_SCOREBOARD_URL,
    ESPN_LEAGUE_SCOREBOARD_TEMPLATE,
    ESPN_SUMMARY_TEMPLATE,
    USER_AGENT,
    ensure_directories,
)
from parser import parse_full_event

ensure_directories()

logger = logging.getLogger("skor60.espn_client")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(ERROR_LOG_PATH, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)


def _request_json_with_retry(
    url: str,
    session: Optional[requests.Session] = None,
    timeout: int = API_TIMEOUT_SECONDS,
    max_retries: int = API_MAX_RETRIES,
) -> Dict[str, Any]:
    """
    Melakukan HTTP GET dengan retry dan exponential backoff.
    Mengembalikan dictionary yang berisi status keberhasilan, HTTP code, latency, dan payload.
    """
    client = session or requests.Session()
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    last_error = ""
    http_status: Optional[int] = None
    elapsed_ms: float = 0.0

    for attempt in range(1, max_retries + 1):
        start_t = time.monotonic()
        try:
            resp = client.get(url, headers=headers, timeout=timeout)
            elapsed_ms = round((time.monotonic() - start_t) * 1000.0, 2)
            http_status = resp.status_code

            if resp.status_code == 200:
                data = resp.json()
                if not isinstance(data, dict):
                    raise ValueError("JSON root is not an object")
                return {
                    "ok": True,
                    "url": url,
                    "http_status": http_status,
                    "elapsed_ms": elapsed_ms,
                    "attempts": attempt,
                    "data": data,
                    "error": None,
                }

            last_error = f"HTTP {resp.status_code} from {url}"
            logger.warning("Attempt %d/%d failed: %s", attempt, max_retries, last_error)

            if attempt < max_retries:
                sleep_sec = API_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                time.sleep(sleep_sec)

        except (requests.RequestException, ValueError) as exc:
            elapsed_ms = round((time.monotonic() - start_t) * 1000.0, 2)
            last_error = f"{type(exc).__name__}: {exc}"
            logger.error("Attempt %d/%d exception on %s: %s", attempt, max_retries, url, last_error)
            if attempt < max_retries:
                sleep_sec = API_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                time.sleep(sleep_sec)

    return {
        "ok": False,
        "url": url,
        "http_status": http_status,
        "elapsed_ms": elapsed_ms,
        "attempts": max_retries,
        "data": None,
        "error": last_error,
    }


def extract_goal_events_from_payload(header: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Mengekstrak daftar event gol dari payload header / competitions ESPN sebagai fallback.
    """
    goals: List[Dict[str, Any]] = []
    try:
        competitions = header.get("competitions", [])
        if competitions and isinstance(competitions, list):
            details = competitions[0].get("details", [])
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                is_scoring = bool(detail.get("scoringPlay", False))
                type_text = str((detail.get("type") or {}).get("text") or "").lower()
                if not is_scoring and "goal" not in type_text and "penalty - scored" not in type_text:
                    continue
                if "miss" in type_text or "saved" in type_text:
                    continue

                clock_disp = str((detail.get("clock") or {}).get("displayValue") or "").strip()
                clock_val = (detail.get("clock") or {}).get("value")
                minute_val: Optional[int] = None
                if clock_disp:
                    m = re.match(r"^(\d+)", clock_disp)
                    if m:
                        minute_val = int(m.group(1))
                elif isinstance(clock_val, (int, float)):
                    minute_val = int(clock_val // 60)

                period_num = int((detail.get("period") or {}).get("number", 0) or 0)
                team_name = str((detail.get("team") or {}).get("displayName") or "").strip()
                participants = detail.get("participants") or []
                scorer = ""
                if isinstance(participants, list) and participants:
                    athlete = (participants[0] or {}).get("athlete") or {}
                    scorer = str(athlete.get("displayName") or "").strip()

                goals.append({
                    "minute": minute_val,
                    "clock_display": clock_disp or (f"{minute_val}'" if minute_val is not None else "N/A"),
                    "period": period_num,
                    "team": team_name,
                    "scorer": scorer,
                    "type": str((detail.get("type") or {}).get("text") or "Goal"),
                    "text": str(detail.get("text") or ""),
                    "time_approximate": False,
                    "source": "ESPN_SUMMARY_HEADER_DETAILS",
                })
    except Exception as e:
        logger.error("Error extracting goal events from payload header: %s", e)
    return goals


def fetch_live_match(
    leagues: Optional[List[str]] = None,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """
    Mengambil data scoreboard dari ESPN ALL dan ESPN MULTI LEAGUE,
    mendeduplikasi berdasarkan match_id resmi, mem-parsing seluruh event,
    dan mengembalikan metrik telemetri lengkap.
    """
    scan_leagues = leagues if leagues is not None else ACTIVE_SCAN_LEAGUES
    http_session = session or requests.Session()
    scan_started_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    endpoints_to_query: List[Tuple[str, str]] = [("all", ESPN_ALL_SCOREBOARD_URL)]
    for slug in scan_leagues:
        endpoints_to_query.append((slug, ESPN_LEAGUE_SCOREBOARD_TEMPLATE.format(league_slug=slug)))

    endpoints_succeeded = 0
    endpoints_failed = 0
    endpoint_logs: List[Dict[str, Any]] = []
    raw_events_received = 0
    deduplicated_raw_events: Dict[str, Tuple[Dict[str, Any], str]] = {}

    for slug_label, url in endpoints_to_query:
        res = _request_json_with_retry(url, session=http_session)
        endpoint_logs.append({
            "league_slug": slug_label,
            "url": url,
            "ok": res["ok"],
            "http_status": res["http_status"],
            "elapsed_ms": res["elapsed_ms"],
            "attempts": res["attempts"],
            "error": res["error"],
        })

        if not res["ok"] or not res["data"]:
            endpoints_failed += 1
            continue

        endpoints_succeeded += 1
        payload = res["data"]

        leagues_meta = payload.get("leagues") or []
        default_league_name = ""
        default_league_slug = "" if slug_label == "all" else slug_label
        if isinstance(leagues_meta, list) and leagues_meta and isinstance(leagues_meta[0], dict):
            default_league_name = str(leagues_meta[0].get("name") or "").strip()
            default_league_slug = str(leagues_meta[0].get("slug") or default_league_slug).strip()

        events = payload.get("events")
        if not isinstance(events, list):
            continue

        raw_events_received += len(events)
        for ev in events:
            if not isinstance(ev, dict):
                continue
            ev_copy = dict(ev)
            if default_league_name and "_league_name" not in ev_copy:
                ev_copy["_league_name"] = default_league_name
            if default_league_slug and "_league_slug" not in ev_copy:
                ev_copy["_league_slug"] = default_league_slug

            ev_id = str(ev_copy.get("id") or "").strip()
            if not ev_id:
                ev_id = f"RAW_NO_ID_{len(deduplicated_raw_events)}"

            if ev_id not in deduplicated_raw_events or slug_label != "all":
                deduplicated_raw_events[ev_id] = (ev_copy, default_league_slug)

    parsed_matches: List[Dict[str, Any]] = []
    matches_processed = 0
    matches_failed_parsing = 0
    parse_errors: List[str] = []

    for ev_id, (raw_ev, hint_slug) in deduplicated_raw_events.items():
        try:
            parsed = parse_full_event(raw_ev, league_slug_hint=hint_slug)
            if not parsed["score"].get("score_valid", False):
                matches_failed_parsing += 1
                parse_errors.append(
                    f"Event {ev_id}: {parsed['score'].get('error', 'Invalid score')}"
                )
                continue
            parsed["raw_event"] = raw_ev
            parsed_matches.append(parsed)
            matches_processed += 1
        except Exception as exc:
            matches_failed_parsing += 1
            err_msg = f"Event {ev_id} parse exception: {type(exc).__name__}: {exc}"
            parse_errors.append(err_msg)
            logger.error(err_msg)

    overall_status = "OK"
    if endpoints_succeeded == 0:
        overall_status = "CRITICAL_ALL_ENDPOINTS_FAILED"
    elif endpoints_failed > 0:
        overall_status = "DEGRADED_PARTIAL_FAILURE"

    return {
        "scan_timestamp_utc": scan_started_utc,
        "source_status": overall_status,
        "endpoints_queried": len(endpoints_to_query),
        "endpoints_succeeded": endpoints_succeeded,
        "endpoints_failed": endpoints_failed,
        "raw_events_received": raw_events_received,
        "unique_events_count": len(deduplicated_raw_events),
        "matches_processed": matches_processed,
        "matches_failed_parsing": matches_failed_parsing,
        "parse_errors": parse_errors[:50],
        "endpoint_logs": endpoint_logs,
        "matches": parsed_matches,
    }


def fetch_match_detail(
    match_id: str,
    league_slug: str = "all",
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """
    Mengambil detail pertandingan spesifik dari endpoint ESPN Summary.
    """
    slug = (league_slug or "all").strip().lower()
    if slug == "unknown" or not slug:
        slug = "all"
    url = ESPN_SUMMARY_TEMPLATE.format(league_slug=slug, match_id=match_id)
    res = _request_json_with_retry(url, session=session)

    if not res["ok"] or not res["data"]:
        return {
            "ok": False,
            "match_id": match_id,
            "http_status": res["http_status"],
            "elapsed_ms": res["elapsed_ms"],
            "error": res["error"],
            "parsed": None,
            "raw_summary": None,
        }

    summary_data = res["data"]
    header = summary_data.get("header") or {}
    competitions = header.get("competitions") or []

    synthetic_event: Dict[str, Any] = {
        "id": header.get("id") or match_id,
        "competitions": competitions,
        "league": header.get("league") or {"slug": slug},
        "_league_slug": slug,
    }
    if competitions and isinstance(competitions[0], dict):
        synthetic_event["status"] = competitions[0].get("status") or {}
        synthetic_event["date"] = competitions[0].get("date") or ""

    parsed = parse_full_event(synthetic_event, league_slug_hint=slug)
    return {
        "ok": parsed["score"].get("score_valid", False),
        "match_id": match_id,
        "http_status": res["http_status"],
        "elapsed_ms": res["elapsed_ms"],
        "error": None if parsed["score"].get("score_valid", False) else parsed["score"].get("error"),
        "parsed": parsed,
        "raw_summary": summary_data,
    }


def fetch_match_events(
    match_id: str,
    league_slug: str = "all",
    summary_payload: Optional[Dict[str, Any]] = None,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    """
    Mengekstrak daftar event gol resmi dari endpoint summary (`keyEvents` / `scoringPlays` / `header`).
    """
    if summary_payload is None:
        detail_res = fetch_match_detail(match_id, league_slug=league_slug, session=session)
        if not detail_res["ok"] or not detail_res["raw_summary"]:
            return []
        summary_payload = detail_res["raw_summary"]

    goals: List[Dict[str, Any]] = []
    if not isinstance(summary_payload, dict):
        return goals

    key_events = summary_payload.get("keyEvents") or summary_payload.get("scoringPlays") or []
    if isinstance(key_events, list):
        for item in key_events:
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
            team_name = str((item.get("team") or {}).get("displayName") or "").strip()
            participants = item.get("participants") or []
            scorer = ""
            if isinstance(participants, list) and participants:
                athlete = (participants[0] or {}).get("athlete") or {}
                scorer = str(athlete.get("displayName") or "").strip()

            goals.append({
                "minute": minute_val,
                "clock_display": clock_disp or (f"{minute_val}'" if minute_val is not None else "N/A"),
                "period": period_num,
                "team": team_name,
                "scorer": scorer,
                "type": str((item.get("type") or {}).get("text") or "Goal"),
                "text": str(item.get("text") or ""),
                "time_approximate": False,
                "source": "ESPN_SUMMARY_KEY_EVENTS",
            })

    if not goals:
        header = summary_payload.get("header") or {}
        goals = extract_goal_events_from_payload(header)

    return goals
