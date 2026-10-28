
import streamlit as st
import pandas as pd
from datetime import datetime
import requests

st.set_page_config(page_title="Skor60 - Level 5 Dashboard", page_icon="⚽", layout="wide")

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
except:
    st.error("Secrets belum di-set")
    st.stop()

st.title("⚽ Skor60 - Level 5 AI Dashboard")
st.caption(f"Live dari Supabase | Update tiap 5 menit | {datetime.now().strftime('%d %b %Y %H:%M WITA')}")

@st.cache_data(ttl=60)
def load_data_rest():
    try:
        url = f"{SUPABASE_URL}/rest/v1/matches?select=*&order=created_at.desc&limit=200"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return pd.DataFrame(data)
        else:
            st.warning(f"Supabase API {r.status_code}: {r.text[:200]}")
            return pd.DataFrame()
    except Exception as e:
        st.warning(f"Load error: {e}")
        return pd.DataFrame()

df = load_data_rest()

if df.empty:
    st.info("📭 Belum ada data - bot baru jalan. Data akan muncul otomatis pas ada bola menit 60 0-0 (jam 19:00-02:00 WITA)")
    st.success(f"✅ Supabase connected: {SUPABASE_URL}")
    st.caption("Tabel matches sudah ada, menunggu match pertama. Bot GitHub Actions jalan tiap 5 menit.")
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Terdeteksi", len(df))
    finished = df[df['final_score_home'].notna()] if 'final_score_home' in df.columns else pd.DataFrame()
    col2.metric("Sudah Selesai", len(finished))
    if not finished.empty and 'goal_after_60' in finished.columns:
        gol = finished[finished['goal_after_60'] == True]
        pct = len(gol) / len(finished) * 100 if len(finished) > 0 else 0
        col3.metric("Jadi Gol Setelah 60'", f"{pct:.1f}%")
    else:
        col3.metric("Jadi Gol Setelah 60'", "Menunggu...")
    aktif = df[df['status'] == 'AKTIF'] if 'status' in df.columns else pd.DataFrame()
    col4.metric("AKTIF 🔥", len(aktif))
    
    st.subheader("📋 20 Match Terakhir")
    cols_show = [c for c in ['created_at','home_team','away_team','league','minute','status','shots_total','dangerous_attacks','final_status','goal_after_60'] if c in df.columns]
    show_df = df.head(20)[cols_show].copy()
    if 'created_at' in show_df.columns:
        show_df['created_at'] = pd.to_datetime(show_df['created_at']).dt.strftime('%d/%m %H:%M')
    st.dataframe(show_df, use_container_width=True, hide_index=True)

st.sidebar.title("Skor60 Level 5")
st.sidebar.success("Phase 1 ✅ Memory\nPhase 2 ✅ Tracking\nPhase 3 🚀 Dashboard\nPhase 4 ⏳ ML Model")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
