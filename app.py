
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, glob, requests

WITA = timezone(timedelta(hours=8))

st.set_page_config(page_title="Trading Bola Menit 60", page_icon="⚽", layout="wide")

# Header
col_logo, col_title = st.columns([1,5])
with col_logo:
    st.markdown("## ⚽")
with col_title:
    st.title("Trading Bola Menit 60 - Last Goal System")
    st.caption(f"V9.2 KOLOM LENGKAP - 220 LIGA - Window 50-80 - {datetime.now(WITA).strftime('%d %b %Y %H:%M WITA')}")

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/muslih156-dot/skor60/main"

LEAGUE_MAP = {
    "ita.1": "🇮🇹 Serie A", "ita.2": "🇮🇹 Serie B", "ita.coppa_italia": "🇮🇹 Coppa Italia",
    "eng.1": "🏴󐁧󐁢󐁥󐁮󐁧󐁿 Premier League", "eng.2": "🏴󐁧󐁢󐁥󐁮󐁧󐁿 Championship", "eng.3": "🏴󐁧󐁢󐁥󐁮󐁧󐁿 League One",
    "eng.fa": "🏴󐁧󐁢󐁥󐁮󐁧󐁿 FA Cup", "eng.league_cup": "🏴󐁧󐁢󐁥󐁮󐁧󐁿 Carabao Cup",
    "ger.1": "🇩🇪 Bundesliga", "ger.2": "🇩🇪 2. Bundesliga", "ger.dfb_pokal": "🇩🇪 DFB Pokal",
    "esp.1": "🇪🇸 LaLiga", "esp.2": "🇪🇸 LaLiga 2", "esp.copa_del_rey": "🇪🇸 Copa del Rey",
    "fra.1": "🇫🇷 Ligue 1", "ned.1": "🇳🇱 Eredivisie", "por.1": "🇵🇹 Primeira Liga",
    "bel.1": "🇧🇪 Jupiler Pro League", "tur.1": "🇹🇷 Süper Lig", "sco.1": "🏴󐁧󐁢󐁳󐁣󐁴󐁿 Premiership",
    "uefa.champions": "🏆 Champions League", "uefa.europa": "🏆 Europa League",
    "usa.1": "🇺🇸 MLS", "bra.1": "🇧🇷 Brasileirão", "arg.1": "🇦🇷 Liga Profesional",
    "jpn.1": "🇯🇵 J1 League", "kor.1": "🇰🇷 K League 1", "aus.1": "🇦🇺 A-League",
    "idn.1": "🇮🇩 Liga 1", "tha.1": "🇹🇭 Thai League 1", "mys.1": "🇲🇾 Liga Super",
    "sau.1": "🇸🇦 Pro League", "egy.1": "🇪🇬 Premier League",
}

def pretty_league(s):
    if not s: return "-"
    if s in LEAGUE_MAP: return LEAGUE_MAP[s]
    if "ita" in s.lower(): 
        if "1" in s: return "🇮🇹 Serie A"
        return f"🇮🇹 {s.replace('ita.','').title()}"
    if "eng" in s.lower(): return f"🏴󐁧󐁢󐁥󐁮󐁧󐁿 {s.replace('eng.','').title()}"
    if "ger" in s.lower(): return f"🇩🇪 {s.replace('ger.','').title()}"
    if "esp" in s.lower(): return f"🇪🇸 {s.replace('esp.','').title()}"
    if "uefa" in s.lower(): return f"🏆 {s.replace('uefa.','').replace('.',' ').title()}"
    return s.replace("."," ").replace("_"," ").title()

def rekomendasi_status(row):
    status = str(row.get('status',''))
    warning = str(row.get('status',''))  # warning ada di status
    if '⚠️' in status:
        return '⚠️ HATI-HATI'
    if 'REKOMENDASI' in status or 'AKTIF' in status:
        return '✅ REKOMENDASI - Gas Trading!'
    return '✅ REKOMENDASI'

