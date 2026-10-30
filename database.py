"""
database.py
Manajemen penyimpanan data produksi untuk TRADING BOLA MENIT 60 – LAST GOAL SYSTEM.
Menggunakan SQLite sebagai database transaksional utama dan menyinkronkan ke file JSON
terstruktur (matches.json, all_time.json, daily/YYYY-MM-DD.json, monthly/YYYY-MM.json)
dengan atomic write (tempfile + os.replace), file locking, backup otomatis, dan anti-duplikasi.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

try:
    import fcntl
except ImportError:
    fcntl = None  # Kompatibilitas sistem non-POSIX (fallback ke lockfile atomic)

from config import (
    ALL_TIME_JSON_PATH,
    BACKUP_DIR,
    DAILY_ARCHIVE_DIR,
    DEFAULT_STAKE,
    LOCK_FILE_PATH,
    MATCHES_JSON_PATH,
    MONTHLY_ARCHIVE_DIR,
    SCAN_META_JSON_PATH,
    SIMULATED_ODDS,
    SQLITE_DB_PATH,
    STRATEGY_MARKET,
    ensure_directories,
)
from parser import compute_trading_day, format_iso_utc_and_wita

REQUIRED_RECORD_FIELDS = [
    "match_id",
    "home_team",
    "away_team",
    "league",
    "league_slug",
    "kickoff_utc",
    "kickoff_wita",
    "detected_at_utc",
    "detected_at_wita",
    "trading_day",
    "minute_detected",
    "score_at_entry",
    "odds_entry",
    "odds_source",
    "stake",
    "source",
    "source_event_id",
    "snapshots",
    "goal_events",
    "current_score",
    "final_score",
    "match_status",
    "settlement_status",
    "result",
    "profit",
    "roi_contribution",
    "is_major",
    "created_at",
    "updated_at",
    "last_verified_at",
    "verification_status",
    "revision_history",
]


@contextmanager
def acquire_file_lock(lock_path: Path = LOCK_FILE_PATH, timeout: float = 15.0) -> Iterator[None]:
    """
    Mencegah dua proses menulis database secara bersamaan.
    Menggunakan fcntl.flock pada Linux/macOS dan atomic lockfile creation sebagai fallback.
    """
    ensure_directories()
    start_time = time.monotonic()
    lock_file = open(lock_path, "a+", encoding="utf-8")
    locked = False
    try:
        while True:
            try:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except (IOError, OSError):
                if (time.monotonic() - start_time) >= timeout:
                    raise TimeoutError(f"Could not acquire database lock at {lock_path} within {timeout}s")
                time.sleep(0.1)
        yield
    finally:
        if locked and fcntl is not None:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        lock_file.close()


def atomic_write_json(target_path: Path, data: Any, create_backup: bool = False) -> None:
    """
    Menulis data ke file JSON secara atomik:
    1. Validasi serialisasi JSON dan struktur kembali (json.loads).
    2. Buat backup jika file target sudah ada dan create_backup=True.
    3. Tulis ke temporary file pada direktori yang sama, flush + fsync, lalu os.replace().
    """
    ensure_directories()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    serialized = json.dumps(data, indent=2, ensure_ascii=False)
    # Validasi struktur JSON sebelum menyentuh disk
    json.loads(serialized)

    if create_backup and target_path.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_file = BACKUP_DIR / f"{target_path.stem}_{ts}.json.bak"
        shutil.copy2(target_path, backup_file)
        # Batasi jumlah file backup maksimal 30 file terbaru agar disk tetap bersih
        backups = sorted(BACKUP_DIR.glob(f"{target_path.stem}_*.bak"), key=lambda p: p.stat().st_mtime)
        while len(backups) > 30:
            oldest = backups.pop(0)
            try:
                oldest.unlink()
            except OSError:
                pass

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.",
        suffix=".tmp",
        dir=str(target_path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(serialized)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_name, target_path)
    except Exception:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        raise


def validate_record_schema(record: Dict[str, Any]) -> None:
    """Memastikan record memiliki seluruh field wajib sesuai spesifikasi Bagian F.2."""
    missing = [field for field in REQUIRED_RECORD_FIELDS if field not in record]
    if missing:
        raise ValueError(f"Record schema validation failed. Missing fields: {missing}")


class TradingDatabase:
    """
    Kelas operasional database utama dengan SQLite + Sinkronisasi Arsip JSON.
    Menjamin prinsip idempotent processing (1 match_id = maksimal 1 kandidat trading).
    """

    def __init__(self, db_path: Path = SQLITE_DB_PATH, matches_json_path: Path = MATCHES_JSON_PATH):
        self.db_path = db_path
        self.matches_json_path = matches_json_path
        ensure_directories()
        self._init_sqlite()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_sqlite(self) -> None:
        with acquire_file_lock():
            with self._get_conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS matches (
                        match_id TEXT PRIMARY KEY,
                        trading_day TEXT NOT NULL,
                        detected_at_utc TEXT NOT NULL,
                        settlement_status TEXT NOT NULL,
                        result TEXT NOT NULL,
                        league_slug TEXT NOT NULL,
                        is_major INTEGER NOT NULL,
                        record_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_trading_day ON matches(trading_day);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_settlement_status ON matches(settlement_status);"
                )
                conn.commit()

    def create_candidate_record(
        self,
        parsed_match: Dict[str, Any],
        detected_dt_utc: Optional[datetime] = None,
        stake: int = DEFAULT_STAKE,
    ) -> Dict[str, Any]:
        """
        Membangun struktur data kandidat trading baru sesuai Bagian F.2.
        Trading day ditetapkan saat ENTRY dan tidak pernah berubah saat FT.
        """
        now_dt = detected_dt_utc or datetime.now(timezone.utc)
        detected_utc, detected_wita = format_iso_utc_and_wita(now_dt)
        trading_day = compute_trading_day(now_dt)

        status_info = parsed_match["status"]
        clock_info = parsed_match["clock"]
        score_info = parsed_match["score"]
        goal_events = parsed_match.get("goal_events") or []

        minute_detected = int(clock_info["minute"])
        entry_score = score_info["formatted_score"]

        initial_snapshot = {
            "timestamp_utc": detected_utc,
            "timestamp_wita": detected_wita,
            "clock": clock_info.get("display_clock") or f"{minute_detected}'",
            "minute": minute_detected,
            "score": entry_score,
            "match_status": status_info["canonical_status"],
            "note": "ENTRY",
        }

        record: Dict[str, Any] = {
            "match_id": score_info["match_id"],
            "home_team": score_info["home_team"],
            "away_team": score_info["away_team"],
            "league": score_info["league"],
            "league_slug": score_info["league_slug"],
            "league_category": score_info.get("league_category", "UNKNOWN"),
            "market": STRATEGY_MARKET,
            "kickoff_utc": score_info["kickoff_utc"],
            "kickoff_wita": score_info["kickoff_wita"],
            "detected_at_utc": detected_utc,
            "detected_at_wita": detected_wita,
            "trading_day": trading_day,
            "minute_detected": minute_detected,
            "score_at_entry": entry_score,
            "odds_entry": score_info["odds_entry"],
            "simulated_odds": SIMULATED_ODDS,
            "odds_source": score_info["odds_source"],
            "stake": int(stake),
            "source": "ESPN_API",
            "source_event_id": score_info["source_event_id"],
            "is_provisional_id": bool(score_info.get("is_provisional_id", False)),
            "snapshots": [initial_snapshot],
            "goal_events": goal_events,
            "current_score": entry_score,
            "final_score": None,
            "match_status": status_info["canonical_status"],
            "settlement_status": "PENDING",
            "result": "PENDING",
            "profit": 0,
            "roi_contribution": 0.0,
            "simulated_profit": 0,
            "simulated_roi_contribution": 0.0,
            "actual_profit": 0 if score_info["odds_entry"] is not None else None,
            "actual_roi_contribution": 0.0 if score_info["odds_entry"] is not None else None,
            "is_major": bool(score_info["is_major"]),
            "created_at": detected_utc,
            "updated_at": detected_utc,
            "last_verified_at": detected_utc,
            "verification_status": "PROVISIONAL_ID" if score_info.get("is_provisional_id") else "VERIFIED_ENTRY",
            "revision_history": [],
        }
        validate_record_schema(record)
        return record

    def insert_candidate_idempotent(
        self,
        parsed_match: Dict[str, Any],
        detected_dt_utc: Optional[datetime] = None,
        stake: int = DEFAULT_STAKE,
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Menyimpan kandidat baru secara idempotent.
        Jika match_id sudah ada di database:
          - JANGAN membuat record baru.
          - JANGAN menggandakan stake atau profit.
          - Kembalikan (existing_record, False).
        Jika belum ada:
          - Simpan kandidat baru dan sinkronkan arsip JSON.
          - Kembalikan (new_record, True).
        """
        match_id = parsed_match["score"]["match_id"]
        with acquire_file_lock():
            existing = self._get_by_id_unlocked(match_id)
            if existing is not None:
                return existing, False

            new_record = self.create_candidate_record(
                parsed_match=parsed_match,
                detected_dt_utc=detected_dt_utc,
                stake=stake,
            )
            self._save_record_unlocked(new_record)
            self._sync_json_archives_unlocked()
            return new_record, True

    def update_existing_record(self, updated_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Memperbarui record yang sudah ada tanpa pernah mengubah `trading_day`,
        `detected_at_utc`, `minute_detected`, `score_at_entry`, atau `stake`.
        """
        validate_record_schema(updated_record)
        match_id = updated_record["match_id"]

        with acquire_file_lock():
            existing = self._get_by_id_unlocked(match_id)
            if existing is not None:
                # Kunci atribut historis saat entry agar tidak pernah berubah
                updated_record["trading_day"] = existing["trading_day"]
                updated_record["detected_at_utc"] = existing["detected_at_utc"]
                updated_record["detected_at_wita"] = existing["detected_at_wita"]
                updated_record["minute_detected"] = existing["minute_detected"]
                updated_record["score_at_entry"] = existing["score_at_entry"]
                updated_record["stake"] = existing["stake"]
                updated_record["created_at"] = existing["created_at"]

            self._save_record_unlocked(updated_record)
            self._sync_json_archives_unlocked()
            return updated_record

    def _get_by_id_unlocked(self, match_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT record_json FROM matches WHERE match_id = ?", (match_id,)
            ).fetchone()
            if not row:
                return None
            return json.loads(row["record_json"])

    def _save_record_unlocked(self, record: Dict[str, Any]) -> None:
        validate_record_schema(record)
        serialized = json.dumps(record, ensure_ascii=False)
        with self._get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
                INSERT INTO matches (
                    match_id, trading_day, detected_at_utc, settlement_status,
                    result, league_slug, is_major, record_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id) DO UPDATE SET
                    settlement_status = excluded.settlement_status,
                    result = excluded.result,
                    record_json = excluded.record_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record["match_id"],
                    record["trading_day"],
                    record["detected_at_utc"],
                    record["settlement_status"],
                    record["result"],
                    record["league_slug"],
                    1 if record["is_major"] else 0,
                    serialized,
                    record["updated_at"],
                ),
            )
            conn.commit()

    def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        with acquire_file_lock():
            return self._get_by_id_unlocked(match_id)

    def get_all_matches(self) -> List[Dict[str, Any]]:
        """Mengambil seluruh pertandingan diurutkan dari yang terbaru di bagian paling atas."""
        with acquire_file_lock():
            return self._get_all_unlocked()

    def _get_all_unlocked(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT record_json FROM matches ORDER BY detected_at_utc DESC, match_id DESC"
            ).fetchall()
            return [json.loads(r["record_json"]) for r in rows]

    def get_pending_matches(self) -> List[Dict[str, Any]]:
        """Mengambil pertandingan yang masih membutuhkan pemantauan atau rekonsiliasi."""
        with acquire_file_lock():
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT record_json FROM matches
                    WHERE settlement_status IN ('PENDING', 'REVIEW')
                    ORDER BY detected_at_utc DESC
                    """
                ).fetchall()
                return [json.loads(r["record_json"]) for r in rows]

    def _sync_json_archives_unlocked(self) -> None:
        """
        Menyinkronkan isi SQLite ke seluruh arsip JSON sesuai Bagian G:
        - data/matches.json
        - data/archive/all_time.json
        - data/archive/daily/YYYY-MM-DD.json
        - data/archive/monthly/YYYY-MM.json
        Semua diurutkan dengan pertandingan terbaru di bagian paling atas.
        """
        all_records = self._get_all_unlocked()
        now_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        envelope = {
            "system": "TRADING BOLA MENIT 60 - LAST GOAL SYSTEM",
            "version": "2.0",
            "last_updated_utc": now_utc_str,
            "total_records": len(all_records),
            "matches": all_records,
        }

        atomic_write_json(self.matches_json_path, envelope, create_backup=True)
        atomic_write_json(ALL_TIME_JSON_PATH, envelope, create_backup=False)

        # Partisi harian (berdasarkan trading_day cut-off 12:00 WITA)
        by_day: Dict[str, List[Dict[str, Any]]] = {}
        by_month: Dict[str, List[Dict[str, Any]]] = {}
        for rec in all_records:
            t_day = str(rec.get("trading_day") or "unknown")
            by_day.setdefault(t_day, []).append(rec)
            if len(t_day) >= 7:
                t_month = t_day[:7]
                by_month.setdefault(t_month, []).append(rec)

        for day_str, day_records in by_day.items():
            day_path = DAILY_ARCHIVE_DIR / f"{day_str}.json"
            atomic_write_json(
                day_path,
                {
                    "trading_day": day_str,
                    "last_updated_utc": now_utc_str,
                    "total_records": len(day_records),
                    "matches": day_records,
                },
                create_backup=False,
            )

        for month_str, month_records in by_month.items():
            month_path = MONTHLY_ARCHIVE_DIR / f"{month_str}.json"
            atomic_write_json(
                month_path,
                {
                    "trading_month": month_str,
                    "last_updated_utc": now_utc_str,
                    "total_records": len(month_records),
                    "matches": month_records,
                },
                create_backup=False,
            )


def save_scan_metadata(meta: Dict[str, Any]) -> None:
    """Menyimpan metadata pemindaian terakhir untuk dipantau oleh dashboard & health check."""
    with acquire_file_lock():
        atomic_write_json(SCAN_META_JSON_PATH, meta, create_backup=False)


def load_scan_metadata() -> Dict[str, Any]:
    """Membaca metadata pemindaian terakhir."""
    if not SCAN_META_JSON_PATH.exists():
        return {
            "scan_timestamp_utc": None,
            "source_status": "NEVER_SCANNED",
            "endpoints_queried": 0,
            "endpoints_succeeded": 0,
            "endpoints_failed": 0,
            "raw_events_received": 0,
            "matches_processed": 0,
            "matches_failed_parsing": 0,
        }
    try:
        with open(SCAN_META_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"scan_timestamp_utc": None, "source_status": "META_READ_ERROR"}
