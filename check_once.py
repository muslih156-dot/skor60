
import os, requests
from datetime import datetime, timedelta
from supabase import create_client

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase connected")

def wita_now():
    utc = datetime.utcnow()
    wita = utc + timedelta(hours=8)
    return wita, utc

def send_telegram(pesan):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": pesan, "parse_mode": "HTML"}
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except:
        return False

def already_sent(mid):
    if not supabase:
        return False
    try:
        res = supabase.table("matches").select("match_id").eq("match_id", str(mid)).execute()
        return len(res.data) > 0
    except:
        return False

def save_to_supabase(mid, home, away, league, minute, status_text, warning=""):
    if not supabase:
        return
    try:
        full_status = status_text
        if warning:
            full_status = f"{status_text} | {warning}"
        data = {"match_id": str(mid), "home_team": home, "away_team": away, "league": league, "minute": minute, "score": "0-0", "status": full_status}
        supabase.table("matches").upsert(data, on_conflict="match_id").execute()
        print(f"Saved {mid} {home} vs {away} Menit {minute} {league} {warning}")
    except Exception as e:
        print(f"Save error {e}")

def parse_clock(clock_str, detail_str=""):
    try:
        s = (clock_str or detail_str or "").strip()
        if not s:
            return 0
        su = s.upper()
        if "HT" in su or "PARUH" in su:
            return 45
        if "FT" in su or "FINAL" in su:
            return 90
        s = s.replace("'", "").replace('"', "").replace("’", "")
        if ":" in s:
            return int(s.split(":")[0])
        if "+" in s:
            return int(s.split("+")[0].split()[0])
        parts = s.split()
        return int(float(parts[0])) if parts else 0
    except:
        return 0

def get_warning_flags(league_name, home, away, league_code=""):
    warnings = []
    low_league = league_name.lower()
    low_home = home.lower()
    low_away = away.lower()
    low_code = league_code.lower()
    combined = f"{low_league} {low_home} {low_away} {low_code}"

    if any(x in combined for x in ["women", "woman", "female", "putri", "wanita"]):
        warnings.append("⚠️ LIGA WANITA")
    youth_keys = ["u17", "u19", "u21", "u23", "u18", "u20", "youth", "young", "junior", "reserves", "reserve", " b ", " ii", " iii", " u-", "akademi", "academy"]
    if any(x in combined for x in youth_keys):
        warnings.append("⚠️ TIM MUDA/CADANGAN")
    if ".2" in league_code or ".3" in league_code or "divisi 1" in low_league or "vtora" in low_league or "2. liga" in low_league:
        warnings.append("⚠️ DIVISI BAWAH")
    weird_keys = ["futsal", "beach", "esports", "amateur", "persahabatan", "friendly", "uji coba", "klub teluk", "gulf", "nextgen", "pokalen", "vtor a", "meistriliiga"]
    if any(x in low_league for x in weird_keys):
        warnings.append("⚠️ LIGA MINOR/ANEH")
    if " ii" in low_home or " ii" in low_away or " iii" in low_home or " iii" in low_away:
        warnings.append("⚠️ TIM II/III")
    return " | ".join(warnings) if warnings else ""

