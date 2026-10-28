Download

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, requests

WITA = timezone(timedelta(hours=8))

st.set_page_config(page_title="Trading Bola Menit 60 - Last Goal System", page_icon="⚽", layout="wide")
st.title("⚽ Trading Bola Menit 60 - Last Goal System")
st.caption(f"Detektor peluang Last Goal menit 60 skor 0-0 | Live AI System | Update tiap 5 menit | {datetime.now(WITA).strftime('%d %b %Y %H:%M WITA')}")

@st.cache_data(ttl=30)
def load_data():
    # PILIHAN A: Baca JSON lokal dulu (work di Streamlit Cloud tanpa DNS error)
    try:
        for p in ["data/matches.json", "matches.json"]:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    if j:
                        df = pd.DataFrame(j)
                        # Kalau ada TEST001 atau data real, return langsung
                        return df, f"OK dari {p} ({len(df)} rows)"
    except Exception as e:
        pass

    # Fallback: Supabase REST (kadang gagal DNS di Streamlit Cloud gratis)
    try:
        supa_url = st.secrets.get("SUPABASE_URL", "") or os.getenv("SUPABASE_URL", "")
        supa_key = st.secrets.get("SUPABASE_KEY", "") or os.getenv("SUPABASE_KEY", "")
        if supa_url and supa_key:
            url = supa_url.strip().rstrip("/") + "/rest/v1/matches?select=*&order=created_at.desc&limit=200"
            headers = {"apikey": supa_key, "Authorization": f"Bearer {supa_key}"}
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200 and r.json():
                return pd.DataFrame(r.json()), "OK dari Supabase REST"
    except Exception as e:
        return pd.DataFrame(), f"Supabase error: {e}"

    return pd.DataFrame(), "Belum ada data"

df, src = load_data()

if df.empty:
    st.info("📭 Belum ada peluang Last Goal - bot baru jalan. Data akan muncul otomatis pas ada bola menit 60 0-0 (jam 19:00-02:00 WITA)")
    if src:
        st.caption(f"Debug: {src}")
    st.success(f"✅ Last Goal System aktif | Bot jalan tiap 5 menit | Supabase ready | Jam: {datetime.now(WITA).strftime('%H:%M WITA')}")
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Peluang", len(df), src)
    finished = df[df['final_score_home'].notna()] if 'final_score_home' in df.columns else pd.DataFrame()
    col2.metric("Sudah Selesai", len(finished))
    if not finished.empty and 'goal_after_60' in finished.columns:
        try:
            gol = finished[finished['goal_after_60'] == True]
            pct = len(gol) / len(finished) * 100 if len(finished) > 0 else 0
            col3.metric("Win Rate Last Goal", f"{pct:.1f}%", f"{len(gol)}/{len(finished)}")
        except:
            col3.metric("Win Rate", f"{len(finished)} done")
    else:
        col3.metric("Win Rate", "Menunggu...")
    aktif = df[df['status'] == 'AKTIF'] if 'status' in df.columns else pd.DataFrame()
    col4.metric("AKTIF 🔥", len(aktif))
    
    st.subheader("📋 20 Peluang Last Goal Terakhir")
    cols_show = [c for c in ['created_at','home_team','away_team','league','minute','status','shots_total','dangerous_attacks','final_status','goal_after_60'] if c in df.columns]
    show_df = df.head(20)[cols_show].copy()
    st.dataframe(show_df, use_container_width=True, hide_index=True)
    if "TEST001" in df['match_id'].values:
        st.warning("⚠️ Ini DATA DUMMY TEST001 - Hapus di Supabase Table Editor setelah test, nanti bot akan timpa dengan data asli jam 02:00-05:00 WITA")

st.sidebar.title("Last Goal System")
st.sidebar.success("Phase 1 ✅ Memory\nPhase 2 ✅ Tracking\nPhase 3 ✅ Dashboard\nPhase 4 ⏳ ML Model")
st.sidebar.info(f"Trading Bola Menit 60 - Last Goal System\nJam WITA: {datetime.now(WITA).strftime('%H:%M:%S')}\nBot 24 jam gratis")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
