
import os, json, requests, time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# V9.0 - WINDOW LEBIH LEBAR SAMPE MENIT 80!
MIN_MINUTE = 50
MAX_MINUTE = 80

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

def save_batch(new_matches):
    try:
        wita, utc = wita_now()
        month_key = wita.strftime("%Y-%m")
        os.makedirs("data", exist_ok=True)
        os.makedirs("data/archive", exist_ok=True)
        
        # Pastikan file exists biar ga error ls
        if not os.path.exists("data/matches.json"):
            with open("data/matches.json", "w") as f:
                json.dump([], f)
        
        existing_dash = load_local_matches("data/matches.json")
        existing_month = load_local_matches(f"data/archive/{month_key}.json")
        existing_all = load_local_matches("data/archive/all_time.json")
        
        existing_ids = set(str(m.get("match_id")) for m in existing_dash)
        filtered = [m for m in new_matches if str(m["id"]) not in existing_ids]
        
        if not filtered:
            print(f"Ga ada yang baru - window {MIN_MINUTE}-{MAX_MINUTE} 0-0 tidak ada yang baru")
            # Tetap pastikan file ada
            return
        
        new_entries = []
        for m in filtered:
            full_status = m["status"]
            if m["warning"]:
                full_status = f"{m['status']} | {m['warning']}"
            entry = {
                "match_id": str(m["id"]),
                "home_team": m["home"],
                "away_team": m["away"],
                "league": m["league"],
                "minute": m["minute"],
                "score": "0-0",
                "status": full_status,
                "created_at": wita.isoformat(),
                "wita_date": wita.strftime("%Y-%m-%d"),
                "month": month_key
            }
            new_entries.append(entry)
        
        updated_dash = new_entries + existing_dash
        updated_dash = updated_dash[:200]
        with open("data/matches.json", "w", encoding="utf-8") as f:
            json.dump(updated_dash, f, indent=2, default=str)
        
        updated_month = new_entries + existing_month
        with open(f"data/archive/{month_key}.json", "w", encoding="utf-8") as f:
            json.dump(updated_month, f, indent=2, default=str)
        
        updated_all = new_entries + existing_all
        with open("data/archive/all_time.json", "w", encoding="utf-8") as f:
            json.dump(updated_all, f, indent=2, default=str)
        
        print(f"✅ Saved BATCH: {len(new_entries)} new | dash {len(updated_dash)} | month {len(updated_month)} | all_time {len(updated_all)}")
        for e in new_entries:
            print(f"  - {e['match_id']} {e['home_team']} vs {e['away_team']} {e['league']} Menit {e['minute']}")
        
    except Exception as e:
        print(f"Save batch error {e}")
        import traceback
        traceback.print_exc()

def parse_clock(clock_str, detail_str=""):
    try:
        s = (clock_str or detail_str or "").strip()
        if not s:
            return 0
        su = s.upper()
        if "HT" in su:
            return 45
        if "FT" in su:
            return 90
        s_clean = s.replace("'", "").replace('"', "").replace("’", "")
        if ":" in s_clean:
            return int(s_clean.split(":")[0])
        if "+" in s_clean:
            return int(s_clean.split("+")[0].split()[0])
        parts = s_clean.split()
        for p in parts:
            if p.isdigit():
                return int(p)
        return int(float(parts[0])) if parts else 0
    except:
        return 0


