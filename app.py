
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os

WITA = timezone(timedelta(hours=8))
now = datetime.now(WITA)

st.set_page_config(page_title="Trading Bola 60", page_icon="⚽", layout="wide")

st.markdown("""
<style>
.stApp { background: #f8fafc; }
</style>
""", unsafe_allow_html=True)

def load_matches():
    files = ["data/matches.json", "data/archive/all_time.json", "data/all_time.json", "matches.json", "all_time.json"]
    out = []
    for fp in files:
        if os.path.exists(fp):
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                    if isinstance(d, list):
                        out.extend(d)
            except:
                pass
    # dedup
    seen = {}
    for m in out:
        mid = str(m.get("match_id") or m.get("id") or f"{m.get('home_team')}-{m.get('away_team')}")
        if mid not in seen:
            seen[mid] = m
    return list(seen.values())

matches = load_matches()

MODAL = 50000
PROFIT = 40000

selesai = 0
win = 0
lose = 0
for m in matches:
    fs = str(m.get("final_score") or m.get("live_score") or "")
    if m.get("is_ft") or m.get("final_score"):
        selesai += 1
        if fs and fs != "0-0" and "-" in fs:
            try:
                hg, ag = map(int, fs.split("-"))
                if hg+ag > 0:
                    win += 1
                else:
                    lose += 1
            except:
                if m.get("result") == "WIN":
                    win += 1
                else:
                    lose += 1
        else:
            if m.get("result") == "WIN":
                win += 1
            else:
                lose += 1

total = len(matches)
wr = (win/selesai*100) if selesai>0 else 0
profit = win*PROFIT - lose*MODAL
roi = (profit/(selesai*MODAL)*100) if selesai>0 else 0

st.markdown(f"""
<div style="background:#0f172a; color:white; padding:20px; border-radius:16px; margin-bottom:16px;">
<h2 style="margin:0; color:white;">⚽ Trading Bola Menit 60 - Last Goal System</h2>
<p style="color:#94a3b8; font-size:12px; margin:6px 0 0 0;">Window 60-66 skor 0-0 | Modal Rp 50rb | {total} match | {win}W-{lose}L {wr:.1f}% WR | Profit Rp {profit} | V3.6 FIXED</p>
<p style="color:#4ade80; font-size:10px; margin:4px 0 0 0;">✅ FIXED - requirements.txt sudah ada streamlit + Logic 0-0 -> 2-1 = WIN</p>
</div>
""", unsafe_allow_html=True)

c1,c2,c3,c4 = st.columns(4)
c1.metric("Total", total)
c2.metric("Selesai", selesai, f"{win}W-{lose}L")
c3.metric("Win Rate", f"{wr:.1f}%", f"Rp {profit}")
c4.metric("ROI", f"{roi:.1f}%")

st.markdown("### 📋 20 Peluang Terakhir (0-0 di 60' -> FT)")

if total == 0:
    st.warning("Data kosong - upload data/matches.json dengan 11W-6L yang gw kasih")
    st.info("File harus di: data/matches.json di GitHub")
else:
    rows = []
    for m in sorted(matches, key=lambda x: x.get("created_at",""), reverse=True)[:20]:
        home = m.get("home_team","-")
        away = m.get("away_team","-")
        league = m.get("league","-")
        ft = m.get("final_score") or m.get("live_score") or "0-0"
        res = m.get("result") or ("WIN" if ft!="0-0" and "-" in ft and sum(map(int, ft.split("-")[:2]))>0 else "LOSE" if m.get("is_ft") else "LIVE")
        # calc profit
        if res == "WIN":
            p = "+40rb"
        elif res == "LOSE":
            p = "-50rb"
        else:
            p = "LIVE"
        rows.append({
            "Match": f"{home} vs {away}",
            "Liga": league,
            "Deteksi": "0-0 (60')",
            "FT": ft,
            "Gol setelah 60'": ft if ft!="0-0" else "0",
            "Result": res,
            "Profit": p
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=600)
    st.success(f"Logic: Deteksi 0-0 di menit 60, kalau FT 2-1 (total 3 gol) berarti 3 gol terjadi di menit 60-90 = WIN Over 0.5 ✅")