@st.cache_data(ttl=10)
def load_dashboard():
    for p in ["data/matches.json", "matches.json"]:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    if isinstance(j, list) and j:
                        real = [x for x in j if "TEST" not in str(x.get("match_id",""))]
                        if real:
                            return pd.DataFrame(real), f"LOCAL {p} ({len(real)})"
        except:
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
    except Exception as e:
        return pd.DataFrame(), f"Error {e}"
    return pd.DataFrame(), "NO DATA"

@st.cache_data(ttl=20)
def load_all_archive():
    all_data = []
    try:
        for arch in glob.glob("data/archive/2026-*.json"):
            if "all_time" not in arch:
                with open(arch, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    if isinstance(j, list): all_data.extend(j)
        if os.path.exists("data/archive/all_time.json") and not all_data:
            with open("data/archive/all_time.json", "r", encoding="utf-8") as f:
                j = json.load(f)
                if isinstance(j, list): all_data = j
    except:
        pass
    if not all_data:
        try:
            url = f"{GITHUB_RAW_BASE}/data/archive/all_time.json?t={int(datetime.now().timestamp())}"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, list): all_data = j
        except:
            pass
    if not all_data:
        return pd.DataFrame(), "NO ARCHIVE"
    df = pd.DataFrame(all_data)
    df = df[~df['match_id'].astype(str).str.contains('TEST', na=False)]
    return df, f"{len(all_data)} total"

df_dash, source_dash = load_dashboard()
df_all, source_all = load_all_archive()

# Sidebar
st.sidebar.title("⚙️ Filter & Tools")
st.sidebar.code(f"Dashboard: {source_dash}\nArchive: {source_all}")
st.sidebar.metric("WITA", datetime.now(WITA).strftime("%H:%M:%S"))
st.sidebar.metric("Dash / All", f"{len(df_dash)} / {len(df_all)}")

if st.sidebar.button("🔄 Clear Cache & Reload"):
    st.cache_data.clear()
    st.rerun()

# Enrich dashboard
if not df_dash.empty:
    df_dash['liga_bener'] = df_dash['league'].apply(pretty_league)
    df_dash['rekomendasi'] = df_dash.apply(rekomendasi_status, axis=1)
    df_dash['trading_signal'] = df_dash['minute'].apply(lambda m: f"🔥 OVER 0.5 Menit {m}'" if m else "🔥 OVER 0.5")
    df_dash['match'] = df_dash['home_team'] + " vs " + df_dash['away_team']
    # Format waktu
    if 'created_at' in df_dash.columns:
        try:
            df_dash['waktu_wita'] = pd.to_datetime(df_dash['created_at']).dt.strftime('%H:%M WITA')
        except:
            df_dash['waktu_wita'] = df_dash.get('wita_date','')

tab1, tab2, tab3 = st.tabs(["🔥 Live Dashboard - Kolom Lengkap", "📅 Monthly & All Time", "💰 Profit Calculator"])

