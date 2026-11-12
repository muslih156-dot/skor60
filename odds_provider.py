# odds_provider.py - V3 FINAL: Tanpa 1.80 Sim lagi
# Urutan: Actual -> Est dari API -> Est dari Liga -> Est Global
import os
import math
import urllib.request
import urllib.parse
import json
import glob

API_KEY = os.environ.get("ODDS_API_KEY", "")

# Rata-rata gol per match per liga, dari data umum. Ini buat fallback kalau liga belum ada di DB kita.
# Nanti ini bakal ke-update otomatis dari DB kita sendiri.
LEAGUE_LAMBDA_DEFAULT = {
    "brazilian serie b": 2.15,
    "brazilian serie a": 2.25,
    "premier league": 2.75,
    "la liga": 2.60,
    "serie a": 2.55,
    "bundesliga": 3.10,
    "ligue 1": 2.65,
    "eredivisie": 3.05,
    "portuguese primeira liga": 2.50,
    "mls": 2.85,
    "j league": 2.60,
    "k league": 2.45,
    "default": 2.45,  # Global, kalau liga unknown
    "unknown league": 2.45,
}

def _poisson_over_prob(lam_sisa):
    return 1 - math.exp(-lam_sisa)

def _lambda_to_odds(lam_total):
    """Rumus hitung manual yang bapak setujui kemarin"""
    # Sisa 30 menit dari 90 menit = 1/3, + boost 1.15 karena 0-0 di menit 60 tim ngotot
    lam_sisa = lam_total * (30.0 / 90.0) * 1.15
    p_gol = _poisson_over_prob(lam_sisa)
    if p_gol <= 0.05 or p_gol >= 0.95:
        p_gol = max(0.10, min(0.90, p_gol))
    odds_fair = 1.0 / p_gol
    odds_pasar = odds_fair / 1.07  # Margin bandar 7%
    return round(max(1.15, min(3.50, odds_pasar)), 2)

def _estimate_lambda_from_api(bookmakers):
    """Hitung lambda dari odds pre-match Over 1.5, 2.5, 3.5 di The Odds API"""
    points = []
    for bm in bookmakers:
        for m in bm.get("markets", []):
            if m.get("key") != "totals":
                continue
            for o in m.get("outcomes", []):
                if o.get("name") == "Over":
                    try:
                        points.append((float(o.get("point")), 1.0 / float(o.get("price"))))
                    except:
                        pass
    if not points:
        return None
    best_lambda, best_error = None, 999
    lam = 0.5
    while lam <= 5.0:
        err = 0
        for point, prob_real in points:
            k = int(point)
            cdf = 0
            for i in range(k + 1):
                cdf += (math.exp(-lam) * (lam ** i) / math.factorial(i))
            prob_model = 1 - cdf
            err += (prob_model - prob_real) ** 2
        if err < best_error:
            best_error, best_lambda = err, lam
        lam += 0.1
    return best_lambda

def _estimate_lambda_from_league_history(league_name):
    """
    HITUNG MANUAL TANPA API: Baca database kita sendiri (data/*.json)
    Cari semua match yang udah selesai di liga yang sama, hitung rata-rata golnya.
    Kalau liga itu udah ada 20 match di DB kita, itu jauh lebih akurat dari tabel default.
    """
    try:
        league_key = str(league_name or "").lower().strip()
        total_goals = 0
        total_matches = 0
        # Cari file data di folder data/
        for fpath in glob.glob("data/*.json") + glob.glob("data/**/*.json", recursive=True):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Format data bisa list atau dict, kita handle dua-duanya
                records = []
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict):
                    records = data.get("records", []) or data.get("matches", []) or list(data.values())
                for rec in records:
                    if not isinstance(rec, dict):
                        continue
                    rec_league = str(rec.get("league", "")).lower()
                    if rec_league != league_key:
                        continue
                    # Ambil skor akhir dari berbagai format field
                    score_str = str(rec.get("final_score", "") or rec.get("current_score", "") or rec.get("score", ""))
                    if "-" in score_str:
                        try:
                            a, b = score_str.replace(" ", "").split("-")[:2]
                            total_goals += int(a) + int(b)
                            total_matches += 1
                        except:
                            pass
            except:
                continue
        if total_matches >= 5:  # Minimal 5 match biar bisa dipercaya
            lam = total_goals / total_matches
            # Kalau datanya aneh, clamp biar nggak ngaco
            return max(1.2, min(4.0, lam)), total_matches
        return None, total_matches
    except Exception as e:
        print(f"[odds] gagal baca history liga: {e}")
        return None, 0

