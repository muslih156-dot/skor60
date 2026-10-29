
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, requests

WITA = timezone(timedelta(hours=8))
now = datetime.now(WITA)

st.set_page_config(page_title="Trading System V3.6 - Menit 60", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', sans-serif; }
.stApp { background: #f8fafc; }
header { visibility: hidden; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

def load_matches():
    matches = []
    for p in ["data/matches.json", "data/archive/all_time.json", "data/all_time.json", "matches.json", "all_time.json"]:
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                    if isinstance(d, list) and len(d) > 0:
                        matches = d
                        break
            except:
                pass
    return matches

matches = load_matches()

MODAL = 50000
PROFIT_WIN = 40000

if not matches:
    st.markdown(f"""
    <div style="background:#0f172a; border-radius:16px; padding:24px; color:white; text-align:center;">
        <div style="font-size:48px;">⚽</div>
        <div style="font-size:22px; font-weight:800; margin-top:12px;">Trading Bola Menit 60 - Last Goal System</div>
        <div style="font-size:14px; color:#94a3b8; margin-top:8px;">Window 60-66 skor 0-0 | Modal Rp 50rb | Menunggu data pertama...</div>
        <div style="margin-top:16px; background:#1e293b; border-radius:12px; padding:16px; display:inline-block;">
            <div style="font-size:12px; color:#22c55e;">✅ SYSTEM RESET - MULAI DARI 0</div>
            <div style="font-size:10px; color:#64748b; margin-top:4px;">Bot akan scan otomatis tiap 5 menit via GitHub Actions + cron-job.org</div>
            <div style="font-size:10px; color:#64748b;">Logic: Deteksi 0-0 di menit 60 → FT 2-1 = 3 gol di 60-90 = WIN Over 0.5</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.info("📭 Belum ada data. Bot akan mulai kumpulin data baru mulai sekarang. Tunggu 5-15 menit setelah bot jalan.")
    st.stop()

# Calculate stats
selesai = len([m for m in matches if m.get("is_ft") or m.get("final_score")])
win = len([m for m in matches if m.get("result")=="WIN"])
lose = len([m for m in matches if m.get("result")=="LOSE"])
total = len(matches)
wr = (win/selesai*100) if selesai>0 else 0
profit = win*PROFIT_WIN - lose*MODAL
roi = (profit/(selesai*MODAL)*100) if selesai>0 else 0

st.markdown(f"""
<div style="background:#0f172a; border-radius:16px; padding:20px; color:white; margin-bottom:16px;">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <div style="font-size:20px; font-weight:800;">⚽ Trading Bola Menit 60 - Last Goal System</div>
            <div style="font-size:11px; color:#94a3b8; margin-top:4px;">Window 60-66 skor 0-0 | Modal Rp 50rb | {total} match | {win}W-{lose}L {wr:.1f}% WR | Profit Rp {profit}</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:10px; background:#22c55e; color:white; padding:4px 10px; border-radius:12px; display:inline-block;">LIVE • BOT AKTIF</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

c1,c2,c3,c4 = st.columns(4)
c1.metric("Total", total)
c2.metric("Selesai FT", selesai, f"{win}W-{lose}L")
c3.metric("Win Rate", f"{wr:.1f}%", f"Rp {profit}")
c4.metric("ROI", f"{roi:.1f}%", f"Modal Rp {selesai*MODAL}")

st.markdown("### 📋 Peluang Terakhir (0-0 di 60' → FT)")
st.markdown(f"*Logic: Deteksi 0-0 (60') → FT 2-1 (total 3 gol) = 3 gol setelah 60' = WIN*")

if matches:
    rows = []
    for m in sorted(matches, key=lambda x: x.get("created_at",""), reverse=True)[:20]:
        home = m.get("home_team","-")
        away = m.get("away_team","-")
        liga = m.get("league","-")
        ft = m.get("final_score") or m.get("live_score") or "LIVE"
        result = m.get("result","LIVE")
        profit_txt = "+40rb" if result=="WIN" else "-50rb" if result=="LOSE" else "LIVE"
        rows.append({
            "Match": f"{home} vs {away}",
            "Liga": liga,
            "Deteksi": "0-0 (60')",
            "FT": ft,
            "Gol setelah 60'": ft,
            "Result": result,
            "Profit": profit_txt
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
else:
    st.warning("Menunggu data pertama dari bot...")
