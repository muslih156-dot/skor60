
import os, json, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WITA = timezone(timedelta(hours=8))

DATA_DIR = Path("data")
MATCHES_FILE = DATA_DIR / "matches.json"
ARCHIVE_DIR = DATA_DIR / "archive"

def wita_now():
    return datetime.now(WITA)

def send_telegram(pesan):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("TOKEN/CHAT_ID belum di set")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": pesan, "parse_mode": "HTML"}
        r = requests.post(url, data=data, timeout=10)
        print(f"Telegram status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error telegram: {e}")
        return False

def load_matches():
    if MATCHES_FILE.exists():
        try:
            with open(MATCHES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_matches(matches):
    DATA_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True, parents=True)
    with open(MATCHES_FILE, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    # Also save to all_time
    all_time_file = ARCHIVE_DIR / "all_time.json"
    # Load existing all_time
    all_matches = []
    if all_time_file.exists():
        try:
            with open(all_time_file, 'r', encoding='utf-8') as f:
                all_matches = json.load(f)
        except:
            all_matches = []
    # Merge
    seen = {str(m.get("match_id")): m for m in all_matches}
    for m in matches:
        mid = str(m.get("match_id"))
        if mid not in seen:
            seen[mid] = m
        else:
            # Update with newer data but keep score_deteksi
            old = seen[mid]
            # Preserve original detection score if exists
            if old.get("score_deteksi"):
                m["score_deteksi"] = old["score_deteksi"]
                m["minute_deteksi"] = old.get("minute_deteksi", old.get("minute", 60))
            seen[mid].update(m)
            # Ensure detection preserved
            if old.get("score_deteksi"):
                seen[mid]["score_deteksi"] = old["score_deteksi"]
    with open(all_time_file, 'w', encoding='utf-8') as f:
        json.dump(list(seen.values()), f, indent=2, ensure_ascii=False)

def cek_menit_60():
    """Scan Sofascore live events menit 60-66 skor 0-0"""
    try:
        url = "https://api.sofascore.com/api/v1/sport/football/events/live"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=15)
        data = r.json()
        out = []
        for ev in data.get("events", []):
            minute = ev.get("time", {}).get("minute", 0)
            hs = ev.get("homeScore", {}).get("current", 0)
            aws = ev.get("awayScore", {}).get("current", 0)
            status_type = ev.get("status", {}).get("type", "")
            status_desc = ev.get("status", {}).get("description", "")
            # Hanya inprogress dan menit 60-66 dan skor 0-0 (deteksi awal)
            if status_type == "inprogress" and 60 <= minute <= 66 and hs == 0 and aws == 0:
                # Filter liga besar? Untuk sekarang semua, nanti filter di dashboard
                out.append({
                    "id": str(ev["id"]),
                    "home": ev["homeTeam"]["name"],
                    "away": ev["awayTeam"]["name"],
                    "league": ev["tournament"]["name"],
                    "league_slug": ev["tournament"].get("slug",""),
                    "minute": minute,
                    "home_score": hs,
                    "away_score": aws,
                    "score": f"{hs}-{aws}",  # ini skor deteksi = 0-0
                    "status_type": status_type,
                    "status_desc": status_desc
                })
        return out
    except Exception as e:
        print(f"Error cek_menit_60: {e}")
        return []

def get_live_score(event_id):
    """Ambil skor live terbaru dari Sofascore"""
    try:
        url = f"https://api.sofascore.com/api/v1/event/{event_id}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()
        ev = data.get("event", {})
        hs = ev.get("homeScore", {}).get("current", 0)
        aws = ev.get("awayScore", {}).get("current", 0)
        minute = ev.get("time", {}).get("minute", 0)
        status_type = ev.get("status", {}).get("type", "")
        status_desc = ev.get("status", {}).get("description", "")
        return {
            "home_score": hs,
            "away_score": aws,
            "score": f"{hs}-{aws}",
            "minute": minute,
            "status_type": status_type,
            "status_desc": status_desc,
            "is_ft": status_type == "finished" or "FT" in status_desc or "Ended" in status_desc
        }
    except Exception as e:
        print(f"Error get_live_score {event_id}: {e}")
        return None

