
import os, json, requests, time
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MIN_MINUTE = 60
MAX_MINUTE = 66
WITA_TZ = timezone(timedelta(hours=8))

def wita_now():
    utc = datetime.utcnow()
    wita = utc + timedelta(hours=8)
    return wita, utc

def load_local_matches(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                j = json.load(f)
                if isinstance(j, list):
                    return j
    except Exception as e:
        print(f"Load {path} error {e}")
    return []

LEAGUE_NAMES = {
    "eng.1": "Premier League", "eng.2": "Championship", "eng.fa": "FA Cup",
    "ger.1": "Bundesliga", "ger.2": "2. Bundesliga", "ger.dfb_pokal": "DFB Pokal",
    "esp.1": "LaLiga", "esp.2": "LaLiga 2", "ita.1": "Serie A", "ita.2": "Serie B",
    "fra.1": "Ligue 1", "ned.1": "Eredivisie", "por.1": "Primeira Liga",
    "bel.1": "Jupiler Pro League", "tur.1": "Süper Lig", "sco.1": "Scottish Premiership",
    "uefa.champions": "Champions League", "uefa.europa": "Europa League",
    "usa.1": "MLS", "bra.1": "Brasileirão", "jpn.1": "J1 League", "idn.1": "Liga 1",
    "swe.1": "Allsvenskan", "nor.1": "Eliteserien", "den.1": "Superliga",
    "afc.cup": "AFC Cup", "afc.champions": "AFC Champions",
}

def get_pretty_league(slug, raw=""):
    if slug in LEAGUE_NAMES:
        return LEAGUE_NAMES[slug]
    if raw and raw != slug and "." not in raw and len(raw) > 3:
        return raw
    return slug.replace("."," ").replace("_"," ").title()

def parse_clock(clock_str, detail_str=""):
    try:
        s = (clock_str or detail_str or "").strip()
        if not s: return 0
        su = s.upper()
        if "HT" in su: return 45
        if "FT" in su: return 90
        s_clean = s.replace("'", "").replace('"', "").replace("’", "")
        if ":" in s_clean: return int(s_clean.split(":")[0])
        if "+" in s_clean: return int(s_clean.split("+")[0].split()[0])
        parts = s_clean.split()
        for p in parts:
            if p.isdigit():
                return int(p)
        return int(float(parts[0])) if parts else 0
    except:
        return 0

def get_warning_flags(league_name, home, away, league_code=""):
    warnings = []
    low = f"{league_name} {home} {away} {league_code}".lower()
    if any(x in low for x in ["women", "female", "putri", "wanita"]): warnings.append("⚠️ LIGA WANITA")
    if any(x in low for x in ["u17","u19","u21","u23","youth","reserves"," ii"," iii"," u-"]): warnings.append("⚠️ TIM MUDA")
    if any(x in low for x in ["futsal","beach","esports","amateur","friendly","nextgen"]): warnings.append("⚠️ LIGA MINOR")
    return " | ".join(warnings) if warnings else ""

def fetch_all_leagues():
    all_leagues = []
    try:
        r = requests.get("https://sports.core.api.espn.com/v2/sports/soccer/leagues?limit=500", timeout=15)
        if r.status_code == 200:
            j = r.json()
            items = j.get("items", [])
            for it in items:
                slug = None
                if "$ref" in it:
                    try: slug = it["$ref"].split("/leagues/")[-1].split("?")[0].split("/")[0]
                    except: pass
                else: slug = it.get("id")
                if slug and len(slug) < 50 and "." in slug:
                    all_leagues.append((slug, slug))
    except: pass
    if len(all_leagues) < 80:
        fallback = ["eng.1","eng.2","eng.fa","ger.1","ger.2","ger.dfb_pokal","esp.1","esp.2","ita.1","fra.1","ned.1","por.1","bel.1","tur.1","sco.1","uefa.champions","uefa.europa","uefa.europa.conf","usa.1","bra.1","arg.1","mex.1","jpn.1","kor.1","aus.1","idn.1","tha.1","mys.1","ind.1","swe.1","nor.1","den.1","afc.cup","afc.champions","ita.2","eng.3","fra.2","ned.2","por.2","bel.2","tur.2","usa.2","bra.2","jpn.2","swe.2","nor.2","den.2","fin.1","egy.1","sau.1","qat.1","uae.1","chn.1","rus.1","ukr.1","pol.1","cze.1","gre.1","sui.1","aut.1","irl.1","wal.1","sco.2","mex.2","arg.2","col.1","chi.1","per.1","uru.1","par.1","bol.1","ven.1","ecu.1","conmebol.libertadores","conmebol.sudamericana"]
        all_leagues = [(c,c) for c in fallback]
    seen={}
    for slug,name in all_leagues: seen[slug]=name
    return list(seen.items())

def fetch_league(league_tuple):
    slug, lname = league_tuple
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"
    try:
        r = requests.get(url, timeout=6)
        if r.status_code==200:
            evs = r.json().get("events",[])
            if evs: return (slug, lname, evs)
        return (slug, lname, [])
    except: return (slug, lname, [])

def cek_parallel():
    wita, utc = wita_now()
    start = time.time()
    print(f"WITA {wita} | SCAN 220 LIGA WINDOW {MIN_MINUTE}-{MAX_MINUTE} V10 LIVE SCORE")
    leagues = fetch_all_leagues()
    print(f"Total {len(leagues)} liga")
    all_events={}
    with ThreadPoolExecutor(max_workers=25) as ex:
        futures = {ex.submit(fetch_league, lt): lt for lt in leagues}
        for fut in as_completed(futures):
            slug, lname, evs = fut.result()
            if evs:
                for ev in evs:
                    all_events[ev.get("id")]=(ev,slug,lname)
    elapsed = time.time()-start
    print(f"Parallel done {elapsed:.1f}s - {len(all_events)} events")
    out=[]
    inprog=[]
    for ev_id,(ev,slug,lname) in all_events.items():
        try:
            comp = ev.get("competitions",[{}])[0]
            status = comp.get("status",{})
            tname = status.get("type",{}).get("name","")
            state = status.get("type",{}).get("state","")
            clock = status.get("displayClock","") or status.get("clock","") or ""
            detail = status.get("type",{}).get("shortDetail","") or status.get("type",{}).get("detail","") or ""
            minute = parse_clock(clock, detail)
            comps = comp.get("competitors",[])
            if len(comps)<2: continue
            home = next((c for c in comps if c.get("homeAway")=="home"), comps[0])
            away = next((c for c in comps if c.get("homeAway")=="away"), comps[1])
            hs = int(home.get("score",0) or 0)
            aws = int(away.get("score",0) or 0)
            hname = home.get("team",{}).get("displayName","Home")
            aname = away.get("team",{}).get("displayName","Away")
            raw_league = (ev.get("leagues",[{}])[0].get("name") if ev.get("leagues") else "") or lname
            real_league = get_pretty_league(slug, raw_league)
            is_live = "IN_PROGRESS" in tname or state=="in"
            is_ft = "FINAL" in tname or "FT" in tname or state=="post"
            if is_live or is_ft:
                warning = get_warning_flags(real_league, hname, aname, slug)
                line = f"{hname} {hs}-{aws} {aname} Menit {minute} {real_league} [{slug}] {tname} {warning}"
                inprog.append((minute, line, ev, hs, aws, hname, aname, real_league, slug, warning, is_ft, is_live, ev_id))
                if MIN_MINUTE <= minute <= MAX_MINUTE and hs==0 and aws==0 and is_live:
                    out.append({"id": ev.get("id"), "home": hname, "away": aname, "league": real_league, "league_slug": slug, "minute": minute, "warning": warning, "status": "AKTIF", "score": f"{hs}-{aws}", "hs": hs, "aws": aws, "is_live": True})
        except Exception as e:
            continue
    inprog_sorted = sorted(inprog, key=lambda x: x[0])
    print(f"--- {len(inprog_sorted)} IN-PROGRESS/FT ---")
    for minute, line, ev, hs, aws, hname, aname, real_league, slug, warning, is_ft, is_live, ev_id in inprog_sorted[:50]:
        print(line)
    print(f"Found {len(out)} peluang {MIN_MINUTE}-{MAX_MINUTE} 0-0")
    return out, inprog_sorted

def update_live_scores():
    """V10: Update score & menit untuk match yang masih live di dashboard"""
    try:
        wita, _ = wita_now()
        dash = load_local_matches("data/matches.json")
        if not dash:
            print("No dash to update")
            return
        
        # Fetch all current events
        leagues = fetch_all_leagues()
        all_events = {}
        with ThreadPoolExecutor(max_workers=25) as ex:
            futures = {ex.submit(fetch_league, lt): lt for lt in leagues}
            for fut in as_completed(futures):
                slug, lname, evs = fut.result()
                if evs:
                    for ev in evs:
                        all_events[ev.get("id")] = ev
        
        updated_count = 0
        finished_count = 0
        
        for m in dash:
            mid = str(m.get("match_id"))
            if mid in all_events:
                ev = all_events[mid]
                comp = ev.get("competitions",[{}])[0]
                status = comp.get("status",{})
                tname = status.get("type",{}).get("name","")
                clock = status.get("displayClock","") or status.get("clock","") or ""
                detail = status.get("type",{}).get("shortDetail","") or ""
                minute = parse_clock(clock, detail)
                comps = comp.get("competitors",[])
                if len(comps) >= 2:
                    home_c = next((c for c in comps if c.get("homeAway")=="home"), comps[0])
                    away_c = next((c for c in comps if c.get("homeAway")=="away"), comps[1])
                    hs = int(home_c.get("score",0) or 0)
                    aws = int(away_c.get("score",0) or 0)
                    is_ft = "FINAL" in tname or "FT" in detail or "FT" in tname
                    
                    # Update live score & menit
                    old_minute = m.get("minute",0)
                    old_score = m.get("score","0-0")
                    new_score = f"{hs}-{aws}"
                    
                    if minute != old_minute or new_score != old_score:
                        m["minute"] = minute
                        m["score"] = new_score
                        m["menit_sekarang"] = minute
                        m["last_update"] = wita.isoformat()
                        m["status_detail"] = detail
                        updated_count += 1
                        print(f"🔄 Update {mid} {m['home_team']} {old_score}@{old_minute}' -> {new_score}@{minute}'")
                    
                    # Kalau FT, cek WIN/LOSE
                    if is_ft:
                        final_score = new_score
                        m["final_score"] = final_score
                        m["is_ft"] = True
                        m["ft_at"] = wita.isoformat()
                        if hs + aws > 0:
                            m["result"] = "✅ WIN"
                            m["betting"] = "WIN - Over 0.5 masuk!"
                            m["profit"] = 80
                        else:
                            m["result"] = "❌ LOSE"
                            m["betting"] = "LOSE - Tetap 0-0"
                            m["profit"] = -100
                        finished_count += 1
                        print(f"🏁 FT {mid} {m['home_team']} vs {m['away_team']} {final_score} = {m['result']}")
            else:
                # Match ga ada di live events lagi, mungkin FT
                try:
                    created = datetime.fromisoformat(m.get('created_at','').replace('Z','+00:00'))
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=WITA_TZ)
                    umur = (wita - created).total_seconds() / 60
                    if umur > 120 and not m.get('is_ft'):  # 2 jam ga ada update = FT 0-0?
                        m["is_ft"] = True
                        m["final_score"] = m.get("score","0-0")
                        if m["final_score"] == "0-0":
                            m["result"] = "❌ LOSE"
                            m["profit"] = -100
                        else:
                            m["result"] = "✅ WIN"
                            m["profit"] = 80
                        finished_count += 1
                except:
                    pass
        
        if updated_count > 0 or finished_count > 0:
            with open("data/matches.json","w",encoding="utf-8") as f:
                json.dump(dash, f, indent=2, default=str)
            print(f"Updated {updated_count} live scores, {finished_count} FT")
            
            # Update archive juga
            month_key = wita.strftime("%Y-%m")
            for arch_path in [f"data/archive/{month_key}.json", "data/archive/all_time.json"]:
                if os.path.exists(arch_path):
                    archive = load_local_matches(arch_path)
                    for am in archive:
                        for dm in dash:
                            if str(am.get('match_id')) == str(dm.get('match_id')):
                                if dm.get('is_ft'):
                                    am['final_score'] = dm.get('final_score')
                                    am['result'] = dm.get('result')
                                    am['is_ft'] = True
                                    am['score'] = dm.get('score')
                                    am['minute'] = dm.get('minute')
                    with open(arch_path,"w",encoding="utf-8") as f:
                        json.dump(archive, f, indent=2, default=str)
        else:
            print("No live updates needed")
            
    except Exception as e:
        print(f"Update live scores error {e}")
        import traceback
        traceback.print_exc()

