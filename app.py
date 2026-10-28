Download

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, glob, io, requests

WITA = timezone(timedelta(hours=8))

st.set_page_config(page_title="Trading Bola Menit 60", page_icon="⚽", layout="wide")
st.title("⚽ Trading Bola Menit 60 - Last Goal System")
st.caption(f"V9.1 NAMA LIGA BENER - 220 LIGA - {datetime.now(WITA).strftime('%d %b %Y %H:%M WITA')}")

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/muslih156-dot/skor60/main"

LEAGUE_EMOJI = {
    "ita.1": "🇮🇹 Serie A", "ita.2": "🇮🇹 Serie B",
    "eng.1": "🏴󐁧󐁢󐁥󐁮󐁧󐁿 Premier League", "eng.2": "🏴󐁧󐁢󐁥󐁮󐁧󐁿 Championship",
    "ger.1": "🇩🇪 Bundesliga", "ger.2": "🇩🇪 2. Bundesliga",
    "esp.1": "🇪🇸 LaLiga", "fra.1": "🇫🇷 Ligue 1",
    "ned.1": "🇳🇱 Eredivisie", "por.1": "🇵🇹 Primeira Liga",
    "uefa.champions": "🏆 Champions League", "uefa.europa": "🏆 Europa League",
}

@st.cache_data(ttl=10)
def load_dashboard():
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
            pass
    
    try:
        url = f"{GITHUB_RAW_BASE}/data/matches.json?t={int(datetime.now().timestamp())}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            j = r.json()
            if isinstance(j, list) and j:
                real = [x for x in j if "TEST" not in str(x.get("match_id",""))]
                if real:
                    return pd.DataFrame(real), f"GITHUB RAW ({len(real)})"
            else:
                return pd.DataFrame(), f"GITHUB RAW empty []"
        else:
            return pd.DataFrame(), f"GITHUB RAW {r.status_code}"
    except Exception as e:
        return pd.DataFrame(), f"GITHUB RAW error: {e}"
    return pd.DataFrame(), "NO DATA"

@st.cache_data(ttl=20)
def load_all_archive():
    all_data = []
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

# Pretty league display
def pretty_league_name(league_str):
    if not league_str:
        return "-"
    # If already has emoji
    if league_str[0] not in "abcdefghijklmnopqrstuvwxyz":
        return league_str
    # Check map
    if league_str in LEAGUE_EMOJI:
        return LEAGUE_EMOJI[league_str]
    # Fallback: ita.1 -> Serie A
    s = league_str.lower()
    if "ita.1" in s: return "🇮🇹 Serie A"
    if "eng.1" in s: return "🏴󐁧󐁢󐁥󐁮󐁧󐁿 Premier League"
    if "ger.1" in s: return "🇩🇪 Bundesliga"
    if "esp.1" in s: return "🇪🇸 LaLiga"
    if "fra.1" in s: return "🇫🇷 Ligue 1"
    if "ita" in s: return f"🇮🇹 {league_str.replace('ita.','Serie ').replace('.',' ').title()}"
    if "eng" in s: return f"🏴󐁧󐁢󐁥󐁮󐁧󐁿 {league_str.replace('eng.','').title()}"
    if "uefa" in s: return f"🏆 {league_str.replace('uefa.','').replace('.',' ').title()}"
    return league_str.replace(".", " ").title()

if not df_dash.empty and 'league' in df_dash.columns:
    df_dash['league_pretty'] = df_dash['league'].apply(pretty_league_name)

tab1, tab2, tab3 = st.tabs(["🔥 Live Dashboard", "📅 All Time", "💰 Profit"])

with tab1:
    st.subheader(f"🔥 Live Dashboard - {source_dash} - V9.1 Nama Liga Bener")
    if df_dash.empty:
        st.warning("Dashboard kosong - bot lagi scan 220 liga...")
        st.info(f"Debug: {source_dash} | {source_all}")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("🔥 AKTIF", len(df_dash))
        col2.metric("✅ REKOMENDASI", len(df_dash[df_dash['status'].str.contains('REKOMENDASI|AKTIF', na=False)]))
        col3.metric("📅 Hari Ini", datetime.now(WITA).strftime("%d %b"))
        
        st.success(f"✅ Ada {len(df_dash)} peluang trading!")
        
        # Display dengan liga cantik
        display_df = df_dash.copy()
        if 'league_pretty' in display_df.columns:
            display_df['liga'] = display_df['league_pretty']
            cols = ['home_team', 'away_team', 'liga', 'minute', 'score', 'status', 'rekomendasi' if 'rekomendasi' in display_df.columns else 'status']
            # Show pretty
            st.dataframe(display_df[['home_team','away_team','liga','minute','score','status']].head(50), use_container_width=True, height=400)
        else:
            st.dataframe(df_dash.head(50), use_container_width=True, height=400)
        
        csv = df_dash.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, f"skor60_{datetime.now(WITA).strftime('%Y%m%d_%H%M')}.csv", "text/csv")

with tab2:
    st.subheader(f"📅 Archive - {source_all}")
    if df_all.empty:
        st.info("Archive kosong")
    else:
        if 'league' in df_all.columns:
            df_all['league_pretty'] = df_all['league'].apply(pretty_league_name)
        st.dataframe(df_all.head(200), use_container_width=True)
        if 'league_pretty' in df_all.columns:
            st.bar_chart(df_all['league_pretty'].value_counts().head(10))

with tab3:
    st.subheader("💰 Profit Calculator")
    if df_all.empty:
        st.info("Butuh data archive untuk hitung profit")
    else:
        stake = st.number_input("Stake per match (ribu)", 10, 1000, 100)
        odds = st.number_input("Odds rata-rata Over 0.5", 1.1, 3.0, 1.8)
        win_rate = st.slider("Win rate %", 50, 95, 80)
        total = len(df_all)
        profit = (total * win_rate/100 * (odds-1) * stake) - (total * (100-win_rate)/100 * stake)
        st.metric("Total Match Archive", total)
        st.metric("Estimasi Profit", f"Rp {profit:,.0f} ribu")
        st.caption(f"{total} match x {win_rate}% win x odds {odds} - stake {stake}rb")

st.caption("V9.1 - Nama liga bener 🇮🇹 Serie A bukan ita.1 - Window 50-80 menit")
