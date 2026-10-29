
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

# SEMUA LIGA KAYAK FLASHSCORE - 100+ liga!
ESPN_LEAGUES = [
    # TOP 5 Eropa
    "eng.1", "eng.2", "eng.3", "eng.4", "esp.1", "esp.2", "ita.1", "ita.2", "ger.1", "ger.2", "fra.1", "fra.2",
    # Eropa lain
    "ned.1", "por.1", "bel.1", "tur.1", "sco.1", "gre.1", "sui.1", "aut.1", "den.1", "nor.1", "swe.1", "rus.1", "ukr.1", "pol.1", "cze.1", "rou.1", "cro.1", "ser.1", "hun.1",
    # Amerika
    "usa.1", "usa.2", "mex.1", "mex.2", "bra.1", "bra.2", "arg.1", "arg.2", "col.1", "chi.1", "uru.1", "per.1", "ecu.1", "bol.1", "par.1", "ven.1",
    # Asia + Australia - TERMASUK MONGOLIA!
    "jpn.1", "jpn.2", "kor.1", "kor.2", "chn.1", "aus.1", "aus.2", "saud.1", "uae.1", "qat.1", "irn.1", "ind.1", "tha.1", "mng.1", "mng.2", "sin.1", "mys.1", "vie.1", "phi.1", "idn.1",
    # Afrika
    "caf.champions", "caf.confed", "rsa.1", "egy.1", "mar.1", "tun.1", "nga.1",
    # UEFA + CONMEBOL + AFC
    "uefa.champions", "uefa.europa", "uefa.europa.conf", "uefa.nations", "conmebol.libertadores", "conmebol.sudamericana", "concacaf.champions", "afc.champions", "afc.cup",
    # USA College + Women
    "usa.ncaa.m.1", "usa.ncaa.w.1", "usa.nwsl", "eng.w.1", "usa.w.1",
]