LEAGUE_NAMES = {'eng.1': '🏴\U000d0067\U000d0062\U000d0065\U000d006e\U000d0067\U000d007f Premier League', 'eng.2': '🏴\U000d0067\U000d0062\U000d0065\U000d006e\U000d0067\U000d007f Championship', 'eng.3': '🏴\U000d0067\U000d0062\U000d0065\U000d006e\U000d0067\U000d007f League One', 'eng.4': '🏴\U000d0067\U000d0062\U000d0065\U000d006e\U000d0067\U000d007f League Two', 'eng.fa': '🏴\U000d0067\U000d0062\U000d0065\U000d006e\U000d0067\U000d007f FA Cup', 'eng.league_cup': '🏴\U000d0067\U000d0062\U000d0065\U000d006e\U000d0067\U000d007f Carabao Cup', 'ger.1': '🇩🇪 Bundesliga', 'ger.2': '🇩🇪 2. Bundesliga', 'ger.dfb_pokal': '🇩🇪 DFB Pokal', 'esp.1': '🇪🇸 LaLiga', 'esp.2': '🇪🇸 LaLiga 2', 'esp.copa_del_rey': '🇪🇸 Copa del Rey', 'ita.1': '🇮🇹 Serie A', 'ita.2': '🇮🇹 Serie B', 'ita.coppa_italia': '🇮🇹 Coppa Italia', 'fra.1': '🇫🇷 Ligue 1', 'fra.2': '🇫🇷 Ligue 2', 'fra.coupe_de_france': '🇫🇷 Coupe de France', 'ned.1': '🇳🇱 Eredivisie', 'ned.cup': '🇳🇱 KNVB Cup', 'por.1': '🇵🇹 Primeira Liga', 'bel.1': '🇧🇪 Jupiler Pro League', 'tur.1': '🇹🇷 Süper Lig', 'sco.1': '🏴\U000d0067\U000d0062\U000d0073\U000d0063\U000d0074\U000d007f Scottish Premiership', 'uefa.champions': '🏆 Champions League', 'uefa.europa': '🏆 Europa League', 'uefa.europa.conf': '🏆 Conference League', 'uefa.champions.qual': '🏆 UCL Qualifiers', 'uefa.nations': '🌍 Nations League', 'uefa.euro': '🌍 Euro', 'usa.1': '🇺🇸 MLS', 'usa.2': '🇺🇸 USL Championship', 'bra.1': '🇧🇷 Brasileirão', 'arg.1': '🇦🇷 Liga Profesional', 'mex.1': '🇲🇽 Liga MX', 'jpn.1': '🇯🇵 J1 League', 'kor.1': '🇰🇷 K League 1', 'aus.1': '🇦🇺 A-League', 'chn.1': '🇨🇳 Super League', 'idn.1': '🇮🇩 Liga 1', 'ind.1': '🇮🇳 ISL', 'tha.1': '🇹🇭 Thai League 1', 'mys.1': '🇲🇾 Liga Super', 'vie.1': '🇻🇳 V-League', 'sgp.1': '🇸🇬 Premier League', 'phi.1': '🇵🇭 PFL', 'sau.1': '🇸🇦 Pro League', 'qat.1': '🇶🇦 Stars League', 'uae.1': '🇦🇪 Pro League', 'egy.1': '🇪🇬 Premier League', 'nga.1': '🇳🇬 NPFL', 'rsa.1': '🇿🇦 PSL', 'aut.1': '🇦🇹 Bundesliga', 'sui.1': '🇨🇭 Super League', 'den.1': '🇩🇰 Superliga', 'swe.1': '🇸🇪 Allsvenskan', 'nor.1': '🇳🇴 Eliteserien', 'pol.1': '🇵🇱 Ekstraklasa', 'cze.1': '🇨🇿 First League', 'gre.1': '🇬🇷 Super League', 'por.cup': '🇵🇹 Taça de Portugal', 'bel.cup': '🇧🇪 Belgian Cup', 'tur.cup': '🇹🇷 Turkish Cup'}

def get_pretty_league(slug, raw_name=""):
    # Jika raw_name bagus (bukan slug), pakai raw_name
    if raw_name and raw_name != slug and len(raw_name) > 3 and "." not in raw_name:
        # Bersihin nama aneh
        if raw_name.lower() not in ["soccer", "football"]:
            return raw_name
    # Mapping
    if slug in LEAGUE_NAMES:
        return LEAGUE_NAMES[slug]
    # Fallback: ita.1 -> ITA 1 -> Serie A
    pretty = slug.replace(".", " ").replace("_", " ").title()
    # Tambah emoji flag dari kode negara
    if slug.startswith("ita"): return f"🇮🇹 {pretty}"
    if slug.startswith("eng"): return f"🏴󐁧󐁢󐁥󐁮󐁧󐁿 {pretty}"
    if slug.startswith("ger"): return f"🇩🇪 {pretty}"
    if slug.startswith("esp"): return f"🇪🇸 {pretty}"
    if slug.startswith("fra"): return f"🇫🇷 {pretty}"
    if slug.startswith("uefa"): return f"🏆 {pretty}"
    if slug.startswith("usa"): return f"🇺🇸 {pretty}"
    return pretty


