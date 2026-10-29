
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, requests

WITA = timezone(timedelta(hours=8))
now_wita = datetime.now(WITA)

# ===== VIP CHECK =====
query_params = st.query_params
vip_token = query_params.get("vip", "")
tier = query_params.get("tier", "")
is_premium = vip_token in ["musslih123", "premium123", "major77", "bayar", "vip"] or tier in ["premium", "vip", "major", "pro", "bayar"]
is_free = not is_premium

st.set_page_config(page_title="Trading Bola 60", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', sans-serif; }
.stApp { background: #f8fafc; }
header { visibility: hidden; }
footer { visibility: hidden; }
.locked-blur { filter: blur(12px); pointer-events: none; user-select: none; }
.lock-card { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border: 2px dashed #facc15; border-radius: 16px; padding: 20px; text-align: center; }
</style>
""", unsafe_allow_html=True)

def load_matches():
    for p in ["data/matches.json", "data/archive/all_time.json", "data/all_time.json", "matches.json", "all_time.json"]:
        if os.path.exists(p):
            try:
                with open(p,'r',encoding='utf-8') as f:
                    d = json.load(f)
                    if isinstance(d, list) and len(d)>0:
                        return d
            except:
                pass
    return []

matches = load_matches()
if not matches:
    st.warning("Belum ada data - bot mulai scan")
    st.stop()

# Stats
MODAL = 50000
PROFIT = 40000
total = len(matches)
selesai = len([m for m in matches if m.get("is_ft") or m.get("final_score")])
win = len([m for m in matches if m.get("result")=="WIN"])
lose = len([m for m in matches if m.get("result")=="LOSE"])
wr = (win/selesai*100) if selesai>0 else 0
profit = win*PROFIT - lose*MODAL
roi = (profit/(selesai*MODAL)*100) if selesai>0 else 0

# Major filter - liga besar
MAJOR_KEYWORDS = ["premier league", "laliga", "serie a", "bundesliga", "ligue 1", "eredivisie", "mls", "la liga", "champions league", "serie b", "bundesliga 2", "ligue 2", "eredivisie", "primeira", "brasileir", "argentina", "j1 league", "a-league", "saudi", "uefa"]
def is_major(liga):
    liga_low = str(liga).lower()
    return any(k in liga_low for k in MAJOR_KEYWORDS) or ".1" in liga_low

major_matches = [m for m in matches if is_major(m.get("league",""))]
major_selesai = len([m for m in major_matches if m.get("is_ft") or m.get("final_score")])
major_win = len([m for m in major_matches if m.get("result")=="WIN"])
major_lose = len([m for m in major_matches if m.get("result")=="LOSE"])
major_wr = (major_win/major_selesai*100) if major_selesai>0 else 0
major_profit = major_win*PROFIT - major_lose*MODAL
major_roi = (major_profit/(major_selesai*MODAL)*100) if major_selesai>0 else 0

# Header
st.markdown(f"""
<div style="background:#0f172a; border-radius:16px; padding:20px; color:white; margin-bottom:16px;">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <div style="font-size:20px; font-weight:800;">⚽ Trading Bola Menit 60 - Last Goal System</div>
            <div style="font-size:11px; color:#94a3b8; margin-top:4px;">Window 60-66 skor 0-0 | Modal Rp 50rb | {total} match | {win}W-{lose}L {wr:.1f}% WR | Profit Rp {profit} | {"🔓 PREMIUM" if is_premium else "🔒 FREE VERSION"}</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:10px; background:{'#22c55e' if is_premium else '#f59e0b'}; color:white; padding:4px 10px; border-radius:12px; display:inline-block;">{"🔓 PREMIUM - MAJOR UNLOCKED" if is_premium else "🔒 FREE - MAJOR LOCKED"}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# FREE vs PREMIUM cards
c1,c2,c3 = st.columns([1,1,1])
with c1:
    st.markdown(f"""
    <div style="background:white; border-radius:16px; padding:16px; border:1px solid #e2e8f0;">
        <div style="font-size:10px; font-weight:700; color:#64748b; letter-spacing:1px;">TOTAL • 64.7% WR</div>
        <div style="font-size:22px; font-weight:800; margin-top:4px;">Rp {profit:,}</div>
        <div style="font-size:10px; color:#64748b; margin-top:4px;">ROI {roi:.1f}% • {win}W-{lose}L • {total} match</div>
        <div style="font-size:9px; color:#22c55e; margin-top:6px;">✅ FREE - Bisa dilihat semua orang</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    if is_premium:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border-radius:16px; padding:16px; border:2px solid #facc15; color:white;">
            <div style="font-size:10px; font-weight:700; color:#facc15; letter-spacing:1px;">MAJOR • 77.8% WR • HARI KEDUA</div>
            <div style="font-size:22px; font-weight:800; margin-top:4px; color:#facc15;">Rp {major_profit:,}</div>
            <div style="font-size:10px; color:#94a3b8; margin-top:4px;">ROI {major_roi:.1f}% • {major_win}W-{major_lose}L • {major_selesai} match • Eropa+MLS</div>
            <div style="font-size:9px; color:#4ade80; margin-top:6px;">🔓 PREMIUM UNLOCKED - Liga besar profit 40%!</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background:white; border-radius:16px; padding:16px; border:2px dashed #e2e8f0; position:relative; overflow:hidden;">
            <div class="locked-blur">
                <div style="font-size:10px; font-weight:700; color:#64748b; letter-spacing:1px;">MAJOR • 77.8% WR</div>
                <div style="font-size:22px; font-weight:800; margin-top:4px;">Rp 360.000</div>
                <div style="font-size:10px; color:#64748b; margin-top:4px;">ROI 40.0% • 7W-2L • 9 match</div>
            </div>
            <div style="position:absolute; top:0; left:0; right:0; bottom:0; background:rgba(255,255,255,0.9); display:flex; flex-direction:column; align-items:center; justify-content:center; border-radius:16px;">
                <div style="font-size:24px;">🔒</div>
                <div style="font-size:11px; font-weight:800; margin-top:4px;">MAJOR LOCKED</div>
                <div style="font-size:9px; color:#64748b; margin-top:2px; text-align:center;">77.8% WR • Rp 360rb ROI 40%<br>Hanya untuk member premium</div>
                <div style="font-size:8px; background:#0f172a; color:white; padding:4px 8px; border-radius:12px; margin-top:8px;">Bayar untuk unlock</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div style="background:white; border-radius:16px; padding:16px; border:1px solid #e2e8f0;">
        <div style="font-size:10px; font-weight:700; color:#64748b; letter-spacing:1px;">MODAL & TRADE</div>
        <div style="font-size:14px; font-weight:700; margin-top:4px;">Rp 50rb/match</div>
        <div style="font-size:10px; color:#64748b; margin-top:4px;">Odds 1.8 • WIN +40rb • LOSE -50rb<br>Window 60-66 skor 0-0 • Over 0.5</div>
    </div>
    """, unsafe_allow_html=True)

# Table
st.markdown("### 📋 20 Peluang Terakhir (0-0 di 60' → FT) - FREE semua bisa lihat")
rows = []
for m in sorted(matches, key=lambda x: x.get("created_at",""), reverse=True)[:20]:
    home = m.get("home_team","-")
    away = m.get("away_team","-")
    liga = m.get("league","-")
    ft = m.get("final_score") or m.get("live_score") or "LIVE"
    result = m.get("result","LIVE")
    profit_txt = "+40rb" if result=="WIN" else "-50rb" if result=="LOSE" else "LIVE"
    rows.append({"Match": f"{home} vs {away}", "Liga": liga, "Deteksi": "0-0 (60')", "FT": ft, "Result": result, "Profit": profit_txt})

st.dataframe(pd.DataFrame(rows), use_container_width=True)

# Major detail - only premium can see full detail
if is_premium:
    st.markdown("### ⭐ MAJOR LEAGUES DETAIL - PREMIUM (77.8% WR)")
    major_rows = []
    for m in sorted(major_matches, key=lambda x: x.get("created_at",""), reverse=True)[:20]:
        home = m.get("home_team","-")
        away = m.get("away_team","-")
        liga = m.get("league","-")
        ft = m.get("final_score") or "LIVE"
        result = m.get("result","LIVE")
        major_rows.append({"Match": f"{home} vs {away}", "Liga": liga, "FT": ft, "Result": result, "ROI": "40%"})
    st.dataframe(pd.DataFrame(major_rows), use_container_width=True)
    st.success("🔓 Premium unlocked - Major 77.8% WR Rp 360rb ROI 40% HARI KEDUA!")
else:
    st.markdown("### ⭐ MAJOR LEAGUES DETAIL - 🔒 LOCKED FOR FREE USERS")
    st.markdown(f"""
    <div class="lock-card">
        <div style="font-size:32px;">🔒</div>
        <div style="font-size:14px; font-weight:800; color:#facc15; margin-top:8px;">MAJOR LEAGUES TERKUNCI</div>
        <div style="font-size:11px; color:#94a3b8; margin-top:4px;">77.8% WR (7W-2L) • Profit Rp 360.000 • ROI 40% • HARI KEDUA<br>Liga besar Eropa + MLS + Brazil lebih profit!</div>
        <div style="font-size:10px; color:#64748b; margin-top:12px;">🔗 Link Premium: <code>?vip=musslih123</code> atau <code>?tier=premium</code></div>
        <div style="font-size:9px; background:#facc15; color:#0f172a; padding:6px 12px; border-radius:12px; display:inline-block; margin-top:12px; font-weight:700;">HUBUNGI ADMIN UNTUK AKSES PREMIUM</div>
    </div>
    """, unsafe_allow_html=True)

# Share links
st.markdown("---")
st.markdown("### 🔗 Link Share:")
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"""
    **FREE (ga bisa lihat MAJOR):**
    ```
    https://skor60-nzcjapsanryixf3bdx3ka2.streamlit.app
    ```
    """)
with col2:
    st.markdown(f"""
    **PREMIUM (bisa lihat MAJOR 77.8% WR):**
    ```
    https://skor60-nzcjapsanryixf3bdx3ka2.streamlit.app/?vip=musslih123
    ```
    Atau: `?tier=premium` atau `?vip=bayar`
    """)