def get_stats(event_id):
    try:
        url = f"https://api.sofascore.com/api/v1/event/{event_id}/statistics"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()
        stats = {}
        for g in data.get("statistics", []):
            for s in g.get("groups", []):
                for it in s.get("statisticsItems", []):
                    if it["name"] in ["Total shots", "Shots on target", "Dangerous attacks", "Expected goals", "Ball possession"]:
                        stats[it["name"]] = {"home": it.get("homeValue", 0), "away": it.get("awayValue", 0)}
        return stats
    except:
        return {}

def analisa(stats):
    try:
        ts_h = int(str(stats.get("Total shots", {}).get("home", 0) or 0).split()[0] if isinstance(stats.get("Total shots", {}).get("home", 0), str) else stats.get("Total shots", {}).get("home", 0) or 0)
        ts_a = int(str(stats.get("Total shots", {}).get("away", 0) or 0).split()[0] if isinstance(stats.get("Total shots", {}).get("away", 0), str) else stats.get("Total shots", {}).get("away", 0) or 0)
        ts = ts_h + ts_a
    except:
        ts = 0
    try:
        da_h = int(stats.get("Dangerous attacks", {}).get("home", 0) or 0)
        da_a = int(stats.get("Dangerous attacks", {}).get("away", 0) or 0)
        da = da_h + da_a
    except:
        da = 0
    try:
        sot_h = int(stats.get("Shots on target", {}).get("home", 0) or 0)
        sot_a = int(stats.get("Shots on target", {}).get("away", 0) or 0)
        sot = sot_h + sot_a
    except:
        sot = 0
    
    if ts >= 12 and da >= 45 and sot >= 3:
        return f"AKTIF 🔥", ts, da, sot
    elif ts <= 6 and da <= 25:
        return f"PASIF 🥶", ts, da, sot
    else:
        return f"SEDANG 😐", ts, da, sot

def update_existing_matches():
    """Update skor live untuk match yang masih aktif, JANGAN overwrite skor deteksi"""
    matches = load_matches()
    updated = []
    now = wita_now()
    for m in matches:
        mid = str(m.get("match_id"))
        # Skip yang sudah FT dan sudah ada final_score lebih dari 2 jam lalu
        try:
            created = datetime.fromisoformat(m.get("created_at","").replace("+08:00","+08:00"))
            umur_jam = (now - created).total_seconds() / 3600
            if m.get("is_ft") and umur_jam > 3:
                updated.append(m)
                continue
        except:
            pass
        
        # Kalau masih aktif atau sedang, cek live score
        if not m.get("is_ft"):
            live = get_live_score(mid)
            if live:
                # PRESERVE skor deteksi asli!
                score_deteksi = m.get("score_deteksi", m.get("score", "0-0"))
                minute_deteksi = m.get("minute_deteksi", m.get("minute", 60))
                
                # Update live score, tapi JANGAN overwrite score_deteksi
                m["live_score"] = live["score"]
                m["current_score"] = live["score"]
                m["minute_live"] = live["minute"]
                m["status_type"] = live["status_type"]
                m["status_desc"] = live["status_desc"]
                m["is_ft"] = live["is_ft"]
                
                if live["is_ft"]:
                    m["final_score"] = live["score"]
                    # HITUNG WIN/LOSE BENAR: bandingkan FT vs deteksi
                    try:
                        hg_ft, ag_ft = map(int, live["score"].split("-"))
                        hg_det, ag_det = map(int, score_deteksi.split("-"))
                        total_ft = hg_ft + ag_ft
                        total_det = hg_det + ag_det
                        gol_setelah = total_ft - total_det
                        m["total_gol_setelah"] = gol_setelah
                        m["gol_terjadi"] = gol_setelah > 0
                        m["result"] = "WIN" if gol_setelah > 0 else "LOSE"
                        m["result_calc"] = m["result"]
                        print(f"FT {mid}: deteksi {score_deteksi} -> FT {live['score']} = gol setelah {gol_setelah} => {m['result']}")
                    except Exception as e:
                        print(f"Error hitung gol {mid}: {e}")
                        m["result"] = "LOSE"
                else:
                    # Masih live
                    m["final_score"] = None
                
                # Preserve deteksi
                m["score_deteksi"] = score_deteksi
                m["minute_deteksi"] = minute_deteksi
                # Score field tetap deteksi untuk kompatibilitas, tapi kita punya live_score juga
                # Jangan overwrite m["score"] dengan live, biar tetap 0-0
            else:
                # Gagal fetch, cek umur
                try:
                    created = datetime.fromisoformat(m.get("created_at",""))
                    umur_menit = (now - created).total_seconds() / 60
                    if umur_menit > 120 and not m.get("final_score"):
                        # Sudah 2 jam, anggap FT 0-0 kalau belum ada update
                        m["is_ft"] = True
                        m["final_score"] = m.get("live_score", "0-0")
                        m["result"] = "LOSE"
                        m["result_calc"] = "LOSE"
                        m["gol_terjadi"] = False
                except:
                    pass
        
        updated.append(m)
    
    return updated