with tab1:
    st.subheader(f"🔥 Live Trading - {source_dash} - V9.2 Kolom Lengkap")
    
    if df_dash.empty:
        st.warning("Belum ada peluang 0-0 menit 50-80 - bot scan 220 liga tiap 5 menit")
        st.info(f"Source: {source_dash} | {source_all}")
    else:
        # Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🔥 AKTIF", len(df_dash))
        c2.metric("✅ REKOMENDASI", len(df_dash[~df_dash['status'].str.contains('⚠️', na=False)]))
        c3.metric("⚠️ HATI-HATI", len(df_dash[df_dash['status'].str.contains('⚠️', na=False)]))
        c4.metric("📅 Hari Ini", datetime.now(WITA).strftime("%d %b"))
        
        st.success(f"✅ Ada {len(df_dash)} peluang trading menit 50-80!")
        
        # Table lengkap seperti Supabase dulu
        display_cols = ['match', 'liga_bener', 'minute', 'score', 'rekomendasi', 'trading_signal', 'status', 'waktu_wita', 'wita_date']
        available = [c for c in display_cols if c in df_dash.columns]
        
        # Style
        st.dataframe(
            df_dash[available].rename(columns={
                'match': '⚽ Match',
                'liga_bener': '🏆 Liga',
                'minute': '⏱️ Menit',
                'score': '📊 Skor',
                'rekomendasi': '💡 Rekomendasi',
                'trading_signal': '🎯 Signal',
                'status': '📋 Status Lengkap',
                'waktu_wita': '🕐 Waktu',
                'wita_date': '📅 Tanggal'
            }).head(100),
            use_container_width=True,
            height=500
        )
        
        # Detail per match
        st.divider()
        st.subheader("📋 Detail Peluang")
        for idx, row in df_dash.head(5).iterrows():
            with st.expander(f"🔥 {row['home_team']} vs {row['away_team']} - {row['liga_bener']} - Menit {row['minute']}' - {row['rekomendasi']}"):
                cc1, cc2, cc3 = st.columns(3)
                cc1.write(f"**Match ID:** {row['match_id']}")
                cc1.write(f"**Liga:** {row['liga_bener']}")
                cc1.write(f"**Menit:** {row['minute']}'")
                cc2.write(f"**Skor:** {row['score']}")
                cc2.write(f"**Status:** {row['status']}")
                cc2.write(f"**Rekomendasi:** {row['rekomendasi']}")
                cc3.write(f"**Waktu:** {row.get('waktu_wita','-')}")
                cc3.write(f"**Signal:** {row['trading_signal']}")
                st.info(f"💡 Trading: {row['home_team']} vs {row['away_team']} masih 0-0 di menit {row['minute']}. Peluang besar ada gol! Rekomendasi: {row['rekomendasi']}")

with tab2:
    st.subheader(f"📅 Archive - {source_all}")
    if df_all.empty:
        st.info("Archive kosong")
    else:
        df_all['liga_bener'] = df_all['league'].apply(pretty_league)
        c1, c2 = st.columns(2)
        c1.metric("Total Archive", len(df_all))
        c2.metric("Bulan Ini", len(df_all[df_all['month']==datetime.now(WITA).strftime('%Y-%m')]) if 'month' in df_all.columns else len(df_all))
        
        st.dataframe(
            df_all[['home_team','away_team','liga_bener','minute','score','status','wita_date']].head(200).rename(columns={
                'home_team': 'Home', 'away_team': 'Away', 'liga_bener': 'Liga', 'minute': 'Menit'
            }),
            use_container_width=True, height=400
        )
        st.bar_chart(df_all['liga_bener'].value_counts().head(15))

with tab3:
    st.subheader("💰 Profit Calculator - VIP System")
    if df_all.empty:
        df_profit = df_dash
    else:
        df_profit = df_all
    
    if df_profit.empty:
        st.info("Butuh data untuk hitung profit")
    else:
        col1, col2, col3 = st.columns(3)
        stake = col1.number_input("Stake per match (ribu Rp)", 10, 1000, 100)
        odds = col2.number_input("Odds Over 0.5", 1.1, 3.0, 1.75)
        win_rate = col3.slider("Win Rate %", 50, 95, 80)
        
        total = len(df_profit)
        wins = total * win_rate / 100
        loses = total - wins
        profit = (wins * (odds-1) * stake) - (loses * stake)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Match", total)
        m2.metric("Win", f"{wins:.0f}")
        m3.metric("Lose", f"{loses:.0f}")
        m4.metric("Profit", f"Rp {profit:,.0f} rb", delta=f"{profit/total:.1f} rb/match" if total else "0")
        
        st.success(f"💰 Dengan {total} match, win rate {win_rate}%, odds {odds}, stake {stake}rb → Profit Rp {profit:,.0f} ribu!")
        
        csv = df_profit.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV Archive", csv, f"skor60_archive_{datetime.now(WITA).strftime('%Y%m%d')}.csv", "text/csv")

st.caption("V9.2 KOLOM LENGKAP - Match, Liga Bener 🇮🇹 Serie A, Menit, Skor, Rekomendasi ✅, Signal 🔥, Status, Waktu WITA - Window 50-80 menit")
