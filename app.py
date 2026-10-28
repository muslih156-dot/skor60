
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, glob, io, requests

WITA = timezone(timedelta(hours=8))

st.set_page_config(page_title="Trading Bola Menit 60", page_icon="⚽", layout="wide")
st.title("⚽ Trading Bola Menit 60 - Last Goal System")
st.caption(f"V8.9 BATCH FIX - 220 LIGA - UNLIMITED - {datetime.now(WITA).strftime('%d %b %Y %H:%M WITA')}")

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/muslih156-dot/skor60/main"

@st.cache_data(ttl=10)
def load_dashboard():
    # Local
    for p in ["data/matches.json", "matches.json", "./data/matches.json"]:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    if isinstance(j, list) and j:
                        real = [x for x in j if "TEST" not in str(x.get("match_id",""))]
                        if real:
                            return pd.DataFrame(real), f"LOCAL {p} ({len(real)})"
        except Exception as e:
            st.write(f"Local error {e}")
    
    # GitHub RAW - bypass cache dengan timestamp
    try:
        url = f"{GITHUB_RAW_BASE}/data/matches.json?t={int(datetime.now().timestamp())}"
        r = requests.get(url, timeout=15)
        st.write(f"GitHub RAW matches.json status: {r.status_code}")
        if r.status_code == 200:
            j = r.json()
            if isinstance(j, list) and j:
                real = [x for x in j if "TEST" not in str(x.get("match_id",""))]
                if real:
                    return pd.DataFrame(real), f"GITHUB RAW ({len(real)})"
            else:
                return pd.DataFrame(), f"GITHUB RAW empty array [] - bot belum nemu peluang"
        else:
            return pd.DataFrame(), f"GITHUB RAW {r.status_code} - file belum ada di GitHub (repo private? atau belum push?)"
    except Exception as e:
        return pd.DataFrame(), f"GITHUB RAW error: {e}"
    
    return pd.DataFrame(), "NO DATA"

@st.cache_data(ttl=20)
def load_all_archive():
    all_data = []
    # Local
    try:
        archives = glob.glob("data/archive/2026-*.json")
        archives = [a for a in archives if "all_time" not in a]
        for arch in sorted(archives):
            with open(arch, "r", encoding="utf-8") as f:
                j = json.load(f)
                if isinstance(j, list):
                    all_data.extend(j)
        if os.path.exists("data/archive/all_time.json"):
            with open("data/archive/all_time.json", "r", encoding="utf-8") as f:
                j = json.load(f)
                if isinstance(j, list) and not all_data:
                    all_data = j
    except:
        pass
    
    # GitHub RAW fallback
    if not all_data:
        try:
            url = f"{GITHUB_RAW_BASE}/data/archive/all_time.json?t={int(datetime.now().timestamp())}"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, list):
                    all_data = j
        except:
            pass
    
    if not all_data:
        return pd.DataFrame(), "NO ARCHIVE"
    
    df = pd.DataFrame(all_data)
    df = df[~df['match_id'].astype(str).str.contains('TEST', na=False)]
    if 'created_at' in df.columns:
        try:
            df['created_at'] = pd.to_datetime(df['created_at'])
        except:
            pass
    return df, f"{len(all_data)} total"

df_dash, source_dash = load_dashboard()
df_all, source_all = load_all_archive()

st.sidebar.title("⚙️ Filter & Tools")
st.sidebar.code(f"Dashboard: {source_dash}\nArchive: {source_all}")
st.sidebar.info(f"WITA: {datetime.now(WITA).strftime('%H:%M:%S')}\nDash: {len(df_dash)}\nAll: {len(df_all)}")

if st.sidebar.button("🔄 Clear Cache & Reload"):
    st.cache_data.clear()
    st.rerun()

tab1, tab2 = st.tabs(["🔥 Live Dashboard", "📅 All Time"])

with tab1:
    st.subheader(f"🔥 Live Dashboard - Source: {source_dash}")
    if df_dash.empty:
        st.warning("Dashboard kosong")
        st.info(f"Debug: {source_dash} | {source_all}")
        st.markdown("""
        **Cek manual:**
        1. Buka https://github.com/muslih156-dot/skor60/tree/main/data - ada matches.json?
        2. Buka https://raw.githubusercontent.com/muslih156-dot/skor60/main/data/matches.json - ada isi?
        3. Kalau 404, repo private! Ganti ke Public di Settings
        4. Kalau [], bot belum nemu 0-0 menit 55-68
        """)
        if not df_all.empty:
            st.success(f"Tapi archive ada {len(df_all)} match!")
            st.dataframe(df_all.head(20), use_container_width=True)
    else:
        st.success(f"✅ Ada {len(df_dash)} peluang!")
        if 'status' in df_dash.columns:
            df_dash['rekomendasi'] = df_dash['status'].apply(lambda x: '✅ REKOMENDASI' if '⚠️' not in str(x) else '⚠️ HATI-HATI')
        st.dataframe(df_dash.head(50), use_container_width=True, height=500)
        # Export
        csv = df_dash.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, f"matches_{datetime.now(WITA).strftime('%Y%m%d')}.csv", "text/csv")

with tab2:
    st.subheader(f"📅 All Time - {source_all}")
    if df_all.empty:
        st.info("Archive kosong")
    else:
        st.dataframe(df_all.head(200), use_container_width=True)
        st.bar_chart(df_all['league'].value_counts().head(15) if 'league' in df_all.columns else pd.DataFrame())

st.caption("V8.9 BATCH FIX - Save 2 match sekaligus ga ketimpa + Force add -f bypass .gitignore")
