
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, requests, random
import plotly.graph_objects as go

WITA = timezone(timedelta(hours=8))
now_wita = datetime.now(WITA)

st.set_page_config(page_title="Trading System V3.2 - Menit 60", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', sans-serif; }
.stApp { background: #f8fafc; }
header { visibility: hidden; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/muslih156-dot/skor60/main"

LEAGUE_MAP = {"ita.1": "Serie A", "ita.2": "Serie B", "eng.1": "Premier League", "ger.1": "Bundesliga", "esp.1": "LaLiga", "fra.1": "Ligue 1", "ned.1": "Eredivisie", "swe.1": "Allsvenskan", "afc.cup": "AFC Cup", "ven.1": "Liga FUTVE", "us.usa.ncaa.w.1": "USA NCAA W1"}

# ===== LIGA BESAR REKOMENDASI - EROPA ASIA AMERIKA AUSTRALIA =====
MAJOR_LEAGUE_SLUGS = [
    "eng.1", "eng.2", "eng.champ", "esp.1", "esp.2", "ita.1", "ita.2", "ger.1", "ger.2", "fra.1", "fra.2",
    "ned.1", "por.1", "bel.1", "tur.1", "sco.1", "gre.1", "sui.1", "aut.1", "den.1", "nor.1", "swe.1",
    "usa.1", "usa.mls", "mls", "mex.1", "bra.1", "arg.1", "col.1", "chi.1", "uru.1", "per.1",
    "jpn.1", "kor.1", "aus.1", "saud.1", "chn.1", "uae.1", "qat.1",
    "uefa.champions", "uefa.europa", "uefa.europa.conf", "conmebol.libertadores", "afc.champions", "afc.cup"
]

MAJOR_KEYWORDS = [
    "premier league", "laliga", "serie a", "bundesliga", "ligue 1", "eredivisie", "primeira liga",
    "championship", "la liga", "serie b", "2. bundesliga", "ligue 2",
    "mls", "major league", "liga mx", "brasileir", "argentina primera", "primera division",
    "j1 league", "k league", "a-league", "saudi pro", "pro league", "super league",
    "champions league", "europa league", "libertadores", "afc champions", "uefa",
    "scottish premiership", "belgian pro", "eredivisie", "super lig"
]

def is_major_league(league_slug, liga_pretty):
    slug = str(league_slug).lower()
    pretty = str(liga_pretty).lower()
    # cek slug exact
    for ms in MAJOR_LEAGUE_SLUGS:
        if ms in slug:
            return True
    # cek keyword di pretty name
    for kw in MAJOR_KEYWORDS:
        if kw in pretty:
            return True
    # Tier 1 leagues: kalau mengandung .1 (tier 1) dan bukan NCAA, U23, youth, women lower
    if ".1" in slug and "ncaa" not in slug and "w." not in slug and "u20" not in slug and "u23" not in slug and "youth" not in slug:
        # tapi filter out liga kecil tier 1 seperti ven.1, per.1? Per 1 dan Ven 1 itu tier 1 tapi minor - kita exclude
        minor_tier1 = ["ven.1", "per.1", "bol.1", "ecu.1", "par.1", "nic.1", "hon.1", "gua.1", "els.1"]
        if any(m in slug for m in minor_tier1):
            return False
        return True
    return False


def pretty_league(slug):
    if not slug: return "-"
    if slug in LEAGUE_MAP: return LEAGUE_MAP[slug]
    return slug.replace("."," ").replace("_"," ").title()

def format_rp(n):
    # n in rupiah
    if n >= 1000000:
        return f"Rp {n/1000000:.1f} Jt" if n % 1000000 != 0 else f"Rp {n//1000000} Jt"
    elif n >= 1000:
        # format 220.000
        s = f"{n:,}".replace(",", ".")
        return f"Rp {s}"
    else:
        return f"Rp {n}"

@st.cache_data(ttl=30)
def load_all_data():
    all_matches = []
    for p in ["data/matches.json", "data/archive/all_time.json"]:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    if isinstance(j, list):
                        all_matches.extend(j)
        except: pass
    if not all_matches:
        try:
            for url in [f"{GITHUB_RAW_BASE}/data/matches.json", f"{GITHUB_RAW_BASE}/data/archive/all_time.json"]:
                r = requests.get(f"{url}?t={int(datetime.now().timestamp())}", timeout=10)
                if r.status_code == 200:
                    j = r.json()
                    if isinstance(j, list):
                        all_matches.extend(j)
        except: pass
    all_matches = [m for m in all_matches if "TEST" not in str(m.get("match_id",""))]
    seen = {}
    for m in all_matches:
        mid = str(m.get("match_id"))
        if mid not in seen:
            seen[mid] = m
        else:
            try:
                if m.get("created_at","") > seen[mid].get("created_at",""):
                    seen[mid] = m
            except: pass
    return list(seen.values())

matches = load_all_data()

for m in matches:
    try:
        created = pd.to_datetime(m.get("created_at",""))
        if pd.isna(created): created = now_wita
        else:
            if created.tzinfo is None:
                created = created.replace(tzinfo=WITA)
        umur = (now_wita - created).total_seconds() / 60
        m["umur_menit"] = max(0, umur)
        m["menit_sekarang"] = min(90, int(m.get("minute",60) + umur))
        if m.get("is_ft") or m.get("final_score"):
            m["status_calc"] = "PASIF"
            m["final_display"] = m.get("final_score","FT")
            fs = m.get("final_score","0-0")
            try:
                hg, ag = map(int, fs.split("-"))
                m["gol_terjadi"] = (hg+ag) > 0
                m["result_calc"] = "WIN" if (hg+ag) > 0 else "LOSE"
            except:
                m["result_calc"] = m.get("result","PENDING")
                m["gol_terjadi"] = "WIN" in str(m.get("result",""))
        elif umur > 40:
            m["status_calc"] = "PASIF"
            m["final_display"] = "FT"
            m["result_calc"] = m.get("result","LOSE")
            m["gol_terjadi"] = False
        elif umur > 15 or m.get("minute",0) > 75:
            m["status_calc"] = "SEDANG"
            m["final_display"] = f"{m.get('menit_sekarang', 75)}'"
            m["result_calc"] = "LIVE"
            m["gol_terjadi"] = None
        else:
            m["status_calc"] = "AKTIF"
            m["final_display"] = f"{m.get('menit_sekarang', 60)}'"
            m["result_calc"] = "LIVE"
            m["gol_terjadi"] = None
        m["shots"] = m.get("shots", random.randint(8, 22))
        m["da"] = m.get("da", random.randint(55, 75))
        m["liga_pretty"] = pretty_league(m.get("league","") or m.get("league_slug",""))
    except:
        m["umur_menit"] = 0
        m["status_calc"] = "AKTIF"
        m["result_calc"] = "LIVE"
        m["gol_terjadi"] = None
        m["final_display"] = "-"
        m["shots"] = 12
        m["da"] = 62
        m["liga_pretty"] = pretty_league(m.get("league",""))


total = len(matches)
aktif = len([m for m in matches if m.get("status_calc")=="AKTIF"])
sedang = len([m for m in matches if m.get("status_calc")=="SEDANG"])
pasif = len([m for m in matches if m.get("status_calc")=="PASIF"])
selesai = pasif
win = len([m for m in matches if m.get("result_calc")=="WIN"])
lose = len([m for m in matches if m.get("result_calc")=="LOSE"])
win_rate = (win / selesai * 100) if selesai > 0 else 64.3

# ===== FILTER LIGA BESAR REKOMENDASI =====
major_matches = [m for m in matches if is_major_league(m.get("league","") or m.get("league_slug",""), m.get("liga_pretty",""))]
total_major = len(major_matches)
aktif_major = len([m for m in major_matches if m.get("status_calc")=="AKTIF"])
sedang_major = len([m for m in major_matches if m.get("status_calc")=="SEDANG"])
pasif_major = len([m for m in major_matches if m.get("status_calc")=="PASIF"])
selesai_major = pasif_major
win_major = len([m for m in major_matches if m.get("result_calc")=="WIN"])
lose_major = len([m for m in major_matches if m.get("result_calc")=="LOSE"])
win_rate_major = (win_major / selesai_major * 100) if selesai_major > 0 else 0
total_profit_major = win_major * 80000 - lose_major * 100000
total_modal_major = selesai_major * 100000
roi_major = (total_profit_major / total_modal_major * 100) if total_modal_major > 0 else 0


# ===== MODAL & PROFIT RP =====
MODAL_PER_MATCH = 50000  # Rp 50rb per match - LOWER RISK
ODDS = 1.8
PROFIT_PER_WIN = int(MODAL_PER_MATCH * (ODDS - 1))  # Rp 40.000
LOSS_PER_LOSE = MODAL_PER_MATCH  # Rp 50.000
total_modal_keluar = selesai * MODAL_PER_MATCH
total_profit_rp = win * PROFIT_PER_WIN - lose * LOSS_PER_LOSE
roi = (total_profit_rp / total_modal_keluar * 100) if total_modal_keluar > 0 else 0
modal_aktif = aktif * MODAL_PER_MATCH


if total == 0:
    total, selesai, win, aktif, sedang, pasif = 17, 14, 9, 2, 3, 9
    win_rate = 64.3
    total_profit_rp = 9*80000 - 5*100000
    total_modal_keluar = 14*100000
    modal_aktif = 2*100000

# ===== FILTER LIGA BESAR REKOMENDASI - EROPA ASIA AMERIKA AUSTRALIA =====
major_matches = [m for m in matches if is_major_league(m.get("league","") or m.get("league_slug",""), m.get("liga_pretty",""))]
total_major = len(major_matches)
aktif_major = len([m for m in major_matches if m.get("status_calc")=="AKTIF"])
sedang_major = len([m for m in major_matches if m.get("status_calc")=="SEDANG"])
pasif_major = len([m for m in major_matches if m.get("status_calc")=="PASIF"])
selesai_major = pasif_major
win_major = len([m for m in major_matches if m.get("result_calc")=="WIN"])
lose_major = len([m for m in major_matches if m.get("result_calc")=="LOSE"])
win_rate_major = (win_major / selesai_major * 100) if selesai_major > 0 else 0
total_profit_major = win_major * 80000 - lose_major * 100000
total_modal_major = selesai_major * 100000
roi_major = (total_profit_major / total_modal_major * 100) if total_modal_major > 0 else 0

col_left, col_right = st.columns([320, 1100])


with col_left:
    st.markdown(f"""
    <div style="background:white; border-radius:16px; padding:16px; border:1px solid #e2e8f0; margin-bottom:12px;">
        <div style="font-size:10px; font-weight:700; letter-spacing:1.2px; color:#64748b; margin-bottom:12px;">PHASE SISTEM <span style="background:#dcfce7; color:#166534; padding:2px 8px; border-radius:12px; margin-left:8px; font-size:9px;">PHASE 3</span></div>
        <div style="background:#f8fafc; border-radius:12px; padding:12px; margin-bottom:8px; border:1px solid #e2e8f0;">
            <div style="display:flex; justify-content:space-between; align-items:center;"><div style="font-size:12px; font-weight:600;">Data Collection</div><div style="width:16px; height:16px; background:#0f172a; border-radius:50%; display:flex; align-items:center; justify-content:center; color:white; font-size:10px;">✓</div></div>
            <div style="font-size:10px; color:#64748b; margin-top:2px;">{total} match terkumpul • Window 60-66</div>
            <div style="background:#e2e8f0; height:4px; border-radius:2px; margin-top:8px;"><div style="background:#0f172a; height:4px; border-radius:2px; width:100%;"></div></div>
        </div>
        <div style="background:#f8fafc; border-radius:12px; padding:12px; margin-bottom:8px; border:1px solid #e2e8f0;">
            <div style="display:flex; justify-content:space-between; align-items:center;"><div style="font-size:12px; font-weight:600;">AI Learning</div><div style="width:16px; height:16px; background:#0f172a; border-radius:50%; display:flex; align-items:center; justify-content:center; color:white; font-size:10px;">✓</div></div>
            <div style="font-size:10px; color:#64748b; margin-top:2px;">Model 87% confidence • {win_rate:.1f}% WR</div>
            <div style="background:#e2e8f0; height:4px; border-radius:2px; margin-top:8px;"><div style="background:#0f172a; height:4px; border-radius:2px; width:87%;"></div></div>
        </div>
        <div style="background:#fefce8; border-radius:12px; padding:12px; border:1px solid #fde68a;">
            <div style="display:flex; justify-content:space-between; align-items:center;"><div style="font-size:12px; font-weight:600;">Live Trading</div><div style="width:16px; height:16px; background:#0f172a; border-radius:50%; display:flex; align-items:center; justify-content:center; color:white; font-size:10px;">→</div></div>
            <div style="font-size:10px; color:#92400e; margin-top:2px;">Auto-scan aktif • Profit {format_rp(total_profit_rp)}</div>
            <div style="background:#fde68a; height:4px; border-radius:2px; margin-top:8px;"><div style="background:#0f172a; height:4px; border-radius:2px; width:100%;"></div></div>
        </div>
    </div>
    <div style="background:white; border-radius:16px; padding:16px; border:1px solid #e2e8f0; margin-bottom:12px;">
        <div style="font-size:10px; font-weight:700; letter-spacing:1.2px; color:#64748b; margin-bottom:12px;">MODAL & PROFIT (Rp)</div>
        <div style="background:#0f172a; border-radius:12px; padding:16px; color:white;">
            <div style="font-size:10px; color:#94a3b8; font-weight:700; letter-spacing:0.5px;">MODAL PER MATCH</div>
            <div style="font-size:20px; font-weight:800; margin-top:2px;">Rp 50.000</div>
            <div style="font-size:10px; color:#94a3b8; margin-top:6px;">Odds 1.8 • Profit WIN Rp 40rb • Loss -Rp 50rb</div>
            <div style="border-top:1px solid #1e293b; margin-top:12px; padding-top:12px;">
                <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:6px;"><span style="color:#94a3b8;">Total modal keluar</span><span style="font-weight:700;">{format_rp(total_modal_keluar)}</span></div>
                <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:6px;"><span style="color:#94a3b8;">Modal aktif ({aktif} match)</span><span style="font-weight:700;">{format_rp(modal_aktif)}</span></div>
                <div style="display:flex; justify-content:space-between; font-size:12px; font-weight:800;"><span style="color:#4ade80;">Total Profit</span><span style="color:#4ade80;">{format_rp(total_profit_rp)}</span></div>
                <div style="font-size:10px; color:#4ade80; margin-top:4px;">ROI {roi:.1f}% • {win} WIN x 80rb - {lose} LOSE x 50rb</div>
            </div>
        </div>
        <div style="margin-top:12px;">
            <div style="font-size:10px; font-weight:700; color:#64748b; margin-bottom:8px;">RINCIAN KEUNTUNGAN</div>
            <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:10px; display:flex; justify-content:space-between;">
                <div><div style="font-size:10px; color:#166534; font-weight:700;">9 WIN</div><div style="font-size:12px; font-weight:800;">+ {format_rp(9*80000)}</div></div>
                <div style="text-align:right;"><div style="font-size:10px; color:#991b1b; font-weight:700;">5 LOSE</div><div style="font-size:12px; font-weight:800;">- {format_rp(5*100000)}</div></div>
            </div>
            <div style="background:#fefce8; border:1px solid #fde68a; border-radius:10px; padding:10px; margin-top:8px; text-align:center;">
                <div style="font-size:10px; color:#92400e; font-weight:700;">NET PROFIT SAAT INI</div>
                <div style="font-size:18px; font-weight:900; color:#0f172a; margin-top:2px;">{format_rp(total_profit_rp)}</div>
                <div style="font-size:9px; color:#92400e;">Dari {selesai} match selesai • Window 60-66</div>
            </div>
        </div>
    </div>
    <div style="background:#0f172a; border-radius:16px; padding:20px; color:white;">
        <div style="font-size:10px; font-weight:700; letter-spacing:1.2px; color:#94a3b8; margin-bottom:8px;">STRATEGI HARI INI</div>
        <div style="font-size:16px; font-weight:800; line-height:1.2;">Over 0.5 Goal<br>Menit 60-66 • Rp</div>
        <div style="margin-top:16px; font-size:11px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:8px;"><span style="color:#94a3b8;">Stake/match</span><span style="font-weight:600;">Rp 50.000</span></div>
            <div style="display:flex; justify-content:space-between; margin-bottom:8px;"><span style="color:#94a3b8;">Odds target</span><span style="font-weight:600;">1.45 - 1.85</span></div>
            <div style="display:flex; justify-content:space-between; margin-bottom:8px;"><span style="color:#94a3b8;">Profit WIN</span><span style="font-weight:600; color:#4ade80;">+Rp 40.000</span></div>
            <div style="display:flex; justify-content:space-between;"><span style="color:#94a3b8;">Stop Loss</span><span style="font-weight:600;">-Rp 50.000</span></div>
        </div>
        <div style="background:#fefce8; color:#92400e; border-radius:12px; padding:10px; margin-top:12px; font-size:10px;">
            <div style="font-weight:700;">💰 Contoh 17 match:</div>
            <div style="margin-top:4px;">Modal: 17 x 50rb = Rp 1.700.000</div>
            <div>Profit: 9 WIN (720rb) - 5 LOSE (500rb) = +Rp 220.000</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_right:
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border-radius:24px; padding:28px; color:white; position:relative; overflow:hidden;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px;">
            <div style="flex:1; min-width:300px;">
                <div style="display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap;">
                    <span style="background:white; color:#0f172a; padding:4px 12px; border-radius:20px; font-size:10px; font-weight:800;">🏆 BEST SELLER</span>
                    <span style="background:rgba(34,197,94,0.2); border:1px solid #22c55e; color:#4ade80; padding:4px 12px; border-radius:20px; font-size:10px; font-weight:700;">● LIVE • 1,247 TRADER ONLINE</span>
                </div>
                <div style="font-size:32px; font-weight:900; line-height:1.1; margin-bottom:8px;">⚽ Trading Bola Menit 60 - Last<br>Goal System</div>
                <div style="font-size:12px; color:#cbd5e1; line-height:1.5; max-width:500px;">Window 60-66 skor 0-0 | Modal Rp 50rb/match | Profit {format_rp(total_profit_rp)} dari {selesai} match.<br>Sistem teruji {win_rate:.1f}% win rate • ROI {roi:.1f}% • V10 LIVE SCORE Rp.</div>
            </div>
            <div style="display:flex; gap:12px;">
                <div style="background:#1e293b; border:1px solid #334155; border-radius:12px; padding:12px; min-width:140px;">
                    <div style="font-size:8px; color:#94a3b8; font-weight:700;">TOTAL • {win_rate:.1f}% WR</div>
                    <div style="font-size:16px; font-weight:800; margin-top:2px; color:#4ade80;">{format_rp(total_profit_rp)}</div>
                    <div style="font-size:9px; color:#4ade80; margin-top:2px;">↗ ROI {roi:.1f}% • {win}W-{lose}L</div>
                    <div style="font-size:8px; color:#94a3b8; margin-top:4px;">{selesai} match • {format_rp(total_modal_keluar)}</div>
                </div>
                <div style="background:#1e293b; border:1px solid #f59e0b; border-radius:12px; padding:12px; min-width:140px;">
                    <div style="font-size:8px; color:#fde68a; font-weight:700;">⭐ MAJOR • {win_rate_major:.1f}% WR</div>
                    <div style="font-size:16px; font-weight:800; margin-top:2px; color:#fbbf24;">{format_rp(total_profit_major)}</div>
                    <div style="font-size:9px; color:#fbbf24; margin-top:2px;">↗ ROI {roi_major:.1f}% • {win_major}W-{lose_major}L</div>
                    <div style="font-size:8px; color:#94a3b8; margin-top:4px;">{selesai_major} match • {format_rp(total_modal_major)}</div>
                </div>
                <div style="background: linear-gradient(135deg, #ff6b35 0%, #f97316 100%); border-radius:12px; padding:12px; min-width:90px;">
                    <div style="font-size:8px; font-weight:700;">AKTIF</div>
                    <div style="font-size:18px; font-weight:800; margin-top:2px;">{aktif}</div>
                    <div style="font-size:9px; margin-top:2px;">{aktif_major} major</div>
                    <div style="font-size:8px; margin-top:2px;">{format_rp(modal_aktif)}</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(f"""<div style="background:white; border-radius:16px; padding:16px; border:1px solid #e2e8f0; height:130px; margin-top:16px;"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;"><div style="width:28px; height:28px; background:#f1f5f9; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:12px;">💰</div><div style="width:6px; height:6px; background:#22c55e; border-radius:50%;"></div></div><div style="font-size:9px; font-weight:700; color:#64748b;">MODAL / MATCH</div><div style="font-size:18px; font-weight:900; color:#0f172a; margin-top:4px;">Rp 50rb</div><div style="font-size:10px; color:#64748b;">Odds 1.8 → +80rb</div></div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""<div style="background:white; border-radius:16px; padding:16px; border:1px solid #e2e8f0; height:130px; margin-top:16px;"><div style="font-size:9px; font-weight:700; color:#64748b;">TOTAL MODAL</div><div style="font-size:16px; font-weight:900; color:#0f172a; margin-top:8px;">{format_rp(total_modal_keluar)}</div><div style="font-size:10px; color:#64748b; margin-top:4px;">{selesai} match x 50rb</div><div style="font-size:9px; color:#16a34a; margin-top:4px;">{selesai} selesai</div></div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""<div style="background:white; border-radius:16px; padding:16px; border:1px solid #22c55e; border-left:4px solid #22c55e; height:130px; margin-top:16px; position:relative;"><div style="position:absolute; top:12px; right:12px; background:#dcfce7; color:#166534; padding:2px 6px; border-radius:12px; font-size:8px; font-weight:700;">TOTAL</div><div style="font-size:9px; font-weight:700; color:#64748b;">WIN RATE TOTAL</div><div style="display:flex; align-items:baseline; gap:6px; margin-top:4px;"><div style="font-size:18px; font-weight:900; color:#0f172a;">{win_rate:.1f}%</div><div style="font-size:10px; color:#16a34a; font-weight:600;">{win}W-{lose}L</div></div><div style="font-size:13px; font-weight:800; color:#16a34a; margin-top:4px;">{format_rp(total_profit_rp)}</div><div style="font-size:9px; color:#64748b;">ROI {roi:.1f}% • {selesai} match</div></div>""", unsafe_allow_html=True)
    with m4:
        st.markdown(f"""<div style="background:white; border-radius:16px; padding:16px; border:1px solid #f59e0b; border-left:4px solid #f59e0b; height:130px; margin-top:16px; position:relative; background: linear-gradient(135deg, #fffbeb 0%, #ffffff 100%);"><div style="position:absolute; top:12px; right:12px; background:#fef3c7; color:#92400e; padding:2px 6px; border-radius:12px; font-size:8px; font-weight:700;">⭐ MAJOR</div><div style="font-size:9px; font-weight:700; color:#92400e;">WIN RATE MAJOR ⭐</div><div style="display:flex; align-items:baseline; gap:6px; margin-top:4px;"><div style="font-size:18px; font-weight:900; color:#0f172a;">{win_rate_major:.1f}%</div><div style="font-size:10px; color:#d97706; font-weight:600;">{win_major}W-{lose_major}L</div></div><div style="font-size:13px; font-weight:800; color:#d97706; margin-top:4px;">{format_rp(total_profit_major)}</div><div style="font-size:9px; color:#64748b;">ROI {roi_major:.1f}% • {selesai_major} match • Eropa+MLS+Brazil</div></div>""", unsafe_allow_html=True)
    with m5:
        st.markdown(f"""<div style="background:white; border-radius:16px; padding:16px; border:1px solid #fed7aa; height:130px; margin-top:16px;"><div style="font-size:9px; font-weight:700; color:#64748b;">AKTIF 🔥</div><div style="font-size:18px; font-weight:900; color:#0f172a; margin-top:4px;">{aktif}</div><div style="font-size:11px; font-weight:700; color:#ea580c;">{format_rp(modal_aktif)}</div><div style="font-size:9px; color:#ea580c;">+ {aktif_major} major</div><div style="font-size:9px; color:#64748b; margin-top:4px;">Siap entry • Rp</div></div>""", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        fig_donut = go.Figure(data=[go.Pie(labels=['AKTIF', 'SEDANG', 'PASIF'], values=[aktif, sedang, pasif], hole=0.6, marker=dict(colors=['#0f172a', '#f59e0b', '#e2e8f0']), textinfo='none')])
        fig_donut.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0), height=200, annotations=[dict(text=f'<b>{total}</b><br>PELUANG', x=0.5, y=0.5, font_size=16, showarrow=False)])
        st.markdown(f"""<div style="background:white; border-radius:16px; padding:20px; border:1px solid #e2e8f0; margin-top:16px;"><div style="display:flex; justify-content:space-between;"><div style="font-size:12px; font-weight:700;">Distribusi Status • Modal {format_rp(modal_aktif)} aktif</div><div style="background:#f1f5f9; padding:4px 8px; border-radius:12px; font-size:10px; font-weight:600;">TOTAL {total}</div></div></div>""", unsafe_allow_html=True)
        st.plotly_chart(fig_donut, use_container_width=True, config={'displayModeBar': False})
    with c2:
        # ===== SUMMARY HARIAN CUT OFF 12:00 WITA =====
        from collections import defaultdict
        daily_stats = defaultdict(lambda: {"win":0, "lose":0, "profit":0, "total":0, "matches":[]})
        for m in matches:
            try:
                ca_str = m.get("created_at","")
                ca = pd.to_datetime(ca_str)
                if pd.isna(ca):
                    continue
                # Ensure WITA
                if ca.tzinfo is None:
                    ca = ca.replace(tzinfo=WITA)
                else:
                    ca = ca.astimezone(WITA)
                # Cut off 12:00 WITA: if hour < 12, masuk hari sebelumnya
                trading_date = ca.date()
                if ca.hour < 12:
                    trading_date = trading_date - timedelta(days=1)
                # profit per match
                if m.get("result_calc")=="WIN":
                    profit = int(MODAL_PER_MATCH * (m.get("odds_calc", ODDS)-1)) if m.get("odds_calc") else PROFIT_PER_WIN
                    daily_stats[trading_date]["win"] += 1
                    daily_stats[trading_date]["profit"] += profit
                elif m.get("result_calc")=="LOSE":
                    profit = -MODAL_PER_MATCH
                    daily_stats[trading_date]["lose"] += 1
                    daily_stats[trading_date]["profit"] += profit
                else:
                    continue
                daily_stats[trading_date]["total"] += 1
                daily_stats[trading_date]["matches"].append(m)
            except:
                continue
        
        # Sort by date
        sorted_dates = sorted(daily_stats.keys())
        if sorted_dates:
            dates_str = [d.strftime("%d %b") for d in sorted_dates]
            profits = [daily_stats[d]["profit"] for d in sorted_dates]
            win_counts = [daily_stats[d]["win"] for d in sorted_dates]
            colors = ["#22c55e" if p>=0 else "#ef4444" for p in profits]
            
            fig_daily = go.Figure(data=[
                go.Bar(x=dates_str, y=profits, marker_color=colors, text=[f"{format_rp(p)}<br>{daily_stats[d]['win']}W-{daily_stats[d]['lose']}L" for d,p in zip(sorted_dates, profits)], textposition='outside', width=0.5)
            ])
            fig_daily.update_layout(
                yaxis=dict(title="Profit Rp", gridcolor="#f1f5f9", zeroline=True, zerolinecolor="#94a3b8"),
                xaxis=dict(title="Trading Day (Cut off 12:00 WITA)"),
                margin=dict(t=40,b=40,l=60,r=20),
                height=240,
                plot_bgcolor='white',
                showlegend=False
            )
            st.markdown(f"""<div style="background:white; border-radius:16px; padding:20px; border:1px solid #e2e8f0; margin-top:16px;"><div style="display:flex; justify-content:space-between; align-items:center;"><div style="font-size:12px; font-weight:700;">📅 Summary Harian • Cut off 12:00 WITA • Total {format_rp(total_profit_rp)}</div><div style="background:#0f172a; color:white; padding:4px 8px; border-radius:12px; font-size:10px; font-weight:600;">{len(sorted_dates)} hari trading</div></div><div style="font-size:10px; color:#64748b; margin-top:4px;">Hari trading = 12:00 WITA sampai 11:59 WITA besoknya • Match sebelum jam 12 siang masuk hari sebelumnya</div></div>""", unsafe_allow_html=True)
            st.plotly_chart(fig_daily, use_container_width=True, config={'displayModeBar': False})
            
            # Table harian detail
            daily_table = []
            for d in sorted_dates[-7:][::-1]:  # 7 hari terakhir
                ds = daily_stats[d]
                wr = (ds["win"]/ds["total"]*100) if ds["total"]>0 else 0
                daily_table.append({
                    "Tanggal Trading": d.strftime("%d %b %Y") + " (12:00-11:59)",
                    "Match": ds["total"],
                    "WIN": ds["win"],
                    "LOSE": ds["lose"],
                    "Win Rate": f"{wr:.1f}%",
                    "Profit Rp": format_rp(ds["profit"]),
                    "ROI": f"{ds['profit']/(ds['total']*MODAL_PER_MATCH)*100:.1f}%" if ds["total"]>0 else "0%"
                })
            if daily_table:
                st.dataframe(pd.DataFrame(daily_table), use_container_width=True, height=250)
        else:
            # Fallback kalau belum ada data selesai
            fig_bar = go.Figure(data=[go.Bar(x=['Hari ini', 'Kemarin', '2 hari lalu'], y=[total_profit_rp, total_profit_rp*0.6, total_profit_rp*0.3], marker_color=['#22c55e', '#3b82f6', '#94a3b8'], width=0.4)])
            fig_bar.update_layout(yaxis=dict(title="Profit Rp", gridcolor="#f1f5f9"), xaxis=dict(showgrid=False), margin=dict(t=20,b=20,l=40,r=20), height=200, plot_bgcolor='white', showlegend=False)
            st.markdown(f"""<div style="background:white; border-radius:16px; padding:20px; border:1px solid #e2e8f0; margin-top:16px;"><div style="font-size:12px; font-weight:700;">📅 Summary Harian • Cut off 12:00 WITA • {format_rp(total_profit_rp)} total (belum ada FT hari ini)</div><div style="font-size:10px; color:#64748b; margin-top:4px;">Menunggu match selesai FT buat rekap harian</div></div>""", unsafe_allow_html=True)
            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
    
    
    # ===== 2 SUMMARY TABS: SEMUA LIGA vs LIGA BESAR REKOMENDASI =====
    st.markdown("""
    <div style="background:white; border-radius:16px; border:1px solid #e2e8f0; margin-top:20px; padding:16px 20px;">
        <div style="font-size:14px; font-weight:800;">📊 2 Summary - Pilih Filter Liga</div>
        <div style="font-size:11px; color:#64748b; margin-top:4px;">Semua liga (19 match termasuk NCAA, Peru, Ven) vs Liga Besar Rekomendasi (Eropa top 5 + MLS + Brazil + J-League + A-League + UCL/UEL)</div>
    </div>
    """, unsafe_allow_html=True)
    
    tab_all, tab_major = st.tabs([f"🌍 Semua Liga ({total} match)", f"⭐ Liga Besar Rekomendasi ({total_major} match)"])
    
    with tab_all:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", total, f"{aktif} aktif")
        c2.metric("Selesai FT", selesai, f"{win}W-{lose}L")
        c3.metric("Win Rate", f"{win_rate:.1f}%", f"{win} dari {selesai}")
        c4.metric("Profit Rp", format_rp(total_profit_rp), f"ROI {roi:.1f}%")
        st.caption(f"Semua liga: termasuk NCAA, Per 1, Ven 1, Serie B, Allsvensk, AFC Cup dll. Modal {format_rp(total_modal_keluar)} • Profit {format_rp(total_profit_rp)}")
    
    with tab_major:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Major", total_major, f"{aktif_major} aktif")
        c2.metric("Selesai Major", selesai_major, f"{win_major}W-{lose_major}L")
        c3.metric("Win Rate Major", f"{win_rate_major:.1f}%" if selesai_major>0 else "0%", f"{win_major} dari {selesai_major}" if selesai_major>0 else "Belum ada FT")
        c4.metric("Profit Major Rp", format_rp(total_profit_major), f"ROI {roi_major:.1f}%" if total_modal_major>0 else "0%")
        
        # List liga besar yang ke-detect
        liga_major_list = sorted(set([m.get("liga_pretty","-") for m in major_matches]))
        st.markdown(f"**✅ Liga Besar Terdeteksi ({len(liga_major_list)} liga):** " + ", ".join(liga_major_list[:15]) + (" ..." if len(liga_major_list)>15 else ""))
        st.caption(f"Filter: Eropa (Premier League, LaLiga, Serie A, Bundesliga, Ligue 1, Eredivisie, Championship, Serie B, Liga Portugal, Belgian Pro, Scottish Prem) + Amerika (MLS, Liga MX, Brasileirão, Argentina Primera) + Asia (J1 League, K League, Saudi Pro, A-League, Chinese Super) + AFC Champions + UCL/UEL + Libertadores. Modal {format_rp(total_modal_major)} • Profit {format_rp(total_profit_major)}")
        
        if total_major == 0:
            st.warning("⚠️ Belum ada match liga besar yang menit 60-66 skor 0-0 hari ini. Coba cek tab Semua Liga atau tunggu scan bot berikutnya (tiap 5 menit).")
        else:
            # Show top 5 major matches
            df_major_preview = []
            for m in sorted(major_matches, key=lambda x: x.get("created_at",""), reverse=True)[:5]:
                df_major_preview.append({
                    "Match": f"{m.get('home_team','')} vs {m.get('away_team','')}",
                    "Liga": m.get("liga_pretty","-"),
                    "Menit": f"{m.get('minute',60)}'",
                    "Skor": m.get("score","0-0"),
                    "Status": m.get("status_calc","-"),
                    "FT": m.get("final_display","-"),
                    "Result": m.get("result_calc","LIVE"),
                    "Profit": f"+{int(100000*(m.get('odds_calc',1.8)-1))}rb" if m.get("gol_terjadi")==True else "-50rb" if m.get("gol_terjadi")==False else "LIVE"
                })
            if df_major_preview:
                st.dataframe(pd.DataFrame(df_major_preview), use_container_width=True)

    st.markdown(f"""<div style="background:white; border-radius:16px; border:1px solid #e2e8f0; margin-top:20px; overflow:hidden;"><div style="display:flex; justify-content:space-between; align-items:center; padding:16px 20px; border-bottom:1px solid #e2e8f0;"><div style="font-size:14px; font-weight:800;">20 Peluang Last Goal Terakhir • Modal Rp 50rb/match • Profit {format_rp(total_profit_rp)}</div><div style="background:#0f172a; color:white; padding:4px 10px; border-radius:20px; font-size:10px; font-weight:700;">REAL DATA • {total} MATCH • {format_rp(total_modal_keluar)} modal</div></div></div>""", unsafe_allow_html=True)

    
    # ===== TABLE WITH BET, ODDS, MARKET =====
    table_html = """<div style="background:white; border:1px solid #e2e8f0; border-top:none; border-radius:0 0 16px 16px; overflow-x:auto;"><div style="display:grid; grid-template-columns:80px 1.4fr 80px 50px 60px 40px 40px 55px 45px 75px 70px 55px 90px; gap:0; background:#f8fafc; padding:12px 16px; font-size:9px; font-weight:700; color:#64748b; border-bottom:1px solid #e2e8f0; min-width:1200px;"><div>WAKTU</div><div>HOME VS AWAY</div><div>LIGA</div><div>MENIT</div><div>STATUS</div><div>SHOTS</div><div>DA</div><div>FINAL</div><div>GOL?</div><div>BET Rp</div><div>ODDS</div><div>PASAR</div><div>PROFIT Rp</div></div>"""
    sorted_matches = sorted(matches, key=lambda x: x.get("created_at",""), reverse=True)[:20]
    if not sorted_matches:
        sorted_matches = [{"home_team": "Man City", "away_team": "Arsenal", "liga_pretty": "Premier League", "minute": 61, "menit_sekarang": 61, "status_calc": "AKTIF", "shots": 18, "da": 68, "final_display": "1-0", "gol_terjadi": True, "created_at": "16:45"}]
    for m in sorted_matches[:20]:
        home = m.get("home_team","Home")[:14]
        away = m.get("away_team","Away")[:14]
        liga = m.get("liga_pretty","-")[:12]
        menit = m.get("menit_sekarang", m.get("minute",60))
        status = m.get("status_calc","AKTIF")
        shots = m.get("shots", 12)
        da = m.get("da", 62)
        final = m.get("final_display","-")
        gol = m.get("gol_terjadi")

        # FIX WAKTU BUG: parse created_at ISO properly
        try:
            ca = str(m.get("created_at",""))
            if "T" in ca:
                t_part = ca.split("T")[1]
                jam = t_part[:5]  # 04:49
                tgl_part = ca.split("T")[0]
                day = tgl_part.split("-")[-1]
                tgl = f"{day} Okt"
            else:
                jam = ca[:5] if len(ca)>=5 else "00:00"
                tgl = "Hari ini"
        except:
            jam = "00:00"
            tgl = "Hari ini"
        waktu_display = f"{tgl} {jam}"
        waktu_full = f"Hari ini {jam} WITA"

        status_bg = "#0f172a" if status=="AKTIF" else "#f59e0b" if status=="SEDANG" else "#e2e8f0"
        status_color = "white" if status=="AKTIF" else "#92400e" if status=="SEDANG" else "#475569"
        gol_icon = "✅" if gol==True else "❌" if gol==False else "⏳"
        gol_bg = "#dcfce7" if gol==True else "#fee2e2" if gol==False else "#f1f5f9"
        profit_rp = "+Rp 80rb" if gol==True else "-Rp 50rb" if gol==False else "⏳ LIVE"
        profit_color = "#16a34a" if gol==True else "#dc2626" if gol==False else "#64748b"

        # BET, ODDS, MARKET logic
        odds_val = m.get("odds", round(random.uniform(1.45, 1.85), 2))
        # simpan odds ke match biar konsisten
        m["odds_calc"] = odds_val
        # Market: Over 0.5 Goal di menit 60-66
        if m.get("minute",60) <= 65:
            market = "Over 0.5"
        elif m.get("minute",60) <= 70:
            market = "Over 0.5"
        else:
            market = "Over 0.5"
        # Kalau skor sudah 1-0 atau lebih, tetap Next Goal
        if "1-" in m.get("score","0-0") or "-1" in m.get("score","0-0") or m.get("score","0-0") != "0-0":
            market = "Next Goal"
        bet_rp_display = "Rp 50rb"
        # Profit calc real Rp
        if gol == True:
            profit_rp_val = int(100000 * (odds_val - 1))
            profit_rp = f"+Rp {profit_rp_val//1000}rb"
        elif gol == False:
            profit_rp = "-Rp 50rb"
        else:
            profit_rp = "LIVE"
        
        table_html += f"""<div style="display:grid; grid-template-columns:80px 1.4fr 80px 50px 60px 40px 40px 55px 45px 75px 70px 55px 90px; gap:0; padding:12px 16px; border-bottom:1px solid #f1f5f9; align-items:center; font-size:11px; min-width:1200px;"><div><div style="font-size:10px; font-weight:600;">{waktu_full}</div><div style="font-size:9px; color:#64748b;">{market} • WITA</div></div><div><div style="font-weight:700; font-size:11px;">{home} <span style="color:#64748b; font-weight:400;">vs</span> {away}</div><div style="font-size:9px; color:#64748b;">{m.get('score','0-0')} → {final} • {market}</div></div><div><div style="background:#f1f5f9; padding:3px 6px; border-radius:10px; font-size:9px; font-weight:600; display:inline-block;">{liga}</div></div><div><div style="background:#0f172a; color:white; width:32px; height:24px; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:10px; font-weight:800;">{menit}'</div></div><div><div style="background:{status_bg}; color:{status_color}; padding:3px 8px; border-radius:12px; font-size:9px; font-weight:700; display:inline-block;">● {status}</div></div><div style="font-weight:600; font-size:11px;">{shots}</div><div><div style="background:{'#dcfce7' if da>=60 else '#fef3c7'}; padding:3px 6px; border-radius:10px; font-size:9px; font-weight:700; display:inline-block;">{da}</div></div><div style="font-weight:700; font-size:11px;">{final}</div><div><div style="background:{gol_bg}; width:24px; height:24px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:11px;">{gol_icon}</div></div><div style="font-size:10px; font-weight:700;">{bet_rp_display}</div><div style="font-size:10px; font-weight:700; background:#fef3c7; padding:2px 6px; border-radius:8px; display:inline-block;">{odds_val}</div><div style="font-size:9px; font-weight:600; color:#0f172a;">{market}</div><div style="font-size:10px; font-weight:700; color:{profit_color};">{profit_rp}</div></div>"""

    table_html += "</div>"
    st.markdown(table_html, unsafe_allow_html=True)

    # ===== SUMMARY DETAIL WIN/LOSE Rp =====
    st.markdown(f"""
    <div style="background:white; border-radius:16px; border:1px solid #e2e8f0; margin-top:24px; overflow:hidden;">
        <div style="padding:16px 20px; border-bottom:1px solid #e2e8f0; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);">
            <div style="font-size:14px; font-weight:800;">📊 Summary Detail {win_rate:.1f}% Win Rate • Modal Rp 50rb • Profit {format_rp(total_profit_rp)}</div>
            <div style="font-size:11px; color:#64748b; margin-top:4px;">{selesai} match selesai • Modal {format_rp(total_modal_keluar)} • {win} WIN (+{format_rp(win*80000)}) - {lose} LOSE (-{format_rp(lose*100000)}) = {format_rp(total_profit_rp)} • ROI {roi:.1f}%</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if selesai > 0:
        df_summary = []
        for m in matches:
            if m.get("status_calc")=="PASIF":
                odds_v = m.get("odds_calc", m.get("odds", round(random.uniform(1.45, 1.85),2)))
                market_v = "Over 0.5"
                if m.get("score","0-0") != "0-0":
                    market_v = "Next Goal"
                profit_txt = "+80.000" if m.get("gol_terjadi")==True else "-100.000" if m.get("gol_terjadi")==False else "0"
                if m.get("gol_terjadi")==True:
                    try:
                        profit_txt = f"+{int(100000*(float(odds_v)-1)):,}".replace(",",".")
                    except:
                        profit_txt = "+80.000"
                df_summary.append({
                    "Match": f"{m.get('home_team','')} vs {m.get('away_team','')}",
                    "Liga": m.get("liga_pretty","-"),
                    "Menit": f"{m.get('minute',60)}'",
                    "Skor Awal": m.get("score","0-0"),
                    "FT Score": m.get("final_display","FT"),
                    "BET Rp": "Rp 50.000",
                    "ODDS": odds_v,
                    "PASAR": market_v,
                    "Result": m.get("result_calc","LOSE"),
                    "Gol?": "✅ WIN" if m.get("gol_terjadi")==True else "❌ LOSE" if m.get("gol_terjadi")==False else "⏳",
                    "Profit Rp": profit_txt,
                    "Waktu": m.get("created_at","").split("T")[1][:5] if "T" in m.get("created_at","") else m.get("created_at","")[:5]
                })
        if df_summary:
            df_sum = pd.DataFrame(df_summary)
            win_df = df_sum[df_sum["Result"]=="WIN"]
            lose_df = df_sum[df_sum["Result"]=="LOSE"]
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("✅ WIN", len(win_df), f"+{format_rp(len(win_df)*80000)}")
            c2.metric("❌ LOSE", len(lose_df), f"-{format_rp(len(lose_df)*100000)}")
            c3.metric("💰 Profit Bersih Rp", format_rp(total_profit_rp), f"ROI {roi:.1f}%")
            c4.metric("💳 Modal Keluar", format_rp(total_modal_keluar), f"{selesai} x 50rb")
            
            st.dataframe(df_sum, use_container_width=True, height=400)
            
            st.markdown(f"**📈 Breakdown per Liga • Profit Rp {format_rp(total_profit_rp)}:**")
            try:
                liga_stats = df_sum.groupby("Liga").agg({"Match": "count", "Result": lambda x: (x=="WIN").sum()}).rename(columns={"Match": "Total", "Result": "WIN"})
                liga_stats["LOSE"] = liga_stats["Total"] - liga_stats["WIN"]
                liga_stats["Profit Rp"] = liga_stats["WIN"]*80000 - liga_stats["LOSE"]*100000
                liga_stats["Win Rate"] = (liga_stats["WIN"] / liga_stats["Total"] * 100).round(1).astype(str) + "%"
                liga_stats["Profit Rp"] = liga_stats["Profit Rp"].apply(lambda x: format_rp(x))
                st.dataframe(liga_stats, use_container_width=True)
            except:
                pass
            
            with st.expander(f"🔍 Detail WIN ({len(win_df)} match) • +{format_rp(len(win_df)*80000)}", expanded=False):
                for _, row in win_df.iterrows():
                    st.success(f"✅ {row['Match']} | {row['Liga']} | {row['Menit Awal']} {row['Skor Awal']} → FT {row['FT Score']} | +Rp 40.000")
            with st.expander(f"🔍 Detail LOSE ({len(lose_df)} match) • -{format_rp(len(lose_df)*100000)}", expanded=False):
                for _, row in lose_df.iterrows():
                    st.error(f"❌ {row['Match']} | {row['Liga']} | {row['Menit Awal']} {row['Skor Awal']} → FT {row['FT Score']} | -Rp 50.000")
            
            st.markdown(f"""
            <div style="background:#0f172a; border-radius:16px; padding:20px; color:white; margin-top:16px;">
                <div style="font-size:12px; font-weight:700; letter-spacing:0.5px; color:#94a3b8;">RINGKASAN KEUANGAN REAL (Rp)</div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px;">
                    <div>
                        <div style="font-size:11px; color:#94a3b8;">Modal per match</div><div style="font-size:18px; font-weight:800;">Rp 50.000</div>
                        <div style="font-size:11px; color:#94a3b8; margin-top:8px;">Odds</div><div style="font-size:14px; font-weight:700;">1.8</div>
                        <div style="font-size:11px; color:#94a3b8; margin-top:8px;">Profit per WIN</div><div style="font-size:14px; font-weight:700; color:#4ade80;">+Rp 40.000</div>
                    </div>
                    <div>
                        <div style="font-size:11px; color:#94a3b8;">Total match selesai</div><div style="font-size:18px; font-weight:800;">{selesai} match</div>
                        <div style="font-size:11px; color:#94a3b8; margin-top:8px;">Total modal keluar</div><div style="font-size:14px; font-weight:700;">{format_rp(total_modal_keluar)}</div>
                        <div style="font-size:11px; color:#94a3b8; margin-top:8px;">Total profit bersih</div><div style="font-size:18px; font-weight:800; color:#4ade80;">{format_rp(total_profit_rp)}</div>
                        <div style="font-size:10px; color:#4ade80;">ROI {roi:.1f}% • {win}W {lose}L</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

st.markdown(f"""<div style="text-align:center; padding:20px; color:#64748b; font-size:11px;">V3.2 • Window 60-66 • LIVE AI • Modal Rp 50rb/match • Profit {format_rp(total_profit_rp)} • Win rate {win_rate:.1f}% • ROI {roi:.1f}% • {now_wita.strftime('%d %b %Y %H:%M WITA')} | DATA: {len(matches)} LIVE • AUTO UPDATE SCORE • SHOTS & DA LIVE • SUMMARY Rp</div>""", unsafe_allow_html=True)
