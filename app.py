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
    try:
        for p in ["data/matches.json", "matches.json"]:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    if j:
                        return pd.DataFrame(j), f"OK dari {p} ({len(j)} rows)"
    except:
        pass
    try:
        supa_url = st.secrets.get("SUPABASE_URL", "")
        supa_key = st.secrets.get("SUPABASE_KEY", "")
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
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Peluang", len(df), src)
    col2.metric("Sudah Selesai", len(df[df['final_score_home'].notna()]) if 'final_score_home' in df.columns else 0)
    col3.metric("Win Rate", "Menunggu...")
    col4.metric("AKTIF 🔥", len(df[df['status'] == 'AKTIF']) if 'status' in df.columns else 0)
    st.dataframe(df.head(20), use_container_width=True, hide_index=True)
    if "TEST001" in df['match_id'].values:
        st.warning("⚠️ DATA DUMMY TEST001 - Hapus di Supabase setelah test")

st.sidebar.button("🔄 Refresh Data", on_click=lambda: st.cache_data.clear())
