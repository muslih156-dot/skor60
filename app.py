
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, requests, random
import plotly.graph_objects as go

WITA = timezone(timedelta(hours=8))
now_wita = datetime.now(WITA)

st.set_page_config(page_title="Trading System V3.6 - Menit 60", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")

LEAGUE_MAP = {"ita.1": "Serie A", "eng.1": "Premier League", "ger.1": "Bundesliga", "esp.1": "LaLiga", "fra.1": "Ligue 1", "usa.1": "MLS", "bra.1": "Brasileirao"}

def pretty_league(slug):
    if not slug: return "-"
    if slug in LEAGUE_MAP: return LEAGUE_MAP[slug]
    return slug.replace("."," ").title()

def format_rp(n):
    if n >= 1000000:
        return f"Rp {n/1000000:.1f} Jt"
    elif n >= 1000:
        s = f"{n:,}".replace(",", ".")
        return f"Rp {s}"
    else:
        return f"Rp {n}"

def load_all_data():
    matches = []
    for fp in ["data/matches.json", "data/archive/all_time.json"]:
        if os.path.exists(fp):
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        matches.extend(data)
            except:
                pass
    # Deduplicate
    seen = {}
    for m in matches:
        mid = str(m.get("match_id") or m.get("id") or f"{m.get('home_team')}-{m.get('away_team')}")
        if mid not in seen:
            seen[mid] = m
    return list(seen.values())

matches = load_all_data()

# FIX STATUS
for m in matches:
    try:
        created = pd.to_datetime(m.get("created_at",""))
        if pd.isna(created):
            created = now_wita
        else:
            if created.tzinfo is None:
                created = created.replace(tzinfo=WITA)
        umur = (now_wita - created).total_seconds() / 60
        m["umur_menit"] = umur
        if m.get("is_ft") or m.get("final_score"):
            m["status_calc"] = "PASIF"
            fs = str(m.get("final_score","0-0"))
            try:
                hg, ag = map(int, fs.split("-"))
                total = hg+ag
                m["gol_terjadi"] = total > 0
                m["result_calc"] = "WIN" if total>0 else "LOSE"
            except:
                m["gol_terjadi"] = "WIN" in str(m.get("result",""))
                m["result_calc"] = "WIN" if m["gol_terjadi"] else "LOSE"
        elif umur > 40:
            m["status_calc"] = "PASIF"
            fs = str(m.get("final_score","0-0"))
            try:
                hg, ag = map(int, fs.split("-"))
                m["gol_terjadi"] = (hg+ag)>0
                m["result_calc"] = "WIN" if m["gol_terjadi"] else "LOSE"
            except:
                m["result_calc"] = "LOSE"
                m["gol_terjadi"] = False
        else:
            m["status_calc"] = "AKTIF"
            m["result_calc"] = "LIVE"
            m["gol_terjadi"] = None
        m["liga_pretty"] = pretty_league(m.get("league",""))
    except:
        m["status_calc"] = "AKTIF"
        m["result_calc"] = "LIVE"
        m["gol_terjadi"] = None
        m["liga_pretty"] = "-"

# MODAL
MODAL_PER_MATCH = 50000
PROFIT_PER_WIN = int(MODAL_PER_MATCH * 0.8)
LOSS_PER_LOSE = MODAL_PER_MATCH

total = len(matches)
pasif = len([m for m in matches if m.get("status_calc")=="PASIF"])
aktif = len([m for m in matches if m.get("status_calc")=="AKTIF"])
selesai = pasif
win = len([m for m in matches if m.get("result_calc")=="WIN"])
lose = len([m for m in matches if m.get("result_calc")=="LOSE"])
win_rate = (win / selesai * 100) if selesai>0 else 0

total_modal = selesai * MODAL_PER_MATCH
total_profit = win * PROFIT_PER_WIN - lose * LOSS_PER_LOSE
roi = (total_profit / total_modal * 100) if total_modal>0 else 0

# UI
st.markdown(f"""
<div style="background: #0f172a; border-radius:16px; padding:20px; color:white; margin-bottom:16px;">
    <div style="font-size:22px; font-weight:800;">⚽ Trading Bola Menit 60 - Last Goal System</div>
    <div style="font-size:12px; color:#94a3b8; margin-top:6px;">Window 60-66 skor 0-0 | Modal Rp 50rb | {total} match | {win}W-{lose}L {win_rate:.1f}% WR | Profit {format_rp(total_profit)} | ROI {roi:.1f}%</div>
    <div style="font-size:10px; color:#4ade80; margin-top:8px;">✅ V3.6 STABIL - NO ERROR - Data: {total} match ({selesai} FT) | Logic: deteksi 0-0 vs FT 2-1 = +3 gol = WIN</div>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Match", total, f"{aktif} aktif")
c2.metric("Selesai FT", selesai, f"{win}W-{lose}L")
c3.metric("Win Rate", f"{win_rate:.1f}%", f"Profit {format_rp(total_profit)}")
c4.metric("ROI", f"{roi:.1f}%", f"Modal {format_rp(total_modal)}")

# Donut
col1, col2 = st.columns(2)
with col1:
    fig = go.Figure(data=[go.Pie(labels=['AKTIF','PASIF'], values=[aktif, pasif], hole=0.6, marker=dict(colors=['#0f172a','#e2e8f0']))])
    fig.update_layout(showlegend=False, height=220, margin=dict(t=0,b=0,l=0,r=0), annotations=[dict(text=f'<b>{total}</b><br>match', x=0.5, y=0.5, font_size=14, showarrow=False)])
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

with col2:
    # Daily summary cut off 12:00 WITA
    from collections import defaultdict
    daily = defaultdict(lambda: {"win":0, "lose":0, "profit":0, "total":0})
    for m in matches:
        try:
            ca = pd.to_datetime(m.get("created_at",""))
            if pd.isna(ca): continue
            if ca.tzinfo is None: ca = ca.replace(tzinfo=WITA)
            else: ca = ca.astimezone(WITA)
            d = ca.date()
            if ca.hour < 12:
                d = d - timedelta(days=1)
            if m.get("result_calc")=="WIN":
                daily[d]["win"]+=1
                daily[d]["profit"]+=PROFIT_PER_WIN
            elif m.get("result_calc")=="LOSE":
                daily[d]["lose"]+=1
                daily[d]["profit"]-=LOSS_PER_LOSE
            else:
                continue
            daily[d]["total"]+=1
        except:
            pass
    dates = sorted(daily.keys())
    if dates:
        x = [d.strftime("%d %b") for d in dates]
        y = [daily[d]["profit"] for d in dates]
        colors = ["#22c55e" if v>=0 else "#ef4444" for v in y]
        fig2 = go.Figure(data=[go.Bar(x=x, y=y, marker_color=colors, text=[f"{format_rp(daily[d]['profit'])}<br>{daily[d]['win']}W-{daily[d]['lose']}L" for d in dates], textposition='outside')])
        fig2.update_layout(height=220, margin=dict(t=30,b=30,l=40,r=20), yaxis=dict(title="Profit Rp"), xaxis=dict(title="Cut off 12:00 WITA"))
        st.markdown(f"<div style='font-size:11px; font-weight:700;'>📅 Summary Harian Cut off 12:00 WITA • {format_rp(total_profit)}</div>", unsafe_allow_html=True)
        st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
        # Table
        rows = []
        for d in dates[-7:][::-1]:
            ds = daily[d]
            wr = (ds["win"]/ds["total"]*100) if ds["total"]>0 else 0
            rows.append({"Tanggal": d.strftime("%d %b %Y")+" (12:00-11:59)", "Match": ds["total"], "W-L": f"{ds['win']}W-{ds['lose']}L", "WR": f"{wr:.1f}%", "Profit": format_rp(ds["profit"])})
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, height=200)

st.markdown(f"### 20 Peluang Terakhir • {win}W-{lose}L {win_rate:.1f}% WR • Modal Rp 50rb • Profit {format_rp(total_profit)}")

# Table
html = "<div style='background:white; border-radius:12px; border:1px solid #e2e8f0; overflow-x:auto;'><div style='display:grid; grid-template-columns:80px 1fr 80px 50px 60px 70px 50px 80px 80px; gap:0; padding:10px; background:#f8fafc; font-size:10px; font-weight:800; color:#64748b;'><div>WAKTU</div><div>MATCH (0-0 → FT)</div><div>LIGA</div><div>MENIT</div><div>STATUS</div><div>FT SCORE</div><div>GOL?</div><div>RESULT</div><div>PROFIT</div></div>"

for m in sorted(matches, key=lambda x: x.get("created_at",""), reverse=True)[:20]:
    try:
        ca = m.get("created_at","")
        jam = ca.split("T")[1][:5] if "T" in ca else "00:00"
    except:
        jam = "00:00"
    home = m.get("home_team","-")
    away = m.get("away_team","-")
    liga = m.get("liga_pretty","-")
    menit = m.get("minute",60)
    status = m.get("status_calc","AKTIF")
    ft = m.get("final_score") or m.get("live_score") or "-"
    gol = m.get("gol_terjadi")
    result = m.get("result_calc","LIVE")
    if gol==True:
        profit = f"+Rp {PROFIT_PER_WIN//1000}rb"
        color="#16a34a"
        icon="✅"
    elif gol==False:
        profit = f"-Rp {LOSS_PER_LOSE//1000}rb"
        color="#dc2626"
        icon="❌"
    else:
        profit="LIVE"
        color="#64748b"
        icon="⏳"
    # Deteksi selalu 0-0
    html += f"<div style='display:grid; grid-template-columns:80px 1fr 80px 50px 60px 70px 50px 80px 80px; gap:0; padding:10px; border-bottom:1px solid #f1f5f9; font-size:11px; align-items:center;'><div style='font-size:10px;'>{jam} WITA</div><div><div style='font-weight:700;'>{home} vs {away}</div><div style='font-size:9px; color:#64748b;'>0-0 (60') → {ft} • Over 0.5</div></div><div style='font-size:9px; background:#f1f5f9; padding:3px 6px; border-radius:8px; display:inline-block;'>{liga}</div><div><span style='background:#0f172a; color:white; padding:3px 8px; border-radius:10px; font-size:10px;'>{menit}'</span></div><div><span style='background:#e2e8f0; padding:3px 8px; border-radius:10px; font-size:9px;'>{status}</span></div><div style='font-weight:700;'>{ft}</div><div><span style='background:#f1f5f9; width:22px; height:22px; display:flex; align-items:center; justify-content:center; border-radius:50%;'>{icon}</span></div><div style='font-size:10px; font-weight:700;'>{result}</div><div style='font-size:10px; font-weight:700; color:{color};'>{profit}</div></div>"

html += "</div>"
st.markdown(html, unsafe_allow_html=True)

st.markdown(f"""
<div style="margin-top:20px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:12px; padding:12px;">
<div style="font-size:11px; font-weight:700; color:#166534;">✅ Logic Benar: Deteksi 0-0 (60') → FT 2-1 = +3 gol = WIN Over 0.5</div>
<div style="font-size:10px; color:#166534; margin-top:4px;">FT 2-1 itu total dari menit 0-90, tapi karena menit 60 masih 0-0, berarti 3 gol terjadi di 60-90 → WIN</div>
</div>
""", unsafe_allow_html=True)