def get_odds_with_fallback(home_team, away_team, league_name="Unknown League"):
    """
    Fungsi utama baru. Ini yang dipanggil check_once.py.
    SELALU return odds, nggak pernah return None lagi. Jadi 1.80 Sim hilang.
    """
    # --- TIER 1 & 2: Coba Odds API dulu ---
    if API_KEY:
        try:
            url = (
                "https://api.the-odds-api.com/v4/sports/soccer/odds/?"
                + urllib.parse.urlencode({
                    "apiKey": API_KEY,
                    "regions": "eu,uk",
                    "markets": "totals",
                    "oddsFormat": "decimal",
                })
            )
            req = urllib.request.Request(url, headers={"User-Agent": "skor60"})
            with urllib.request.urlopen(req, timeout=15) as r:
                # Cek kuota habis: kalau header sisa 0, langsung lempar ke fallback
                remaining = r.headers.get("x-requests-remaining")
                if remaining is not None and float(remaining) <= 0:
                    raise Exception("Kuota Odds API habis")
                data = json.loads(r.read().decode("utf-8"))

            home = str(home_team).lower()
            away = str(away_team).lower()
            for ev in data:
                ev_home = str(ev.get("home_team", "")).lower()
                ev_away = str(ev.get("away_team", "")).lower()
                if home[:5] in ev_home and away[:5] in ev_away:
                    # Tier 1: Over 0.5 langsung
                    for bm in ev.get("bookmakers", []):
                        for m in bm.get("markets", []):
                            if m.get("key") == "totals":
                                for o in m.get("outcomes", []):
                                    if o.get("name") == "Over" and float(o.get("point", 99)) == 0.5:
                                        return {"odds": float(o.get("price")), "source": f"Actual - {bm.get('title')}", "type": "Actual"}
                    # Tier 2: Hitung manual dari pre-match
                    lam = _estimate_lambda_from_api(ev.get("bookmakers", []))
                    if lam:
                        return {"odds": _lambda_to_odds(lam), "source": f"Est - API (lam={lam:.1f})", "type": "Est"}
            # Kalau match nggak ketemu di API, lanjut ke Tier 3 di bawah, jangan return None
            print(f"[odds] {home_team} vs {away_team} nggak ada di Odds API, pakai hitung manual Liga")
        except Exception as e:
            # Ini yang bapak mau: kuota habis / API error / 429 -> langsung hitung manual, nggak balik ke Sim
            print(f"[odds] API gagal / kuota habis ({e}), pakai hitung manual Liga")

    # --- TIER 3: Hitung manual dari history liga kita sendiri (TANPA API, TANPA KUOTA) ---
    lam_liga, n_match = _estimate_lambda_from_league_history(league_name)
    if lam_liga:
        odds = _lambda_to_odds(lam_liga)
        return {"odds": odds, "source": f"Est - Liga {league_name} ({n_match} match, lam={lam_liga:.1f})", "type": "Est"}

    # --- TIER 4: Hitung manual dari tabel default (kalau liga bener-bener baru) ---
    league_key = str(league_name or "").lower().strip()
    lam_default = LEAGUE_LAMBDA_DEFAULT.get(league_key, LEAGUE_LAMBDA_DEFAULT["default"])
    odds = _lambda_to_odds(lam_default)
    return {"odds": odds, "source": f"Est - Global (lam={lam_default:.1f})", "type": "Est"}

# Biar file lama yang masih manggil nama lama nggak error
def get_live_over_05_odds(home_team, away_team, league_name="Unknown League"):
    return get_odds_with_fallback(home_team, away_team, league_name)
