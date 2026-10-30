"""
config.py
Konfigurasi terpusat untuk TRADING BOLA MENIT 60 – LAST GOAL SYSTEM.
Seluruh parameter strategi, daftar liga, batas waktu, dan path penyimpanan
didefinisikan di sini agar mudah diaudit dan diperbarui tanpa mengubah logika inti.
"""

import os
from pathlib import Path
from typing import Dict, List, Set

# =====================================================================
# 1. KONFIGURASI MODAL, ODDS, DAN ZONA WAKTU
# =====================================================================
DEFAULT_STAKE: int = 50_000
SIMULATED_ODDS: float = 1.80
CURRENCY: str = "IDR"
TIMEZONE_NAME: str = "Asia/Makassar"  # WITA (UTC+8)
TRADING_DAY_CUTOFF_HOUR: int = 12     # Cut-off pukul 12:00 WITA

# =====================================================================
# 2. PARAMETER STRATEGI DETEKSI KANDIDAT
# =====================================================================
STRATEGY_MARKET: str = "OVER 0.5 GOAL AFTER ENTRY"
ENTRY_MINUTE_MIN: int = 60
ENTRY_MINUTE_MAX: int = 66
REQUIRED_PERIOD: int = 2
REQUIRED_ENTRY_HOME_SCORE: int = 0
REQUIRED_ENTRY_AWAY_SCORE: int = 0

# Ambang batas ukuran sampel statistik
MIN_SAMPLE_SIZE_RELIABLE: int = 30
WILSON_Z_SCORE_95: float = 1.959963984540054  # 95% confidence interval

# =====================================================================
# 3. KONFIGURASI API ESPN & RETRY
# =====================================================================
ESPN_BASE_URL: str = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_ALL_SCOREBOARD_URL: str = f"{ESPN_BASE_URL}/all/scoreboard"
ESPN_LEAGUE_SCOREBOARD_TEMPLATE: str = f"{ESPN_BASE_URL}/{{league_slug}}/scoreboard"
ESPN_SUMMARY_TEMPLATE: str = f"{ESPN_BASE_URL}/{{league_slug}}/summary?event={{match_id}}"

API_TIMEOUT_SECONDS: int = 15
API_MAX_RETRIES: int = 3
API_BACKOFF_BASE_SECONDS: float = 1.5
USER_AGENT: str = (
    "Mozilla/5.0 (compatible; Skor60TradingSystem/2.0; +https://github.com/muslih156-dot/skor60)"
)

# =====================================================================
# 4. KLASIFIKASI LIGA (MAJOR, MINOR, UNKNOWN)
# =====================================================================
MAJOR_LEAGUES_BY_REGION: Dict[str, List[str]] = {
    "Eropa": [
        "eng.1",
        "esp.1",
        "ita.1",
        "ger.1",
        "fra.1",
        "ned.1",
        "por.1",
        "bel.1",
        "tur.1",
    ],
    "Amerika": [
        "usa.1",
        "mex.1",
        "bra.1",
        "arg.1",
    ],
    "Asia": [
        "jpn.1",
        "kor.1",
        "aus.1",
        "saud.1",
    ],
    "Internasional": [
        "uefa.champions",
        "uefa.europa",
        "conmebol.libertadores",
        "afc.champions",
    ],
}

MAJOR_LEAGUE_SLUGS: Set[str] = {
    slug
    for slugs in MAJOR_LEAGUES_BY_REGION.values()
    for slug in slugs
}

# Daftar liga divisi kedua / piala domestik yang terverifikasi sebagai MINOR
MINOR_LEAGUE_SLUGS: Set[str] = {
    "eng.2", "eng.3", "eng.4", "eng.fa", "eng.league_cup",
    "esp.2", "esp.copa_del_rey",
    "ita.2", "ita.coppa_italia",
    "ger.2", "ger.dfb_pokal",
    "fra.2", "fra.coupe_de_france",
    "ned.2", "por.2", "bel.2", "tur.2",
    "usa.2", "mex.2", "bra.2", "arg.2",
    "jpn.2", "kor.2", "idn.1", "tha.1", "mys.1", "sgp.1",
    "uefa.europa.conf", "conmebol.sudamericana",
}

# Daftar liga yang dipindai secara aktif pada ESPN MULTI LEAGUE
ACTIVE_SCAN_LEAGUES: List[str] = sorted(list(MAJOR_LEAGUE_SLUGS))


def classify_league_slug(league_slug: str) -> str:
    """
    Mengklasifikasikan liga berdasarkan slug resmi ESPN.
    Prioritas utama adalah exact match pada slug, bukan pencarian kata longgar.
    Mengembalikan: 'MAJOR', 'MINOR', atau 'UNKNOWN'.
    """
    if not league_slug or not isinstance(league_slug, str):
        return "UNKNOWN"
    clean_slug = league_slug.strip().lower()
    if clean_slug in MAJOR_LEAGUE_SLUGS:
        return "MAJOR"
    if clean_slug in MINOR_LEAGUE_SLUGS:
        return "MINOR"
    return "UNKNOWN"


# =====================================================================
# 5. PATH DIREKTORI DAN FILE PENYIMPANAN
# =====================================================================
BASE_DIR: Path = Path(os.environ.get("SKOR60_BASE_DIR", Path(__file__).resolve().parent))
DATA_DIR: Path = BASE_DIR / "data"
ARCHIVE_DIR: Path = DATA_DIR / "archive"
DAILY_ARCHIVE_DIR: Path = ARCHIVE_DIR / "daily"
MONTHLY_ARCHIVE_DIR: Path = ARCHIVE_DIR / "monthly"
BACKUP_DIR: Path = DATA_DIR / "backups"
LOG_DIR: Path = DATA_DIR / "logs"

SQLITE_DB_PATH: Path = DATA_DIR / "trading.db"
MATCHES_JSON_PATH: Path = DATA_DIR / "matches.json"
ALL_TIME_JSON_PATH: Path = ARCHIVE_DIR / "all_time.json"
SCAN_META_JSON_PATH: Path = DATA_DIR / "scan_meta.json"
LOCK_FILE_PATH: Path = DATA_DIR / ".db.lock"
ERROR_LOG_PATH: Path = LOG_DIR / "system_errors.log"


def ensure_directories() -> None:
    """Memastikan seluruh direktori data, arsip, backup, dan log tersedia."""
    for folder in (
        DATA_DIR,
        ARCHIVE_DIR,
        DAILY_ARCHIVE_DIR,
        MONTHLY_ARCHIVE_DIR,
        BACKUP_DIR,
        LOG_DIR,
    ):
        folder.mkdir(parents=True, exist_ok=True)
