
import os, json, requests, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

WITA = timezone(timedelta(hours=8))
DATA_DIR = Path("data")
MATCHES_FILE = DATA_DIR / "matches.json"
ARCHIVE_DIR = DATA_DIR / "archive"
DAILY_DIR = ARCHIVE_DIR / "daily"

def now_wita():
    return datetime.now(WITA)

def get_trading_day(dt):
    """Cut off 12:00 WITA - trading day 12:00-11:59 next day"""
    # Kalau jam <12, trading day nya kemarin
    # Kalau jam >=12, trading day nya hari ini
    if dt.hour < 12:
        trading_date = (dt - timedelta(days=1)).date()
    else:
        trading_date = dt.date()
    return trading_date

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
    DAILY_DIR.mkdir(exist_ok=True, parents=True)
    
    # Save main files
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
    
    # ===== PARTISI HARIAN CUT OFF 12:00 WITA =====
    # Group by trading day
    daily_groups = {}
    for m in matches:
        try:
            created_str = m.get("created_at","")
            created = datetime.fromisoformat(created_str.replace("Z","+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=WITA)
            # Convert to WITA
            created_wita = created.astimezone(WITA)
            trading_day = get_trading_day(created_wita)
            key = trading_day.isoformat()
            if key not in daily_groups:
                daily_groups[key] = []
            daily_groups[key].append(m)
        except:
            # Fallback ke hari ini
            today_key = get_trading_day(now_wita()).isoformat()
            if today_key not in daily_groups:
                daily_groups[today_key] = []
            daily_groups[today_key].append(m)
    
    # Save tiap trading day
    for day_key, day_matches in daily_groups.items():
        daily_file = DAILY_DIR / f"{day_key}.json"
        with open(daily_file,'w',encoding='utf-8') as f:
            json.dump(day_matches, f, indent=2, ensure_ascii=False)
        print(f"  Partisi {day_key} (cut off 12:00 WITA): {len(day_matches)} match")
    
    return daily_groups

ESPN_LEAGUES = [
    "eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "ned.1", "por.1", "bel.1", "tur.1", "usa.1", "mex.1", "bra.1", "arg.1", "jpn.1", "kor.1", "aus.1", "saud.1",
    "uefa.champions", "uefa.europa", "conmebol.libertadores", "afc.champions",
]

def parse_minute(detail):
    minute=0
    try:
        if not detail:
            return 0
        d=str(detail)
        if "'" in d:
            if " - " in d:
                parts=d.split(" - ")
                if len(parts)>=2:
                    num=''.join(filter(str.isdigit, parts[1]))
                    if num:
                        base=45 if "Second" in parts[0] or "2nd" in parts[0] else 0
                        minute=base+int(num)
            else:
                num=''.join(filter(str.isdigit, d.split("'")[0].split()[-1]))
                if num:
                    minute=int(num)
    except:
        pass
    return minute

def fetch_espn_full():
    headers = {"User-Agent": "Mozilla/5.0"}
    all_live = []
    candidates = []
    skipped = []
    total = 0
    seen_ids = set()
    
    print("=== 1. ESPN ALL (100 events) ===")
    try:
        r = requests.get("https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard", headers=headers, timeout=10)
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
                is_live = state=="in" or (minute>=1 and minute<=90) or ("'" in str(detail))
                if state=="post":
                    is_live=False
                if is_live:
                    seen_ids.add(ev_id)
                    all_live.append({"id":ev_id,"home":ht,"away":at,"league":league,"minute":minute,"score":f"{hs}-{aws}","hs":hs,"aws":aws,"detail":detail})
                    print(f"  LIVE {minute:2d}' {ht} {hs}-{aws} {at} [{league}] {detail} - ALL")
                    if 60<=minute<=66:
                        if hs==0 and aws==0:
                            candidates.append({"id":ev_id,"home":ht,"away":at,"league":league,"minute":minute})
                            print(f"    >> 60-66 0-0 CANDIDATE -> WEB!")
                        else:
                            skipped.append({"id":ev_id,"home":ht,"away":at,"league":league,"minute":minute,"score":f"{hs}-{aws}"})
    except Exception as e:
        print(f"[ESPN ALL] Error {e}")
    
    print("\n=== 2. ESPN MULTI 50+ LIGA ===")
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
    
    print(f"\n[ESPN FULL ONLY] Total: {total} events, Live: {len(all_live)}, 60-66 0-0: {len(candidates)}")
    return all_live, candidates, skipped, total

if __name__ == "__main__":
    print("=== START V19 - PARTISI CUT OFF 12:00 WITA + ESPN FULL 300+ EVENTS ===")
    print(f"Scan {now_wita()} | WITA")
    print(f"Cut off: 12:00 WITA - trading day 12:00-11:59 next day")
    print(f"17 match sebelum jam 12 siang ini = trading day 2026-10-28 (12:00 28 Oct - 11:59 29 Oct)")
    print(f"Nanti sore setelah jam 12 siang = trading day 2026-10-29 (12:00 29 Oct - 11:59 30 Oct) - masuk di atas 17 match!")
    print("")
    existing=load_matches()
    print(f"Existing: {len(existing)} match di web")
    # Hitung trading day existing
    trading_days={}
    for m in existing:
        try:
            created=datetime.fromisoformat(m.get("created_at","").replace("Z","+00:00"))
            if created.tzinfo is None:
                created=created.replace(tzinfo=WITA)
            created_wita=created.astimezone(WITA)
            td=get_trading_day(created_wita)
            trading_days[td.isoformat()]=trading_days.get(td.isoformat(),0)+1
        except:
            pass
    print(f"Partisi existing:")
    for day, cnt in sorted(trading_days.items()):
        print(f"  {day} (12:00 WITA cut off): {cnt} match")
    print("")
    
    all_live, candidates, skipped, total = fetch_espn_full()
    
    print(f"\n=== TOTAL LIVE 0-90: {len(all_live)} match ===")
    print(f"60-66 0-0 (ke web, masuk di atas 17 match): {len(candidates)}")
    for c in candidates:
        print(f"  ✅ {c['minute']}' {c['home']} vs {c['away']} [{c['league']}] 0-0 -> AKAN MASUK DI ATAS 17 MATCH!")
    
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
                "source": "V19 partisi 12:00 WITA",
                "trading_day": get_trading_day(now_wita()).isoformat(),
            })
            added+=1
            print(f"+ NEW KE WEB (di atas 17): {nm['home']} vs {nm['away']} [{nm.get('league','')}]")
    
    print(f"\nAdded {added} new ke web - akan muncul DI ATAS 17 match sebelumnya!")
    daily_groups = save_matches(existing)
    print(f"\n=== PARTISI CUT OFF 12:00 WITA ===")
    for day_key, day_matches in sorted(daily_groups.items()):
        print(f"  {day_key}: {len(day_matches)} match - file data/archive/daily/{day_key}.json")
    print(f"\nSaved {len(existing)} total - {added} baru di atas 17 lama")
    print("=== SELESAI V19 - PARTISI 12:00 WITA - BARU DI ATAS LAMA ===")