if __name__ == "__main__":
    print(f"=== Check Menit 60-66 - {wita_now().strftime('%d %b %Y %H:%M WITA')} ===")
    
    # 1. Update existing matches dulu (live score -> FT)
    existing = update_existing_matches()
    print(f"Existing matches updated: {len(existing)}")
    
    # 2. Scan new matches
    new_matches = cek_menit_60()
    print(f"Found {len(new_matches)} new match 0-0 di menit 60-66")
    
    # Filter yang belum ada
    existing_ids = set(str(m.get("match_id")) for m in existing)
    to_add = []
    for nm in new_matches:
        if nm["id"] not in existing_ids:
            stats = get_stats(nm["id"])
            status_text, ts, da, sot = analisa(stats)
            
            match_data = {
                "match_id": nm["id"],
                "home_team": nm["home"],
                "away_team": nm["away"],
                "league": nm["league"],
                "league_slug": nm["league_slug"],
                "minute": nm["minute"],
                "minute_deteksi": nm["minute"],
                "score": "0-0",  # skor deteksi selalu 0-0
                "score_deteksi": "0-0",
                "live_score": "0-0",
                "current_score": "0-0",
                "final_score": None,
                "status": status_text,
                "status_calc": "AKTIF",
                "shots": ts,
                "da": da,
                "sot": sot,
                "created_at": wita_now().isoformat(),
                "wita_date": wita_now().strftime("%Y-%m-%d"),
                "is_ft": False,
                "result": "LIVE",
                "result_calc": "LIVE",
                "gol_terjadi": None,
                "total_gol_setelah": 0,
                "odds": round(1.46 + (da % 40) / 100, 2),  # odds dummy 1.46-1.86
                "odds_calc": round(1.46 + (da % 40) / 100, 2)
            }
            to_add.append(match_data)
            
            pesan = f"""⚽ <b>MENIT 60 - 0-0 DETEKSI</b>

🏟️ {nm['home']} vs {nm['away']}
🏆 {nm['league']}
⏱️ Menit {nm['minute']} - Skor {nm['score']} (deteksi)

📊 {status_text}
Shots {ts} | DA {da} | SoT {sot}

💰 BET: Rp 50rb | ODDS: {match_data['odds']} | PASAR: Over 0.5 Goal
ID: {nm['id']} | {wita_now().strftime('%H:%M WITA')}"""
            send_telegram(pesan)
            print(f"Added: {nm['home']} vs {nm['away']} - {status_text}")
    
    # Gabung
    all_matches = existing + to_add
    # Sort by created_at desc
    try:
        all_matches = sorted(all_matches, key=lambda x: x.get("created_at",""), reverse=True)
    except:
        pass
    
    # Keep only last 100
    all_matches = all_matches[:100]
    
    save_matches(all_matches)
    print(f"Total matches saved: {len(all_matches)} - New: {len(to_add)}")
    print("Done")
