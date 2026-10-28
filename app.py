
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os

WITA = timezone(timedelta(hours=8))

st.set_page_config(page_title="Skor60 - Level 5 Dashboard", page_icon="⚽", layout="wide")

st.title("⚽ Skor60 - Level 5 AI Dashboard")
st.caption(f"Bot detektor menit 60 skor 0-0 | Live dari GitHub + Supabase | Update tiap 5 menit | {datetime.now(WITA).strftime('%d %b %Y %H:%M WITA')}")

@st.cache_data(ttl=60)
def load_data():
    try:
        if os.path.exists("data/matches.json"):
            with open("data/matches.json", "r") as f:
                data = json.load(f)
                return pd.DataFrame(data)
        if os.path.exists("matches.json"):
            with open("matches.json", "r") as f:
                return pd.DataFrame(json.load(f))
    except Exception as e:
        st.warning(f"Load local error: {e}")
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.info("📭 Belum ada data - bot baru jalan. Data akan muncul otomatis pas ada bola menit 60 0-0 (jam 19:00-02:00 WITA)")
    st.success(f"✅ Bot GitHub Actions jalan tiap 5 menit | Supabase table matches sudah ada | Menunggu match pertama... | Jam server: {datetime.now(WITA).strftime('%H:%M WITA')}")
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Terdeteksi", len(df))
    finished = df[df['final_score_home'].notna()] if 'final_score_home' in df.columns else pd.DataFrame()
    col2.metric("Sudah Selesai", len(finished))
    if not finished.empty and 'goal_after_60' in finished.columns:
        gol = finished[finished['goal_after_60'] == True]
        pct = len(gol) / len(finished) * 100 if len(finished) > 0 else 0
        col3.metric("Jadi Gol Setelah 60'", f"{pct:.1f}%", f"{len(gol)} dari {len(finished)}")
    else:
        col3.metric("Jadi Gol Setelah 60'", "Menunggu hasil...")
    aktif = df[df['status'] == 'AKTIF'] if 'status' in df.columns else pd.DataFrame()
    col4.metric("AKTIF 🔥", len(aktif))
    
    st.subheader("📋 20 Match Terakhir Menit 60 0-0")
    cols_show = [c for c in ['created_at','home_team','away_team','league','minute','status','shots_total','dangerous_attacks','final_status','goal_after_60'] if c in df.columns]
    show_df = df.head(20)[cols_show].copy()
    if 'created_at' in show_df.columns:
        show_df['created_at'] = pd.to_datetime(show_df['created_at']).dt.tz_localize(None).dt.tz_localize('UTC').dt.tz_convert('Asia/Makassar').dt.strftime('%d/%m %H:%M')
    st.dataframe(show_df, use_container_width=True, hide_index=True)

st.sidebar.title("Skor60 Level 5")
st.sidebar.success("Phase 1 ✅ Memory\nPhase 2 ✅ Tracking\nPhase 3 ✅ Dashboard\nPhase 4 ⏳ ML Model (butuh 50 data)")
st.sidebar.info(f"Jam WITA: {datetime.now(WITA).strftime('%H:%M:%S')}\nBot jalan 24 jam gratis\nGitHub Actions → Supabase → JSON → Dashboard")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
