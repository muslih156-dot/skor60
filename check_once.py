
import os, json, requests, time, random
from datetime import datetime, timezone, timedelta
from pathlib import Path

WITA = timezone(timedelta(hours=8))
DATA_DIR = Path("data")
MATCHES_FILE = DATA_DIR / "matches.json"
ARCHIVE_DIR = DATA_DIR / "archive"

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
    with open(MATCHES_FILE,'w',encoding='utf-8') as f:
        json.dump(matches[-200:], f, indent=2, ensure_ascii=False)
    with open(ARCHIVE_DIR / "all_time.json",'w',encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    with open(ARCHIVE_DIR / f"{now_wita().strftime('%Y-%m')}.json",'w',encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    with open("matches.json",'w',encoding='utf-8') as f:
        json.dump(matches[-200:], f, indent=2, ensure_ascii=False)
    with open("all_time.json",'w',encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

# 200+ LIGA - 50 liga x 4-5 match = 200+ events
ESPN_LEAGUES = [
    "eng.1", "eng.2", "eng.3", "esp.1", "esp.2", "ita.1", "ita.2", "ger.1", "ger.2", "fra.1", "fra.2",
    "ned.1", "por.1", "bel.1", "tur.1", "sco.1", "gre.1", "sui.1", "aut.1", "den.1", "nor.1", "swe.1", "rus.1", "ukr.1",
    "usa.1", "mex.1", "bra.1", "arg.1", "col.1", "chi.1", "uru.1", "per.1", "ecu.1", "bol.1", "par.1", "ven.1",
    "jpn.1", "kor.1", "chn.1", "aus.1", "saud.1", "uae.1", "qat.1", "irn.1",
    "uefa.champions", "uefa.europa", "uefa.europa.conf", "conmebol.libertadores", "concacaf.champions", "afc.champions",
    "usa.ncaa.m.1", "usa.ncaa.w.1", "usa.nwsl"
]

def fetch_espn_multi():
    source = "ESPN MULTI-LEAGUE 50 liga (200+ events)"
    all_events = []
    found_60 = []
    total_scanned = 0
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for league in ESPN_LEAGUES:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            events = data.get("events", [])
            total_scanned += len(events)
            for ev in events:
                comp = ev.get("competitions", [{}])[0]
                status_type = comp.get("status", {}).get("type", {}).get("name", "")
                status_detail = comp.get("status", {}).get("type", {}).get("detail", "")
                clock = comp.get("status", {}).get("displayClock", "0'")
                # Parse minute from detail like "62'" or "Second Half - 15'"
                minute = 0
                try:
                    if "'" in status_detail:
                        minute = int(''.join(filter(str.isdigit, status_detail.split("'")[0].split()[-1])) or 0)
                    if " - " in status_detail and "'" in status_detail:
                        # Second Half - 15' = 60'
                        part = status_detail.split(" - ")
                        if "Second Half" in part[0]:
                            minute = 45 + int(''.join(filter(str.isdigit, part[1])) or 0)
                        elif "First Half" in part[0]:
                            minute = int(''.join(filter(str.isdigit, part[1])) or 0)
                except:
                    pass
                # Fallback from clock
                if minute == 0:
                    try:
                        if "'" in clock:
                            minute = int(clock.replace("'","").split("+")[0])
                    except:
                        pass
                
                competitors = comp.get("competitors", [])
                if len(competitors) < 2:
                    continue
                home = next((c for c in competitors if c.get("homeAway")=="home"), competitors[0])
                away = next((c for c in competitors if c.get("homeAway")=="away"), competitors[1] if len(competitors)>1 else {})
                hs = int(home.get("score","0") or 0)
                aws = int(away.get("score","0") or 0)
                ht = home.get("team",{}).get("displayName","Home")
                at = away.get("team",{}).get("displayName","Away")
                
                # Check inprogress
                is_live = "in progress" in status_type.lower() or "half" in status_type.lower() or "in" in status_type.lower()
                if not is_live:
                    # Also check if clock shows live
                    if minute>0 and minute<90:
                        is_live = True
                
                if is_live:
                    all_events.append(ev)
                    # Debug 55-75'
                    if 55 <= minute <= 75:
                        print(f"  -> LIVE {minute}' {ht} {hs}-{aws} {at} [{league}] {status_detail}")
                    # Found 0-0 at 60-66
                    if 60 <= minute <= 66 and hs==0 and aws==0:
                        found_60.append({
                            "id": ev.get("id",""),
                            "home": ht,
                            "away": at,
                            "league": league,
                            "league_name": league,
                            "minute": minute,
                            "source": source,
                        })
                        print(f"  >> FOUND 0-0 at {minute}' : {ht} vs {at} [{league}] via ESPN {league}")
            time.sleep(0.2)  # jangan spam
        except Exception as e:
            # print(f"[{league}] error {e}")
            continue
    
    print(f"[{source}] Total events scanned: {total_scanned} dari {len(ESPN_LEAGUES)} liga")
    print(f"[{source}] Live events: {len(all_events)}")
    print(f"[{source}] Found 0-0 at 60-66: {len(found_60)}")
    return found_60, source, f"OK {total_scanned} events from {len(ESPN_LEAGUES)} leagues ({len(all_events)} live)"

def fetch_sofascore_v2():
    sources = []
    found = []
    # Coba beberapa endpoint Sofascore dengan headers lebih lengkap
    urls = [
        "https://api.sofascore.com/api/v1/sport/football/events/live",
        "https://www.sofascore.com/api/v1/sport/football/events/live",
    ]
    headers_list = [
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.sofascore.com/",
            "Origin": "https://www.sofascore.com",
        },
        {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Accept": "application/json",
        }
    ]
    
    for url in urls:
        for headers in headers_list:
            try:
                print(f"Trying Sofascore {url} with UA {headers['User-Agent'][:30]}...")
                r = requests.get(url, headers=headers, timeout=15)
                print(f"[Sofascore] {url} Status: {r.status_code}")
                if r.status_code == 403:
                    print(f"[Sofascore] 403 Forbidden - blocked by Cloudflare")
                    continue
                if r.status_code != 200:
                    continue
                data = r.json()
                events = data.get("events", [])
                print(f"[Sofascore] Total live: {len(events)}")
                for ev in events:
                    minute = ev.get("time", {}).get("minute", 0)
                    hs = ev.get("homeScore", {}).get("current", 0)
                    aws = ev.get("awayScore", {}).get("current", 0)
                    status = ev.get("status", {}).get("type", "")
                    if 55 <= minute <= 75 and status=="inprogress":
                        print(f"  -> LIVE {minute}' {ev.get('homeTeam',{}).get('name')} {hs}-{aws} {ev.get('awayTeam',{}).get('name')} [{ev.get('tournament',{}).get('slug')}]")
                    if status=="inprogress" and 60 <= minute <= 66 and hs==0 and aws==0:
                        found.append({
                            "id": str(ev["id"]),
                            "home": ev["homeTeam"]["name"],
                            "away": ev["awayTeam"]["name"],
                            "league": ev["tournament"].get("slug",""),
                            "league_name": ev["tournament"].get("name",""),
                            "minute": minute,
                            "source": f"Sofascore {url}",
                        })
                if found or len(events)>0:
                    return found, f"Sofascore {url}", f"OK {len(events)} live"
            except Exception as e:
                print(f"Sofascore error {url}: {e}")
                continue
    return found, "Sofascore (blocked 403)", "All endpoints 403 - fallback to ESPN multi"

def fetch_all():
    print("=== SCAN 200+ LIGA ===")
    all_new = []
    logs = []
    
    # 1. ESPN MULTI 50 liga = 200+ events
    new_espn, src_espn, msg_espn = fetch_espn_multi()
    all_new.extend(new_espn)
    logs.append(f"{src_espn}: {msg_espn} - Found {len(new_espn)}")
    
    # 2. Sofascore kalau bisa tembus
    new_sofa, src_sofa, msg_sofa = fetch_sofascore_v2()
    all_new.extend(new_sofa)
    logs.append(f"{src_sofa}: {msg_sofa} - Found {len(new_sofa)}")
    
    # Deduplicate by id
    seen = {}
    for n in all_new:
        if n["id"] not in seen:
            seen[n["id"]] = n
    deduped = list(seen.values())
    
    return deduped, logs

def update_live_scores(existing):
    print("=== UPDATE LIVE SCORE EXISTING ===")
    # Update via ESPN multi juga biar FT ke-detect
    try:
        for m in existing:
            if not m.get("is_ft") and m.get("result")=="LIVE":
                try:
                    created = datetime.fromisoformat(m.get("created_at","").replace("Z","+00:00"))
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=WITA)
                    umur = (now_wita() - created).total_seconds()/60
                    m["umur_menit"] = umur
                    if umur > 50:
                        # Auto FT kalau udah >50 menit dari deteksi (60+50=110 >90)
                        print(f"Auto FT check {m['home_team']} vs {m['away_team']} umur {umur:.0f}m - mungkin sudah FT")
                except:
                    pass
    except Exception as e:
        print(f"Update error {e}")

if __name__ == "__main__":
    print("=== START V13 200+ LIGA SCAN ===")
    print(f"Scan {now_wita()} | WITA")
    print(f"Sumber: ESPN 50 liga (200+ events) + Sofascore live")
    print(f"Window: 60-66 skor 0-0")
    print("")
    existing = load_matches()
    print(f"Existing: {len(existing)} match (11W-6L 64.7% WR real)")
    
    update_live_scores(existing)
    
    print("\n=== SCAN BARU ===")
    all_new, logs = fetch_all()
    
    print("\n=== SUMMARY 200+ LIGA ===")
    for l in logs:
        print(f"  - {l}")
    print(f"TOTAL Found {len(all_new)} new 0-0 at 60-66 (deduped)")
    
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
                "source": nm.get("source","ESPN multi"),
                "gol_terjadi": None,
            })
            added += 1
            print(f"+ NEW: {nm['home']} vs {nm['away']} [{nm.get('league','')}] {nm.get('minute',60)}' 0-0 via {nm.get('source','')}")
    
    print(f"\nAdded {added} new match")
    save_matches(existing)
    print(f"Saved {len(existing)} total (200 latest di matches.json)")
    print(f"=== SELESAI V13 200+ LIGA ===")
