
import os, json, requests, time
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

# ESPN 53 LIGA = 200+ EVENTS - SUDAH TERBUKTI BAGUS SEMALAM!
ESPN_LEAGUES = [
    "eng.1", "eng.2", "eng.3", "esp.1", "esp.2", "ita.1", "ita.2", "ger.1", "ger.2", "fra.1", "fra.2",
    "ned.1", "por.1", "bel.1", "tur.1", "sco.1", "gre.1", "sui.1", "aut.1", "den.1", "nor.1", "swe.1", "rus.1", "ukr.1",
    "usa.1", "mex.1", "bra.1", "arg.1", "col.1", "chi.1", "uru.1", "per.1", "ecu.1", "bol.1", "par.1", "ven.1",
    "jpn.1", "kor.1", "chn.1", "aus.1", "saud.1", "uae.1", "qat.1", "irn.1",
    "uefa.champions", "uefa.europa", "uefa.europa.conf", "conmebol.libertadores", "concacaf.champions", "afc.champions",
    "usa.ncaa.m.1", "usa.ncaa.w.1", "usa.nwsl"
]

def fetch_espn_multi():
    """ESPN ONLY - 200+ LIGA - TERBUKTI WORK SEMALAM, GA USAH SOFASCORE 403!"""
    source = "ESPN 53 liga (200+ events) ONLY - BEST"
    all_live = []
    found_60 = []
    total_scanned = 0
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for league in ESPN_LEAGUES:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code != 200:
                continue
            data = r.json()
            events = data.get("events", [])
            total_scanned += len(events)
            for ev in events:
                comp = ev.get("competitions", [{}])[0]
                status_type = comp.get("status", {}).get("type", {}).get("name", "")
                status_detail = comp.get("status", {}).get("type", {}).get("detail", "")
                minute = 0
                try:
                    if "'" in status_detail:
                        # "62'" atau "Second Half - 17'" = 62
                        if " - " in status_detail:
                            part = status_detail.split(" - ")
                            if "Second Half" in part[0]:
                                minute = 45 + int(''.join(filter(str.isdigit, part[1])) or 0)
                            else:
                                minute = int(''.join(filter(str.isdigit, part[1])) or 0)
                        else:
                            minute = int(''.join(filter(str.isdigit, status_detail.split("'")[0])) or 0)
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
                
                is_live = "in progress" in status_type.lower() or "half" in status_type.lower()
                if not is_live and minute>0 and minute<90:
                    is_live = True
                
                if is_live:
                    all_live.append(ev)
                    if 55 <= minute <= 75:
                        print(f"  LIVE {minute}' {ht} {hs}-{aws} {at} [{league}] {status_detail}")
                    if 60 <= minute <= 66 and hs==0 and aws==0:
                        found_60.append({
                            "id": ev.get("id",""),
                            "home": ht,
                            "away": at,
                            "league": league,
                            "minute": minute,
                        })
                        print(f"  >> FOUND 0-0 at {minute}' : {ht} vs {at} [{league}]")
            time.sleep(0.15)
        except Exception as e:
            continue
    
    print(f"[{source}] Total events scanned: {total_scanned} dari {len(ESPN_LEAGUES)} liga")
    print(f"[{source}] Live events: {len(all_live)}")
    print(f"[{source}] Found 0-0 at 60-66: {len(found_60)}")
    return found_60, source, f"OK {total_scanned} events from {len(ESPN_LEAGUES)} leagues ({len(all_live)} live) - ESPN ONLY, NO SOFASCORE 403"

if __name__ == "__main__":
    print("=== START V14 ESPN ONLY 200+ LIGA - BEST SEMALAM ===")
    print(f"Scan {now_wita()} | WITA")
    print(f"Sumber: ESPN ONLY 53 liga (200+ events) - TERBUKTI BAGUS, GA ADA SOFASCORE 403")
    print(f"Window: 60-66 skor 0-0")
    print("")
    existing = load_matches()
    print(f"Existing: {len(existing)} match (11W-6L 64.7% WR real)")
    
    print("\n=== SCAN ESPN ONLY 200+ LIGA ===")
    all_new, src, msg = fetch_espn_multi()
    
    print(f"\n=== SUMMARY ESPN ONLY ===")
    print(f"  - {src}: {msg} - Found {len(all_new)}")
    print(f"TOTAL Found {len(all_new)} new 0-0 at 60-66")
    
    added = 0
    for nm in all_new:
        if str(nm["id"]) not in [str(m.get("match_id")) for m in existing]:
            existing.append({
                "match_id": nm["id"],
                "home_team": nm["home"],
                "away_team": nm["away"],
                "league": nm.get("league",""),
                "minute": nm.get("minute",60),
                "score": "0-0",
                "score_deteksi": "0-0",
                "live_score": "0-0",
                "final_score": None,
                "is_ft": False,
                "result": "LIVE",
                "created_at": now_wita().isoformat(),
                "odds": 1.8,
                "source": "ESPN 53 liga ONLY - BEST",
            })
            added += 1
            print(f"+ NEW: {nm['home']} vs {nm['away']} [{nm.get('league','')}] {nm.get('minute',60)}' 0-0")
    
    print(f"\nAdded {added} new")
    save_matches(existing)
    print(f"Saved {len(existing)} total")
    print("=== SELESAI V14 ESPN ONLY - NO SOFASCORE 403 ===")
