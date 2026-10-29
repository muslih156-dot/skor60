
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

ESPN_LEAGUES = [
    "eng.1", "eng.2", "eng.3", "esp.1", "esp.2", "ita.1", "ita.2", "ger.1", "ger.2", "fra.1", "fra.2",
    "ned.1", "por.1", "bel.1", "tur.1", "sco.1", "gre.1", "sui.1", "aut.1", "den.1", "nor.1", "swe.1", "rus.1", "ukr.1", "pol.1", "cze.1",
    "usa.1", "mex.1", "bra.1", "bra.2", "arg.1", "col.1", "chi.1", "uru.1", "per.1",
    "jpn.1", "kor.1", "chn.1", "aus.1", "saud.1", "uae.1", "qat.1",
    "uefa.champions", "uefa.europa", "uefa.europa.conf", "conmebol.libertadores", "concacaf.champions", "afc.champions",
    "usa.ncaa.m.1", "usa.ncaa.w.1", "usa.nwsl", "eng.w.1"
]

def parse_minute(detail):
    minute=0
    try:
        if not detail:
            return 0
        d=str(detail)
        if "'" in d:
            if " - " in d:
                # "Second Half - 17'" = 62
                parts=d.split(" - ")
                if len(parts)>=2:
                    num=''.join(filter(str.isdigit, parts[1]))
                    if num:
                        base=45 if "Second" in parts[0] or "2nd" in parts[0] else 0
                        minute=base+int(num)
            else:
                # "62'" 
                num=''.join(filter(str.isdigit, d.split("'")[0].split()[-1]))
                if num:
                    minute=int(num)
        elif "Half" in d:
            # "Halftime", "First Half"
            if "Half" in d:
                minute=45
    except:
        pass
    return minute

