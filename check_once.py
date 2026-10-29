
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
    "eng.1", "eng.2", "esp.1", "esp.2", "ita.1", "ita.2", "ger.1", "ger.2", "fra.1", "fra.2",
    "ned.1", "por.1", "bel.1", "tur.1", "sco.1", "gre.1", "sui.1", "aut.1", "den.1", "nor.1", "swe.1", "rus.1",
    "usa.1", "mex.1", "bra.1", "arg.1", "col.1", "chi.1", "uru.1", "per.1",
    "jpn.1", "kor.1", "chn.1", "aus.1", "saud.1",
    "uefa.champions", "uefa.europa", "uefa.europa.conf", "conmebol.libertadores", "concacaf.champions", "afc.champions",
    "usa.ncaa.m.1", "usa.ncaa.w.1", "usa.nwsl"
]

def fetch_espn_all_live():
    """SEMUA LAGA MENIT 0 LANGSUNG MASUK LOG - KAYAK SEMALAM V10!"""
    headers = {"User-Agent": "Mozilla/5.0"}
    all_live_matches = []  # Semua laga 0-90
    candidates_60 = []  # Yang 60-66 0-0 -> pindah ke web
    skipped_60 = []  # Yang 60-66 tapi udah ada skor -> skip tapi tampil di log
    
    total_scanned = 0
    
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
                status_state = comp.get("status", {}).get("type", {}).get("state", "")  # in, pre, post
                
                minute = 0
                try:
                    if "'" in status_detail:
                        if " - " in status_detail:
                            part = status_detail.split(" - ")
                            if "Second Half" in part[0]:
                                minute = 45 + int(''.join(filter(str.isdigit, part[1])) or 0)
                            elif "First Half" in part[0]:
                                minute = int(''.join(filter(str.isdigit, part[1])) or 0)
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
                    
                    # LOG SEMUA LAGA LIVE 0-90 - kayak semalam!
                    print(f"  LIVE {minute:2d}' {ht} {hs}-{aws} {at} [{league}] {status_detail}")
                    
                    # CEK MENIT 60 MASIH 0-0?
                    if 60 <= minute <= 66:
                        if hs==0 and aws==0:
                            candidates_60.append({
                                "id": ev.get("id",""),
                                "home": ht,
                                "away": at,
                                "league": league,
                                "minute": minute,
                            })
                            print(f"    >> 60-66 0-0 CANDIDATE -> PINDAH KE WEB! {ht} vs {at}")
                        else:
                            skipped_60.append({
                                "id": ev.get("id",""),
                                "home": ht,
                                "away": at,
                                "league": league,
                                "minute": minute,
                                "score": f"{hs}-{aws}",
                            })
                            print(f"    -> 60-66 {hs}-{aws} SKIP (udah ada gol) tapi tetep tampil di log sampai habis")
            time.sleep(0.12)
        except:
            continue
    
    print(f"\n=== TOTAL LIVE 0-90: {len(all_live_matches)} match ===")
    for m in all_live_matches[:10]:
        print(f"  {m['minute']:2d}' {m['home']} {m['score']} {m['away']} [{m['league']}]")
    if len(all_live_matches)>10:
        print(f"  ... dan {len(all_live_matches)-10} lainnya")
    
    print(f"\n=== MENIT 60-66 ===")
    print(f"  0-0 (CANDIDATE -> WEB): {len(candidates_60)}")
    for c in candidates_60:
        print(f"    ✅ {c['minute']}' {c['home']} vs {c['away']} [{c['league']}] 0-0 -> KE WEB")
    print(f"  Udah ada skor (SKIP tapi tampil di log V10 sampai habis): {len(skipped_60)}")
    for s in skipped_60:
        print(f"    ⏭️  {s['minute']}' {s['home']} {s['score']} {s['away']} [{s['league']}] SKIP (ada gol)")
    
    return all_live_matches, candidates_60, skipped_60, total_scanned

if __name__ == "__main__":
    print("=== START V15 - SEMUA LAGA 0' MASUK LOG, 60' 0-0 BARU KE WEB - KAYAK SEMALAM V10 ===")
    print(f"Scan {now_wita()} | WITA")
    print(f"Sumber: ESPN 42 liga (200+ events) ONLY - BEST SEMALAM")
    print(f"Logik: Semua live 0-90 tampil di log bot V10 sampai habis, cuma 60-66 0-0 yang pindah ke web")
    print(f"Window: 60-66 skor 0-0")
    print("")
    existing = load_matches()
    print(f"Existing: {len(existing)} match di web (11W-6L 64.7% WR real)")
    print("")
    
    all_live, candidates, skipped, total = fetch_espn_all_live()
    
    print(f"\n=== SUMMARY V15 - KAYAK SEMALAM ===")
    print(f"Total events scanned: {total} dari 42 liga")
    print(f"Semua laga LIVE 0-90 (masuk log): {len(all_live)} match")
    print(f"  -> Ini yang semalam tampil di run bot V10 sampai habis!")
    print(f"Menit 60-66 0-0 (CANDIDATE -> pindah ke web): {len(candidates)}")
    print(f"Menit 60-66 udah ada skor (SKIP tapi tetep di log): {len(skipped)}")
    print(f"TOTAL yang akan ditambah ke web: {len(candidates)}")
    
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
                "source": "ESPN 42 liga - V15 all live 0-90 log, 60-66 0-0 ke web",
            })
            added += 1
            print(f"+ NEW KE WEB: {nm['home']} vs {nm['away']} [{nm.get('league','')}] {nm.get('minute',60)}' 0-0")
    
    print(f"\nAdded {added} new ke web")
    save_matches(existing)
    print(f"Saved {len(existing)} total di web (200 latest)")
    print(f"=== SELESAI V15 - SEMUA LAGA 0-90 DI LOG, 60-66 0-0 KE WEB - KAYAK V10 SEMALAM ===")