def save_batch(new_matches):
    try:
        wita, utc = wita_now()
        month_key = wita.strftime("%Y-%m")
        os.makedirs("data", exist_ok=True)
        os.makedirs("data/archive", exist_ok=True)
        if not os.path.exists("data/matches.json"):
            with open("data/matches.json","w") as f: json.dump([], f)
        
        existing_dash = load_local_matches("data/matches.json")
        existing_month = load_local_matches(f"data/archive/{month_key}.json")
        existing_all = load_local_matches("data/archive/all_time.json")
        
        existing_ids = set(str(m.get("match_id")) for m in existing_dash)
        filtered = [m for m in new_matches if str(m["id"]) not in existing_ids]
        
        if not filtered:
            print(f"Ga ada yang baru")
            return
        
        new_entries = []
        for m in filtered:
            full_status = m["status"]
            if m["warning"]: full_status = f"{m['status']} | {m['warning']}"
            entry = {
                "match_id": str(m["id"]),
                "home_team": m["home"],
                "away_team": m["away"],
                "league": m["league"],
                "league_slug": m.get("league_slug",""),
                "minute": m["minute"],
                "menit_sekarang": m["minute"],
                "score": m.get("score","0-0"),
                "status": full_status,
                "status_detail": "AKTIF",
                "created_at": wita.isoformat(),
                "last_update": wita.isoformat(),
                "wita_date": wita.strftime("%Y-%m-%d"),
                "month": month_key,
                "prob_gol": 75,
                "is_ft": False
            }
            new_entries.append(entry)
        
        updated_dash = new_entries + existing_dash
        updated_dash = updated_dash[:200]
        with open("data/matches.json","w",encoding="utf-8") as f: json.dump(updated_dash, f, indent=2, default=str)
        
        updated_month = new_entries + existing_month
        with open(f"data/archive/{month_key}.json","w",encoding="utf-8") as f: json.dump(updated_month, f, indent=2, default=str)
        
        updated_all = new_entries + existing_all
        with open("data/archive/all_time.json","w",encoding="utf-8") as f: json.dump(updated_all, f, indent=2, default=str)
        
        print(f"✅ Saved BATCH: {len(new_entries)} new | dash {len(updated_dash)}")
        for e in new_entries:
            print(f"  - {e['match_id']} {e['home_team']} vs {e['away_team']} {e['league']} Menit {e['minute']}")
        
    except Exception as e:
        print(f"Save batch error {e}")
        import traceback
        traceback.print_exc()

if __name__=="__main__":
    wita,utc = wita_now()
    print(f"V10 LIVE SCORE + RESULT - WINDOW {MIN_MINUTE}-{MAX_MINUTE} - WITA {wita}")
    print("=== Step 1: Update live scores for existing matches ===")
    update_live_scores()
    print("=== Step 2: Scan new peluang ===")
    new_matches, all_inprog = cek_parallel()
    save_batch(new_matches)
    print(f"Done V10 - Updated live scores + {len(new_matches)} new")