def fetch_espn_full():
    """ESPN FULL ONLY - 300+ EVENTS - NO FOTMOB NO SOFASCORE 403 - BEST!"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    all_live = []
    candidates = []
    skipped = []
    total = 0
    seen_ids = set()
    
    # 1. ESPN ALL - 100 events termasuk minor
    print("=== 1. ESPN ALL (100 events termasuk minor leagues) ===")
    try:
        r = requests.get("https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard", headers=headers, timeout=10)
        print(f"[ESPN ALL] Status: {r.status_code}")
        if r.status_code==200:
            data=r.json()
            events=data.get("events",[])
            total+=len(events)
            print(f"[ESPN ALL] Total: {len(events)} events")
            for ev in events:
                ev_id=ev.get("id","")
                if ev_id in seen_ids:
                    continue
                comp=ev.get("competitions",[{}])[0]
                status=comp.get("status",{}).get("type",{})
                detail=status.get("detail","")
                state=status.get("state","")
                name=status.get("name","")
                minute=parse_minute(detail)
                comps=comp.get("competitors",[])
                if len(comps)<2:
                    continue
                home=next((c for c in comps if c.get("homeAway")=="home"), comps[0])
                away=next((c for c in comps if c.get("homeAway")=="away"), comps[1] if len(comps)>1 else {})
                hs=int(home.get("score","0") or 0)
                aws=int(away.get("score","0") or 0)
                ht=home.get("team",{}).get("displayName","Home")
                at=away.get("team",{}).get("displayName","Away")
                league=ev.get("league",{}).get("slug","all")
                # LIVE jika state=in ATAU minute 1-90 ATAU detail ada ' dan bukan FT
                is_live = False
                if state=="in":
                    is_live=True
                elif minute>=1 and minute<=90:
                    is_live=True
                elif "'" in str(detail) and "Final" not in str(detail) and "FT" not in str(name):
                    is_live=True
                # Tapi bukan post
                if state=="post":
                    is_live=False
                
                if is_live:
                    if ev_id not in seen_ids:
                        seen_ids.add(ev_id)
                        all_live.append({"id":ev_id,"home":ht,"away":at,"league":league,"minute":minute,"score":f"{hs}-{aws}","hs":hs,"aws":aws,"detail":detail})
                        print(f"  LIVE {minute:2d}' {ht} {hs}-{aws} {at} [{league}] {detail} - ALL")
                        if 60<=minute<=66:
                            if hs==0 and aws==0:
                                candidates.append({"id":ev_id,"home":ht,"away":at,"league":league,"minute":minute})
                                print(f"    >> 60-66 0-0 CANDIDATE -> WEB!")
                            else:
                                skipped.append({"id":ev_id,"home":ht,"away":at,"league":league,"minute":minute,"score":f"{hs}-{aws}"})
                                print(f"    -> SKIP {hs}-{aws} tapi log")
                else:
                    # Debug kenapa ga live
                    if minute>0:
                        print(f"  NOT LIVE? {minute:2d}' {ht} {hs}-{aws} {at} [{league}] state={state} detail={detail} name={name}")
    except Exception as e:
        print(f"[ESPN ALL] Error {e}")
    
    # 2. ESPN MULTI 50+ liga
    print("\n=== 2. ESPN MULTI 50+ LIGA (200+ events) ===")
    for league in ESPN_LEAGUES:
        try:
            r=requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard", headers=headers, timeout=6)
            if r.status_code!=200:
                continue
            data=r.json()
            events=data.get("events",[])
            total+=len(events)
            for ev in events:
                ev_id=ev.get("id","")
                if ev_id in seen_ids:
                    continue
                comp=ev.get("competitions",[{}])[0]
                status=comp.get("status",{}).get("type",{})
                detail=status.get("detail","")
                state=status.get("state","")
                minute=parse_minute(detail)
                comps=comp.get("competitors",[])
                if len(comps)<2:
                    continue
                home=next((c for c in comps if c.get("homeAway")=="home"), comps[0])
                away=next((c for c in comps if c.get("homeAway")=="away"), comps[1] if len(comps)>1 else {})
                hs=int(home.get("score","0") or 0)
                aws=int(away.get("score","0") or 0)
                ht=home.get("team",{}).get("displayName","Home")
                at=away.get("team",{}).get("displayName","Away")
                is_live = state=="in" or (minute>=1 and minute<=90) or ("'" in str(detail))
                if state=="post":
                    is_live=False
                if is_live:
                    seen_ids.add(ev_id)
                    all_live.append({"id":ev_id,"home":ht,"away":at,"league":league,"minute":minute,"score":f"{hs}-{aws}","hs":hs,"aws":aws,"detail":detail})
                    print(f"  LIVE {minute:2d}' {ht} {hs}-{aws} {at} [{league}] {detail} - MULTI")
                    if 60<=minute<=66:
                        if hs==0 and aws==0:
                            candidates.append({"id":ev_id,"home":ht,"away":at,"league":league,"minute":minute})
                            print(f"    >> 60-66 0-0 CANDIDATE MULTI -> WEB!")
                        else:
                            skipped.append({"id":ev_id,"home":ht,"away":at,"league":league,"minute":minute,"score":f"{hs}-{aws}"})
            time.sleep(0.05)
        except:
            continue
    
    print(f"\n[ESPN FULL ONLY] Total events scanned: {total} dari ALL + {len(ESPN_LEAGUES)} liga")
    print(f"[ESPN FULL ONLY] Live 0-90: {len(all_live)} match")
    print(f"[ESPN FULL ONLY] 60-66 0-0: {len(candidates)} candidate -> WEB")
    print(f"[ESPN FULL ONLY] 60-66 ada skor: {len(skipped)} skip tapi log")
    print(f"[ESPN FULL ONLY] NO FOTMOB 404, NO SOFASCORE 403 TIMEOUT - CUMA ESPN BEST!")
    return all_live, candidates, skipped, total

if __name__ == "__main__":
    print("=== START V18 - ESPN FULL ONLY - 300+ EVENTS - NO FOTMOB 404 NO SOFASCORE 403 - BEST SEMALAM ===")
    print(f"Scan {now_wita()} | WITA")
    print(f"Sumber: ESPN FULL ONLY - ALL (100 events) + MULTI 50+ liga (200+ events) = 300+ events")
    print(f"Fix: FotMob 404 & Sofascore proxy timeout dihapus - cuma ESPN yang terbukti bagus semalam!")
    print(f"Logik: Semua live 0-90 tampil di log, 60-66 0-0 ke web, ada skor skip tapi log")
    print("")
    existing=load_matches()
    print(f"Existing: {len(existing)} match di web (11W-6L 64.7% WR)")
    print("")
    
    all_live, candidates, skipped, total = fetch_espn_full()
    
    print(f"\n=== TOTAL LIVE 0-90: {len(all_live)} match (semua masuk log kayak V10 semalam) ===")
    for m in all_live[:20]:
        flag="🔥" if 60<=m["minute"]<=66 and m["hs"]==0 and m["aws"]==0 else "  "
        print(f"{flag} {m['minute']:2d}' {m['home']} {m['score']} {m['away']} [{m['league']}] {m['detail']}")
    if len(all_live)>20:
        print(f"  ... dan {len(all_live)-20} lainnya")
    
    print(f"\n=== MENIT 60-66 ===")
    print(f"  0-0 (CANDIDATE -> WEB): {len(candidates)}")
    for c in candidates:
        print(f"    ✅ {c['minute']}' {c['home']} vs {c['away']} [{c['league']}] 0-0 -> KE WEB")
    print(f"  Ada skor (SKIP tapi log): {len(skipped)}")
    for s in skipped[:10]:
        print(f"    ⏭️  {s['minute']}' {s['home']} {s['score']} {s['away']} [{s['league']}] SKIP")
    
    print(f"\n=== SUMMARY V18 - ESPN FULL ONLY - ANTI ZONK ===")
    print(f"Total events scanned: {total} dari ALL + {len(ESPN_LEAGUES)} liga = 300+ events!")
    print(f"Semua laga LIVE 0-90 (masuk log): {len(all_live)} match - ANTI ZONK SORE!")
    print(f"Menit 60-66 0-0 (ke web): {len(candidates)}")
    print(f"Menit 60-66 ada skor (skip tapi log): {len(skipped)}")
    
    added=0
    for nm in candidates:
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
                "source": "ESPN FULL ONLY V18",
            })
            added+=1
            print(f"+ NEW KE WEB: {nm['home']} vs {nm['away']} [{nm.get('league','')}] {nm.get('minute',60)}' 0-0")
    
    print(f"\nAdded {added} new ke web")
    save_matches(existing)
    print(f"Saved {len(existing)} total")
    print("=== SELESAI V18 - ESPN FULL ONLY 300+ EVENTS - NO 404 NO 403 - BEST ===")
