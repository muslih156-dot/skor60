
import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Skor60 - Level 5 Dashboard", page_icon="⚽", layout="wide")

# Secrets dari Streamlit Cloud atau .streamlit/secrets.toml
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except:
    # Fallback untuk test lokal - ganti dengan URL kamu
    SUPABASE_URL = "https://osujspgrzyrjpzkwwupo.supabase.co"
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "") if "SUPABASE_KEY" in st.secrets else ""

@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

st.title("⚽ Skor60 - Level 5 AI Dashboard")
st.caption(f"Bot detektor menit 60 skor 0-0 | Live dari Supabase | Update tiap 5 menit | {datetime.now().strftime('%d %b %Y %H:%M WITA')}")

# Fetch data
@st.cache_data(ttl=60)
def load_data():
    try:
        res = supabase.table("matches").select("*").order("created_at", desc=True).limit(200).execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Error load data: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("Belum ada data - bot baru jalan. Data akan muncul otomatis pas ada bola menit 60 0-0 (biasanya jam 19:00-02:00 WITA)")
    st.info("Supabase connected ✅ - Menunggu match pertama...")
else:
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    total = len(df)
    with col1:
        st.metric("Total Terdeteksi", total)
    with col2:
        finished = df[df['final_score_home'].notna()]
        st.metric("Sudah Selesai", len(finished))
    with col3:
        if not finished.empty:
            gol = finished[finished['goal_after_60'] == True]
            pct = len(gol) / len(finished) * 100 if len(finished) > 0 else 0
            st.metric("Jadi Gol Setelah 60'", f"{pct:.1f}%", f"{len(gol)} dari {len(finished)}")
        else:
            st.metric("Jadi Gol Setelah 60'", "Menunggu...")
    with col4:
        aktif = df[df['status'] == 'AKTIF']
        st.metric("AKTIF 🔥", len(aktif))

    st.divider()

    # Charts
    c1, c2 = st.columns(2)
    with c1:
        if 'status' in df.columns:
            fig = px.pie(df, names='status', title='Distribusi Status (AKTIF/PASIF/JEBAKAN)', color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        if not finished.empty and 'goal_after_60' in finished.columns:
            fig2 = px.bar(finished.groupby('status')['goal_after_60'].mean().reset_index(), x='status', y='goal_after_60', title='Probabilitas Gol Setelah 60 by Status', labels={'goal_after_60': 'Prob Gol'})
            st.plotly_chart(fig2, use_container_width=True)

    # Table live
    st.subheader("📋 20 Match Terakhir Menit 60 0-0")
    show_df = df.head(20)[['created_at','home_team','away_team','league','minute','status','shots_total','dangerous_attacks','final_status','goal_after_60']].copy()
    show_df['created_at'] = pd.to_datetime(show_df['created_at']).dt.strftime('%d/%m %H:%M')
    st.dataframe(show_df, use_container_width=True, hide_index=True)

    st.divider()
    st.caption("Level 5 - Bot punya memory + bisa belajar | Data dari Supabase osujspgrzyrjpzkwwupo | GitHub Actions tiap 5 menit")

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
st.sidebar.success("Bot jalan 24 jam gratis - GitHub public + Supabase free")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