def fetch_all_espn_leagues():
    all_leagues = []
    # 1. Coba core API - struktur baru
    urls = [
        "https://sports.core.api.espn.com/v2/sports/soccer/leagues?limit=500",
        "https://site.api.espn.com/apis/site/v2/sports/soccer/leagues",
        "https://site.api.espn.com/apis/site/v2/sports/soccer",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            print(f"Fetch leagues {url} -> {r.status_code} len {len(r.text)}")
            if r.status_code != 200:
                continue
            j = r.json()
            items = []
            # Struktur 1: core API -> items = [{"$ref": ".../leagues/eng.1", "id": "eng.1", "name": "Premier League"}] atau direct
            if "items" in j:
                items = j["items"]
            elif "leagues" in j:
                items = j["leagues"]
            elif "sports" in j:
                # site api /soccer -> sports[0].leagues
                try:
                    items = j["sports"][0]["leagues"]
                except:
                    items = j.get("leagues", [])
            elif "data" in j:
                items = j["data"].get("leagues", [])

            print(f"Raw items count {len(items)} from {url}")
            for it in items[:5]:
                print(f"Sample item: {str(it)[:200]}")

            for it in items:
                if not isinstance(it, dict):
                    continue
                # Core API kadang cuma $ref
                slug = it.get("slug") or it.get("abbreviation") or it.get("id") or it.get("name")
                # Kalau id = "eng.1" atau ref mengandung eng.1
                if "$ref" in it:
                    ref = it["$ref"]
                    # ref like .../leagues/eng.1 or .../leagues/123
                    try:
                        slug_from_ref = ref.split("/leagues/")[-1].split("?")[0].split("/")[0]
                        if slug_from_ref:
                            slug = slug_from_ref
                    except:
                        pass
                name = it.get("name") or it.get("displayName") or slug
                if slug and isinstance(slug, str) and len(slug) < 50:
                    # Filter yang terlihat seperti kode liga, bukan angka random panjang
                    # ESPN slug biasanya mengandung . atau huruf, bukan angka murni panjang
                    if slug not in [x[0] for x in all_leagues]:
                        all_leagues.append((slug, name))

            print(f"Found {len(all_leagues)} leagues after parsing {url}")
            if all_leagues:
                break
        except Exception as e:
            print(f"Leagues fetch error {url}: {e}")
            import traceback
            traceback.print_exc()
            continue

    if not all_leagues:
        print("Discovery gagal, pakai hardcode fallback + SEA + AUS")
        fallback = ["all","eng.1","eng.2","esp.1","ger.1","ita.1","fra.1","ned.1","por.1","sco.1","bel.1","tur.1",
                    "uefa.champions","uefa.europa","uefa.europa.conf","uefa.nations",
                    "ind.1","tha.1","mys.1","vie.1","sgp.1","phi.1","idn.1",
                    "jpn.1","kor.1","chn.1","aus.1","nzl.1",
                    "sau.1","uae.1","qat.1","afc.champions","afc.champions.league.2",
                    "mex.1","usa.1","bra.1","arg.1","conmebol.libertadores",
                    "den.1","bul.1","est.1","aze.1","pol.1","cze.1","gre.1","rus.1"]
        all_leagues = [(c, c) for c in fallback]

    seen = {}
    for slug, name in all_leagues:
        if slug not in seen:
            seen[slug] = name
    print(f"Total unique leagues untuk di-scan: {len(seen)}")
    return list(seen.items())

def fetch_espn_league_events(league_slug, date_str):
    base = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_slug}/scoreboard"
    url = f"{base}?dates={date_str}" if date_str else base
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        return r.json().get("events", [])
    except:
        return []