def get_warning_flags(league_name, home, away, league_code=""):
    warnings = []
    low_league = league_name.lower()
    low_home = home.lower()
    low_away = away.lower()
    low_code = league_code.lower()
    combined = f"{low_league} {low_home} {low_away} {low_code}"
    if any(x in combined for x in ["women", "female", "putri", "wanita"]):
        warnings.append("⚠️ LIGA WANITA")
    youth_keys = ["u17", "u19", "u21", "u23", "u18", "u20", "youth", "reserves", " ii", " iii", " u-"]
    if any(x in combined for x in youth_keys):
        warnings.append("⚠️ TIM MUDA/CADANGAN")
    weird_keys = ["futsal", "beach", "esports", "amateur", "friendly", "nextgen", "corners"]
    if any(x in low_league for x in weird_keys):
        warnings.append("⚠️ LIGA MINOR/ANEH")
    if " ii" in low_home or " ii" in low_away or " iii" in low_home or " iii" in low_away:
        warnings.append("⚠️ TIM II/III")
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
                    try:
                        slug = it["$ref"].split("/leagues/")[-1].split("?")[0].split("/")[0]
                    except:
                        pass
                else:
                    slug = it.get("id")
                if slug and len(slug) < 50 and "." in slug:
                    all_leagues.append((slug, slug))
    except:
        pass
    if len(all_leagues) < 80:
        fallback = ["eng.1","eng.2","eng.fa","ger.1","ger.2","ger.dfb_pokal","esp.1","esp.2","ita.1","fra.1","ned.1","por.1","bel.1","tur.1","sco.1","uefa.champions","uefa.europa","uefa.europa.conf","uefa.nations","ind.1","tha.1","mys.1","vie.1","sgp.1","phi.1","jpn.1","kor.1","aus.1","usa.1","bra.1","arg.1","mex.1","egy.1","fin.1","aut.1","den.1","gre.1","svk.1","cze.1","pol.1","bul.1","nor.1","swe.1","sui.1","qat.1","sau.1","uae.1","chn.1","rus.1","ukr.1","rou.1","cro.1","srb.1","hun.1","irl.1","qat.1","isr.1","mar.1","nga.1","rsa.1","col.1","chi.1","per.1","uru.1","conmebol.libertadores","afc.champions","caf.champions","eng.3","eng.4","eng.league_cup","esp.copa_del_rey","ita.coppa_italia","fra.coupe_de_france","ned.cup","por.cup","bel.cup","tur.cup","sco.cup","jpn.2","kor.2","aus.2","nzl.1","chn.2","usa.2","bra.2","arg.2","mex.2","egy.2","fin.2","aut.2","den.2","gre.2","cze.2","pol.2","nor.2","swe.2","sui.2","irl.2","tha.2","mys.2","vie.2","ind.2","aut.cup","den.cup","gre.cup","svk.cup","cze.cup","pol.cup","bul.cup","srb.cup","rou.cup","ukr.cup","rus.cup","nor.cup","swe.cup","sui.cup","irl.cup","jpn.cup","kor.fa_cup","aus.cup","usa.open_cup","bra.cup","arg.cup","mex.cup","egy.cup","fin.cup","qat.cup","sau.cup","uae.cup","isr.cup","tha.fa_cup","mys.fa_cup","vie.cup","sgp.cup","phi.cup","idn.1","idn.2","chn.fa_cup","jpn.league_cup","kor.super_cup","aus.2.1","usa.super_cup","bra.super_cup","arg.super_cup","mex.super_cup","egy.super_cup","tur.super_cup","ned.super_cup","por.super_cup","bel.super_cup","sco.league_cup","jpn.super_cup","chn.super_cup","ind.super_cup","tha.league_cup","mys.cup","uefa.champions.qual","uefa.europa.qual","uefa.euro","uefa.euro.qual","uefa.super_cup","uefa.youth","conmebol.sudamericana","conmebol.recopa","caf.confed","afc.cup","fin.league_cup","aut.super_cup","den.super_cup","gre.super_cup","svk.super_cup","cze.super_cup","pol.super_cup","bul.super_cup","nor.super_cup","swe.super_cup","sui.super_cup","usa.3","bra.3","arg.1","col.2","ecu.1","bol.1","ven.1","par.1","mar.2","tun.1","alg.1","ken.1","jor.1","kuw.1","bhr.1","omn.1","irn.1","irq.1","qat.2","sau.2","uae.2","isr.2","slo.1","bih.1","mne.1","mac.1","mlt.1","cyp.1","geo.1","arm.1","aze.1","kaz.1","uzb.1","wal.1","nir.1","wal.cup","cyp.cup","slo.2","hun.2","slo.cup","bih.1"]
        all_leagues = [(c,c) for c in fallback]
    seen={}
    for slug,name in all_leagues:
        seen[slug]=name
    return list(seen.items())