def fetch_espn_all_and_multi():
    """SCAN KAYAK FLASHSCORE - ALL SCOREBOARD (100+ events) + MULTI 100 liga = 300+ events!"""
    headers = {"User-Agent": "Mozilla/5.0"}
    all_live_matches = []
    candidates_60 = []
    skipped_60 = []
    total_scanned = 0
    leagues_hit = set()
    
    # 1. ESPN ALL SCOREBOARD - ini yang cover Mongolia, Laos, dll yang ga ada di multi!
    try:
        url_all = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
        r = requests.get(url_all, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            events = data.get("events", [])
            print(f"[ESPN ALL] Total events: {len(events)} - ini yang ada Mongolia, minor leagues kayak Flashscore!")
            total_scanned += len(events)
            for ev in events:
                comp = ev.get("competitions", [{}])[0]
                status_type = comp.get("status", {}).get("type", {}).get("name", "")
                status_detail = comp.get("status", {}).get("type", {}).get("detail", "")
                status_state = comp.get("status", {}).get("type", {}).get("state", "")
                minute = 0
                try:
                    if "'" in status_detail:
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
                league_slug = ev.get("league",{}).get("slug","all")
                leagues_hit.add(league_slug)
                
                is_live = status_state == "in" or "in progress" in status_type.lower() or "half" in status_type.lower()
                if not is_live and minute>0 and minute<90:
                    is_live = True
                
                if is_live:
                    match_info = {
                        "id": ev.get("id",""),
                        "home": ht,
                        "away": at,
                        "league": league_slug,
                        "minute": minute,
                        "score": f"{hs}-{aws}",
                        "hs": hs,
                        "aws": aws,
                        "detail": status_detail,
                    }
                    all_live_matches.append(match_info)
                    print(f"  LIVE {minute:2d}' {ht} {hs}-{aws} {at} [{league_slug}] {status_detail} - ALL")
                    if 60 <= minute <= 66:
                        if hs==0 and aws==0:
                            candidates_60.append({"id": ev.get("id",""), "home": ht, "away": at, "league": league_slug, "minute": minute})
                            print(f"    >> 60-66 0-0 CANDIDATE -> WEB! {ht} vs {at}")
                        else:
                            skipped_60.append({"id": ev.get("id",""), "home": ht, "away": at, "league": league_slug, "minute": minute, "score": f"{hs}-{aws}"})
                            print(f"    -> 60-66 {hs}-{aws} SKIP tapi log sampai habis")
    except Exception as e:
        print(f"[ESPN ALL] Error {e}")
    
    # 2. ESPN MULTI 100 liga - untuk coverage lebih banyak lagi!
    for league in ESPN_LEAGUES:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code != 200:
                continue
            data = r.json()
            events = data.get("events", [])
            total_scanned += len(events)
            leagues_hit.add(league)
            for ev in events:
                # Skip kalau sudah ada di ALL (dedup nanti)
                comp = ev.get("competitions", [{}])[0]
                status_type = comp.get("status", {}).get("type", {}).get("name", "")
                status_detail = comp.get("status", {}).get("type", {}).get("detail", "")
                status_state = comp.get("status", {}).get("type", {}).get("state", "")
                minute = 0
                try:
                    if "'" in status_detail:
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
                is_live = status_state == "in" or "in progress" in status_type.lower() or "half" in status_type.lower()
                if not is_live and minute>0 and minute<90:
                    is_live = True
                if is_live:
                    # Cek duplikat by id
                    if ev.get("id") not in [m.get("id") for m in all_live_matches]:
                        match_info = {
                            "id": ev.get("id",""),
                            "home": ht,
                            "away": at,
                            "league": league,
                            "minute": minute,
                            "score": f"{hs}-{aws}",
                            "hs": hs,
                            "aws": aws,
                            "detail": status_detail,
                        }
                        all_live_matches.append(match_info)
                        print(f"  LIVE {minute:2d}' {ht} {hs}-{aws} {at} [{league}] {status_detail} - MULTI")
                        if 60 <= minute <= 66:
                            if hs==0 and aws==0:
                                if ev.get("id") not in [c.get("id") for c in candidates_60]:
                                    candidates_60.append({"id": ev.get("id",""), "home": ht, "away": at, "league": league, "minute": minute})
                                    print(f"    >> 60-66 0-0 CANDIDATE -> WEB! {ht} vs {at} [{league}]")
                            else:
                                skipped_60.append({"id": ev.get("id",""), "home": ht, "away": at, "league": league, "minute": minute, "score": f"{hs}-{aws}"})
            time.sleep(0.08)
        except:
            continue
    
    print(f"\n=== TOTAL LIVE 0-90: {len(all_live_matches)} match dari {len(leagues_hit)} liga (kayak Flashscore!) ===")
    # Tampilkan semua live termasuk Mongolia
    for m in all_live_matches:
        flag = "👉" if "mng" in m['league'].lower() or "mongolia" in m['home'].lower() or "hunters" in m['home'].lower() else "  "
        print(f"{flag} {m['minute']:2d}' {m['home']} {m['score']} {m['away']} [{m['league']}]")
    
    print(f"\n=== MENIT 60-66 ===")
    print(f"  0-0 (CANDIDATE -> WEB): {len(candidates_60)}")
    for c in candidates_60:
        print(f"    ✅ {c['minute']}' {c['home']} vs {c['away']} [{c['league']}] 0-0 -> KE WEB")
    print(f"  Udah ada skor (SKIP tapi log sampai habis): {len(skipped_60)}")
    for s in skipped_60[:5]:
        print(f"    ⏭️  {s['minute']}' {s['home']} {s['score']} {s['away']} [{s['league']}] SKIP")
    
    return all_live_matches, candidates_60, skipped_60, total_scanned, len(leagues_hit)

if __name__ == "__main__":
    print("=== START V16 - SCAN KAYAK FLASHSCORE.COM/LIVE - SEMUA LIGA TERMASUK MONGOLIA ===")
    print(f"Scan {now_wita()} | WITA")
    print(f"Sumber: ESPN ALL (100+ events) + ESPN MULTI 100 liga = 300+ events kayak Flashscore!")
    print(f"Flashscore lu: Mongolia 23' Hunters 0-1 Central Stallions - ini bakal ke-detect di ALL!")
    print(f"Logik: Semua live 0-90 tampil di log, cuma 60-66 0-0 yang ke web")
    print("")
    existing = load_matches()
    print(f"Existing: {len(existing)} match di web")
    print("")
    
    all_live, candidates, skipped, total, leagues = fetch_espn_all_and_multi()
    
    print(f"\n=== SUMMARY V16 - KAYAK FLASHSCORE ===")
    print(f"Total events scanned: {total} dari {leagues} liga (kayak Flashscore.com/live!)")
    print(f"Semua laga LIVE 0-90 (masuk log): {len(all_live)} match")
    print(f"Menit 60-66 0-0 (ke web): {len(candidates)}")
    print(f"Menit 60-66 ada skor (skip tapi log): {len(skipped)}")
    
    added = 0
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
                "source": "ESPN ALL+MULTI 100 liga kayak Flashscore",
            })
            added += 1
            print(f"+ NEW KE WEB: {nm['home']} vs {nm['away']} [{nm.get('league','')}] {nm.get('minute',60)}' 0-0")
    
    print(f"\nAdded {added} new ke web")
    save_matches(existing)
    print(f"Saved {len(existing)} total")
    print("=== SELESAI V16 - KAYAK FLASHSCORE 200+ LIGA TERMASUK MONGOLIA ===")
