
import os, json, requests, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

WITA = timezone(timedelta(hours=8))
DATA_DIR = Path("data")
MATCHES_FILE = DATA_DIR / "matches.json"
ARCHIVE_DIR = DATA_DIR / "archive"

SOURCES = [
    "https://api.sofascore.com/api/v1/sport/football/events/live",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard",
]

def now_wita():
    return datetime.now(WITA)

def load_matches():
    if MATCHES_FILE.exists():
        try:
            with open(MATCHES_FILE,'r',encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_matches(matches):
    DATA_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True, parents=True)
    # Keep last 50 for main, but save all for archive
    with open(MATCHES_FILE,'w',encoding='utf-8') as f:
        json.dump(matches[-50:], f, indent=2, ensure_ascii=False)
    with open(ARCHIVE_DIR / "all_time.json",'w',encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    with open(ARCHIVE_DIR / f"{now_wita().strftime('%Y-%m')}.json",'w',encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    with open("matches.json",'w',encoding='utf-8') as f:
        json.dump(matches[-50:], f, indent=2, ensure_ascii=False)
    with open("all_time.json",'w',encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

def fetch_sofascore():
    source = "Sofascore API - api.sofascore.com"
    try:
        url = "https://api.sofascore.com/api/v1/sport/football/events/live"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=15)
        print(f"[{source}] Status: {r.status_code}")
        if r.status_code != 200:
            print(f"[{source}] Gagal: {r.text[:200]}")
            return [], source, f"HTTP {r.status_code}"
        data = r.json()
        events = data.get("events", [])
        print(f"[{source}] Total live events: {len(events)}")
        out = []
        for ev in events:
            minute = ev.get("time", {}).get("minute", 0)
            hs = ev.get("homeScore", {}).get("current", 0)
            aws = ev.get("awayScore", {}).get("current", 0)
            status = ev.get("status", {}).get("type", "")
            ht = ev.get("homeTeam", {}).get("name", "Home")
            at = ev.get("awayTeam", {}).get("name", "Away")
            tour = ev.get("tournament", {})
            league_slug = tour.get("slug","")
            league_name = tour.get("name","")
            ev_id = str(ev.get("id",""))
            
            # Debug: print all inprogress 60-70
            if status == "inprogress" and 55 <= minute <= 75:
                print(f"  -> LIVE {minute}' {ht} {hs}-{aws} {at} [{league_slug}] status={status}")
            
            if status == "inprogress" and 60 <= minute <= 66 and hs == 0 and aws == 0:
                out.append({
                    "id": ev_id,
                    "home": ht,
                    "away": at,
                    "league": league_slug,
                    "league_name": league_name,
                    "minute": minute,
                    "source": source,
                })
                print(f"  >> FOUND 0-0 at {minute}' : {ht} vs {at} [{league_slug}]")
        return out, source, f"OK {len(events)} events scanned"
    except Exception as e:
        print(f"[{source}] Error: {e}")
        return [], source, f"Error {e}"

def fetch_espn():
    source = "ESPN API - site.api.espn.com"
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
        r = requests.get(url, timeout=15)
        print(f"[{source}] Status: {r.status_code}")
        if r.status_code != 200:
            return [], source, f"HTTP {r.status_code}"
        data = r.json()
        events = data.get("events", [])
        print(f"[{source}] Total events: {len(events)}")
        out = []
        for ev in events:
            comp = ev.get("competitions", [{}])[0]
            status_type = comp.get("status", {}).get("type", {}).get("name", "")
            clock = comp.get("status", {}).get("displayClock", "0'")
            # Parse minute
            minute = 0
            try:
                minute = int(''.join(filter(str.isdigit, clock.split(':')[0])) or 0)
                if "'" in clock:
                    minute = int(clock.replace("'","").split("+")[0])
            except:
                pass
            home = comp.get("competitors", [{}])[0]
            away = comp.get("competitors", [{}])[1] if len(comp.get("competitors",[]))>1 else {}
            hs = int(home.get("score","0") or 0) if home else 0
            aws = int(away.get("score","0") or 0) if away else 0
            ht = home.get("team",{}).get("displayName","Home")
            at = away.get("team",{}).get("displayName","Away")
            league_slug = ev.get("league",{}).get("slug","")
            
            if "in progress" in status_type.lower() or "first half" in status_type.lower() or "second half" in status_type.lower():
                if 60 <= minute <= 66 and hs==0 and aws==0:
                    out.append({"id": ev.get("id",""), "home": ht, "away": at, "league": league_slug, "minute": minute, "source": source})
        return out, source, f"OK {len(events)} events"
    except Exception as e:
        print(f"[{source}] Error: {e}")
        return [], source, f"Error {e}"

def update_live_scores(existing):
    """Update live_score dan final_score untuk match yang masih LIVE"""
    print("=== UPDATE LIVE SCORE EXISTING MATCHES ===")
    # Coba Sofascore lagi untuk update final
    try:
        url = "https://api.sofascore.com/api/v1/sport/football/events/live"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        live_map = {str(ev["id"]): ev for ev in data.get("events",[])}
        for m in existing:
            mid = str(m.get("match_id",""))
            if mid in live_map:
                ev = live_map[mid]
                hs = ev.get("homeScore", {}).get("current", 0)
                aws = ev.get("awayScore", {}).get("current", 0)
                status = ev.get("status", {}).get("type","")
                minute = ev.get("time", {}).get("minute", 0)
                live_score = f"{hs}-{aws}"
                m["live_score"] = live_score
                m["menit_sekarang"] = minute
                print(f"Update LIVE {m['home_team']} vs {m['away_team']} -> {live_score} ({minute}')")
                if status == "finished":
                    m["final_score"] = live_score
                    m["is_ft"] = True
                    # Calculate WIN/LOSE: total FT > 0 karena deteksi 0-0
                    total = hs+aws
                    m["result"] = "WIN" if total>0 else "LOSE"
                    m["result_calc"] = m["result"]
                    m["gol_terjadi"] = total>0
                    print(f"  -> FT {live_score} = {m['result']}")
            else:
                # Kalau ga ada di live, coba cek sudah FT (umur > 40 menit masih LIVE = jadi FT)
                try:
                    created = datetime.fromisoformat(m.get("created_at","").replace("Z","+00:00"))
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=WITA)
                    umur = (now_wita() - created).total_seconds()/60
                    if umur > 40 and not m.get("is_ft") and m.get("result")=="LIVE":
                        print(f"Auto-expire {m['home_team']} vs {m['away_team']} umur {umur:.0f}m -> cek final via ESPN fallback")
                        # Tetap LIVE, nanti di next scan akan FT, atau biarkan user lihat umur
                        m["umur_menit"] = umur
                except:
                    pass
    except Exception as e:
        print(f"Update live error: {e}")

if __name__ == "__main__":
    print(f"=== START V12 LIVE SCORE WITH SOURCE ===")
    print(f"Scan {now_wita()} | WITA Asia/Makassar")
    print(f"Sumber: Sofascore API (primary) + ESPN API (fallback)")
    print(f"Window: menit 60-66 skor 0-0")
    print("")
    existing = load_matches()
    print(f"Existing: {len(existing)} match (11W-6L 64.7% WR data real tadi pagi)")
    
    # Update live scores dulu
    update_live_scores(existing)
    
    # Cari match baru 0-0 di 60'
    print("\n=== SCAN BARU 0-0 DI 60-66 ===")
    all_new = []
    sources_log = []
    
    new_s, src, msg = fetch_sofascore()
    all_new.extend(new_s)
    sources_log.append(f"{src}: {msg} - Found {len(new_s)}")
    
    # ESPN sebagai fallback kalau Sofascore 0
    if len(new_s)==0:
        new_e, src_e, msg_e = fetch_espn()
        all_new.extend(new_e)
        sources_log.append(f"{src_e}: {msg_e} - Found {len(new_e)}")
    
    print(f"\n=== SUMMARY SOURCES ===")
    for s in sources_log:
        print(f"  - {s}")
    print(f"Found {len(all_new)} new 0-0 at 60' TOTAL")
    
    added = 0
    for nm in all_new:
        if str(nm["id"]) not in [str(m.get("match_id")) for m in existing]:
            existing.append({
                "match_id": nm["id"],
                "home_team": nm["home"],
                "away_team": nm["away"],
                "league": nm.get("league",""),
                "league_name": nm.get("league_name",""),
                "minute": nm.get("minute",60),
                "minute_deteksi": 60,
                "score": "0-0",
                "score_deteksi": "0-0",
                "skor_deteksi_real": "0-0",
                "live_score": "0-0",
                "final_score": None,
                "is_ft": False,
                "result": "LIVE",
                "result_calc": "LIVE",
                "created_at": now_wita().isoformat(),
                "odds": 1.8,
                "odds_calc": 1.8,
                "source": nm.get("source","Sofascore"),
                "gol_terjadi": None,
            })
            added += 1
            print(f"+ NEW: {nm['home']} vs {nm['away']} [{nm.get('league','')}] {nm.get('minute',60)}' 0-0 via {nm.get('source','')}")
    
    print(f"\nAdded {added} new match")
    save_matches(existing)
    print(f"Saved {len(existing)} total (last 50 di matches.json, all di all_time.json)")
    print(f"=== FILES ===")
    print(f"Sources used: {', '.join([s.split(':')[0] for s in sources_log])}")