def fetch_league(league_tuple):
    slug, lname = league_tuple
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"
    try:
        r = requests.get(url, timeout=6)
        if r.status_code==200:
            evs = r.json().get("events",[])
            if evs:
                return (slug, lname, evs)
        return (slug, lname, [])
    except:
        return (slug, lname, [])

def cek_parallel():
    wita, utc = wita_now()
    start = time.time()
    print(f"WITA {wita} | UTC {utc} - SCAN 220 LIGA PARALLEL V9.0 WINDOW {MIN_MINUTE}-{MAX_MINUTE} MENIT!")
    leagues = fetch_all_leagues()
    print(f"Total {len(leagues)} liga - window {MIN_MINUTE}-{MAX_MINUTE}")
    all_events={}
    with ThreadPoolExecutor(max_workers=25) as ex:
        futures = {ex.submit(fetch_league, lt): lt for lt in leagues}
        for fut in as_completed(futures):
            slug, lname, evs = fut.result()
            if evs:
                for ev in evs:
                    all_events[ev.get("id")]=(ev,slug,lname)
    elapsed = time.time()-start
    print(f"Parallel done {elapsed:.1f}s - {len(all_events)} unique events")
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
            if len(comps)<2:
                continue
            home = next((c for c in comps if c.get("homeAway")=="home"), comps[0])
            away = next((c for c in comps if c.get("homeAway")=="away"), comps[1])
            hs = int(home.get("score",0) or 0)
            aws = int(away.get("score",0) or 0)
            hname = home.get("team",{}).get("displayName","Home")
            aname = away.get("team",{}).get("displayName","Away")
            raw_league_name = (ev.get("leagues",[{}])[0].get("name") if ev.get("leagues") else "") or lname or ""
            real_league = get_pretty_league(slug, raw_league_name)
            if "IN_PROGRESS" in tname or state=="in":
                warning = get_warning_flags(real_league, hname, aname, slug)
                line = f"{hname} {hs}-{aws} {aname} Menit {minute} {real_league} [{slug}] {warning}"
                inprog.append((minute, line, ev, hs, aws, hname, aname, real_league, slug, warning))
        except:
            continue
    inprog_sorted = sorted(inprog, key=lambda x: x[0])
    print(f"--- {len(inprog_sorted)} IN-PROGRESS in {elapsed:.1f}s ---")
    for minute, line, ev, hs, aws, hname, aname, real_league, slug, warning in inprog_sorted[:50]:
        print(line)
        # V9.0: WINDOW SAMPE 80!
        if MIN_MINUTE <= minute <= MAX_MINUTE and hs==0 and aws==0:
            out.append({"id": ev.get("id"), "home": hname, "away": aname, "league": real_league, "minute": minute, "warning": warning, "slug": slug, "status": "AKTIF"})
    print(f"Found {len(out)} match {MIN_MINUTE}-{MAX_MINUTE} 0-0 (V9.0 sampe menit 80!)")
    return out


