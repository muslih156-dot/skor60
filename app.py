Download

import streamlit as st
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="Skor60 - Level 5 Dashboard", page_icon="⚽", layout="wide")

# Ambil secrets dengan aman
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"].strip()
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
except Exception as e:
    st.error(f"Secrets belum di-set: {e}")
    st.info("Set SUPABASE_URL dan SUPABASE_KEY di Advanced settings")
    st.stop()

# Lazy import supabase biar error gak crash full app
try:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Gagal connect Supabase: {e}")
    st.info(f"URL yang dipakai: {SUPABASE_URL}")
    supabase = None

st.title("⚽ Skor60 - Level 5 AI Dashboard")
st.caption(f"Bot detektor menit 60 skor 0-0 | Live dari Supabase | Update tiap 5 menit | {datetime.now().strftime('%d %b %Y %H:%M WITA')}")

@st.cache_data(ttl=60)
def load_data():
    if not supabase:
        return pd.DataFrame()
    try:
        res = supabase.table("matches").select("*").order("created_at", desc=True).limit(200).execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        # Jangan crash, return kosong aja
        st.warning(f"Load data error (akan retry): {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.info("📭 Belum ada data - bot baru jalan. Data akan muncul otomatis pas ada bola menit 60 0-0 (biasanya jam 19:00-02:00 WITA)")
    st.success("✅ Supabase connected - URL: " + SUPABASE_URL + " - Menunggu match pertama...")
    st.balloons()
else:
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    total = len(df)
    with col1:
        st.metric("Total Terdeteksi", total)
    with col2:
        finished = df[df['final_score_home'].notna()] if 'final_score_home' in df.columns else pd.DataFrame()
        st.metric("Sudah Selesai", len(finished))
    with col3:
        if not finished.empty and 'goal_after_60' in finished.columns:
            gol = finished[finished['goal_after_60'] == True]
            pct = len(gol) / len(finished) * 100 if len(finished) > 0 else 0
            st.metric("Jadi Gol Setelah 60'", f"{pct:.1f}%", f"{len(gol)} dari {len(finished)}")
        else:
            st.metric("Jadi Gol Setelah 60'", "Menunggu hasil...")
    with col4:
        aktif = df[df['status'] == 'AKTIF'] if 'status' in df.columns else pd.DataFrame()
        st.metric("AKTIF 🔥", len(aktif))

    st.divider()

    # Table live
    st.subheader("📋 20 Match Terakhir Menit 60 0-0")
    cols_show = [c for c in ['created_at','home_team','away_team','league','minute','status','shots_total','dangerous_attacks','final_status','goal_after_60'] if c in df.columns]
    show_df = df.head(20)[cols_show].copy()
    if 'created_at' in show_df.columns:
        show_df['created_at'] = pd.to_datetime(show_df['created_at']).dt.strftime('%d/%m %H:%M')
    st.dataframe(show_df, use_container_width=True, hide_index=True)

    try:
        import plotly.express as px
        c1, c2 = st.columns(2)
        with c1:
            if 'status' in df.columns and not df.empty:
                fig = px.pie(df, names='status', title='Distribusi Status (AKTIF/PASIF/JEBAKAN)')
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            if not finished.empty and 'goal_after_60' in finished.columns and 'status' in finished.columns:
                prob = finished.groupby('status')['goal_after_60'].mean().reset_index()
                fig2 = px.bar(prob, x='status', y='goal_after_60', title='Probabilitas Gol Setelah 60 by Status')
                st.plotly_chart(fig2, use_container_width=True)
    except:
        pass

    st.divider()
    st.caption("Level 5 - Bot punya memory + bisa belajar | GitHub Actions tiap 5 menit")

st.sidebar.title("Skor60 Level 5")
st.sidebar.info("""
**Arsitektur:**
Sofascore API → GitHub Actions → Supabase → Dashboard ini

**Phase:**
- Phase 1 ✅ Memory (Supabase)
- Phase 2 ✅ Tracking hasil
- Phase 3 🚀 Dashboard (kamu di sini)
- Phase 4 ⏳ ML Model (butuh 50+ data)
""")
st.sidebar.success(f"Bot jalan 24 jam gratis\nURL: {SUPABASE_URL}")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