def cek_all_leagues():
    wita, utc = wita_now()
    print(f"WITA NOW: {wita.strftime('%Y-%m-%d %H:%M:%S')} WITA | UTC {utc.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    date_wita = wita.strftime("%Y%m%d")
    date_wita_yest = (wita - timedelta(days=1)).strftime("%Y%m%d")
    date_utc = utc.strftime("%Y%m%d")

    leagues = fetch_all_espn_leagues()
    top_priority = ["all","eng.1","esp.1","ita.1","ger.1","fra.1","uefa.champions","uefa.europa","uefa.europa.conf","uefa.nations","ind.1","aus.1","jpn.1","usa.1","bra.1","mex.1","ned.1","por.1","sau.1","tha.1","mys.1","vie.1"]
    def sort_key(item):
        slug, name = item
        return (0 if slug in top_priority else 1, slug)
    leagues_sorted = sorted(leagues, key=sort_key)
    leagues_to_scan = leagues_sorted[:100]
    print(f"Scan {len(leagues_to_scan)} liga (dari {len(leagues)} total) - prioritas top + SEA + AUS + semua dunia")

    all_events = {}
    for slug, lname in leagues_to_scan:
        for d in [date_wita, date_wita_yest, date_utc, ""]:
            evs = fetch_espn_league_events(slug, d)
            if evs:
                print(f"ESPN {slug} dates={d or 'live'} -> {len(evs)} events")
            for ev in evs:
                all_events[ev.get("id")] = (ev, slug, lname)

    print(f"Total UNIQUE events gabungan semua liga dunia: {len(all_events)}")

    out = []
    inprog = []
    sched = 0
    fin = 0
    for ev_id, (ev, league_slug, league_name_from_list) in all_events.items():
        try:
            comp = ev.get("competitions", [{}])[0]
            status = comp.get("status", {})
            tname = status.get("type", {}).get("name", "")
            state = status.get("type", {}).get("state", "")
            clock = status.get("displayClock", "") or status.get("clock", "") or ""
            detail = status.get("type", {}).get("shortDetail", "") or status.get("type", {}).get("detail", "") or ""
            minute = parse_clock(clock, detail)
            comps = comp.get("competitors", [])
            if len(comps) < 2:
                continue
            home = next((c for c in comps if c.get("homeAway") == "home"), comps[0])
            away = next((c for c in comps if c.get("homeAway") == "away"), comps[1])
            hs = int(home.get("score", 0) or 0)
            aws = int(away.get("score", 0) or 0)
            hname = home.get("team", {}).get("displayName", "Home")
            aname = away.get("team", {}).get("displayName", "Away")
            real_league_name = (ev.get("leagues", [{}])[0].get("name") if ev.get("leagues") else league_name_from_list) or league_slug

            if "IN_PROGRESS" in tname or state == "in":
                warning = get_warning_flags(real_league_name, hname, aname, league_slug)
                line = f"{hname} {hs}-{aws} {aname} Menit {minute} ({clock}/{detail}) {real_league_name} {warning}"
                inprog.append((minute, line, ev, hs, aws, hname, aname, real_league_name, league_slug, warning))
            elif "PRE" in tname or state == "pre":
                sched += 1
            elif "POST" in tname or state == "post":
                fin += 1
        except:
            continue

    inprog_sorted = sorted(inprog, key=lambda x: x[0])
    print(f"--- {len(inprog_sorted)} IN-PROGRESS | {sched} SCHEDULED | {fin} FINISHED | WITA {wita.strftime('%H:%M')} ---")
    for minute, line, ev, hs, aws, hname, aname, real_league_name, league_slug, warning in inprog_sorted[:40]:
        print(line)
        if 55 <= minute <= 68 and hs == 0 and aws == 0:
            out.append({"id": ev.get("id"), "home": hname, "away": aname, "league": real_league_name, "minute": minute, "warning": warning, "slug": league_slug})

    if len(inprog_sorted) > 40:
        print(f"... dan {len(inprog_sorted)-40} lagi tidak ditampilkan")
    print("--- end list ---")
    return out

if __name__ == "__main__":
    wita, utc = wita_now()
    print(f"Phase 1 - ESPN V8.1 ALL LEAGUES FIX PARSER - WITA {wita} | UTC {utc}")
    matches = cek_all_leagues()
    print(f"Found {len(matches)} match di jendela 55-68 0-0 (semua liga dunia)")
    for m in matches:
        if already_sent(m["id"]):
            print(f"Skip {m['id']} sudah ada")
            continue
        save_to_supabase(m["id"], m["home"], m["away"], m["league"], m["minute"], "AKTIF", m["warning"])
        warning_text = f"\n\n{m['warning']}" if m["warning"] else ""
        pesan = f"⚽ <b>MENIT 60 - 0-0</b>\n\n🏟️ {m['home']} vs {m['away']}\n🏆 {m['league']} ({m['slug']})\n⏱️ Menit {m['minute']}{warning_text}\n\nID: {m['id']}"
        send_telegram(pesan)
    print("Done V8.1 ALL LEAGUES")