def check_final_result(match_id, home, away):
    """Cek hasil final dari ESPN untuk tau WIN/LOSE Over 0.5"""
    try:
        # Coba semua liga
        leagues = fetch_all_leagues()
        for slug, lname in leagues[:50]:  # cek 50 liga top aja biar cepat
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"
            try:
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    evs = r.json().get("events", [])
                    for ev in evs:
                        if str(ev.get("id")) == str(match_id):
                            comp = ev.get("competitions", [{}])[0]
                            status = comp.get("status", {}).get("type", {}).get("name", "")
                            comps = comp.get("competitors", [])
                            if len(comps) >= 2:
                                home_c = next((c for c in comps if c.get("homeAway")=="home"), comps[0])
                                away_c = next((c for c in comps if c.get("homeAway")=="away"), comps[1])
                                hs = int(home_c.get("score",0) or 0)
                                aws = int(away_c.get("score",0) or 0)
                                is_ft = "FINAL" in status or "FT" in status
                                final_score = f"{hs}-{aws}"
                                # WIN kalau bukan 0-0
                                result = "WIN" if (hs+aws) > 0 else "LOSE"
                                return {"final_score": final_score, "result": result, "is_ft": is_ft, "home_score": hs, "away_score": aws}
            except:
                continue
        return None
    except Exception as e:
        print(f"Check result error {match_id}: {e}")
        return None

def update_expired_results():
    """Update hasil FT untuk match yang sudah expired >40 menit"""
    try:
        wita, utc = wita_now()
        all_matches = load_local_matches("data/matches.json")
        if not all_matches:
            return
        
        updated = 0
        for m in all_matches:
            # Cek umur
            try:
                created = datetime.fromisoformat(m.get('created_at','').replace('Z','+00:00'))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone(timedelta(hours=8)))
                umur = (wita - created).total_seconds() / 60
            except:
                umur = 0
            
            # Kalau umur >35 menit dan belum ada hasil final, cek
            if umur > 35 and not m.get('final_checked'):
                res = check_final_result(m.get('match_id'), m.get('home_team'), m.get('away_team'))
                if res:
                    m['final_score'] = res['final_score']
                    m['result'] = res['result']
                    m['final_checked'] = True
                    m['is_ft'] = res['is_ft']
                    m['checked_at'] = wita.isoformat()
                    print(f"✅ Result {m['match_id']} {m['home_team']} vs {m['away_team']} FT {res['final_score']} = {res['result']}")
                    updated += 1
        
        if updated > 0:
            # Save updated
            with open("data/matches.json", "w", encoding="utf-8") as f:
                json.dump(all_matches, f, indent=2, default=str)
            
            # Update archive juga
            month_key = wita.strftime("%Y-%m")
            archive_path = f"data/archive/{month_key}.json"
            if os.path.exists(archive_path):
                archive = load_local_matches(archive_path)
                for am in archive:
                    for um in all_matches:
                        if str(am.get('match_id')) == str(um.get('match_id')) and um.get('final_checked'):
                            am['final_score'] = um.get('final_score')
                            am['result'] = um.get('result')
                            am['final_checked'] = True
                with open(archive_path, "w", encoding="utf-8") as f:
                    json.dump(archive, f, indent=2, default=str)
            
            all_time_path = "data/archive/all_time.json"
            if os.path.exists(all_time_path):
                all_time = load_local_matches(all_time_path)
                for atm in all_time:
                    for um in all_matches:
                        if str(atm.get('match_id')) == str(um.get('match_id')) and um.get('final_checked'):
                            atm['final_score'] = um.get('final_score')
                            atm['result'] = um.get('result')
                            atm['final_checked'] = True
                with open(all_time_path, "w", encoding="utf-8") as f:
                    json.dump(all_time, f, indent=2, default=str)
            
            print(f"Updated {updated} final results")
    except Exception as e:
        print(f"Update expired error {e}")
        import traceback
        traceback.print_exc()


if __name__=="__main__":
    wita,utc = wita_now()
    print(f"V9.5 WINDOW {MIN_MINUTE}-{MAX_MINUTE} + RESULT CHECKER - WITA {wita}")
    matches = cek_parallel()
    save_batch(matches)
    print("=== Checking FT results for AI learning ===")
    update_expired_results()
    print(f"Done V9.5 WINDOW {MIN_MINUTE}-{MAX_MINUTE} + RESULTS")
