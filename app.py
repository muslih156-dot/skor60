
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, glob, requests

WITA = timezone(timedelta(hours=8))

st.set_page_config(page_title="Trading Bola Menit 60", page_icon="⚽", layout="wide")

col_logo, col_title = st.columns([1,5])
with col_logo:
    st.markdown("## ⚽")
with col_title:
    st.title("Trading Bola Menit 60 - Last Goal System")
    st.caption(f"V9.3 AUTO-EXPIRE - Window 50-80 - {datetime.now(WITA).strftime('%d %b %Y %H:%M WITA')}")

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/muslih156-dot/skor60/main"

LEAGUE_MAP = {
    "ita.1": "🇮🇹 Serie A", "ita.2": "🇮🇹 Serie B",
    "eng.1": "🏴󐁧󐁢󐁥󐁮󐁧󐁿 Premier League", "eng.2": "🏴󐁧󐁢󐁥󐁮󐁧󐁿 Championship",
    "ger.1": "🇩🇪 Bundesliga", "ger.2": "🇩🇪 2. Bundesliga", "ger.dfb_pokal": "🇩🇪 DFB Pokal",
    "esp.1": "🇪🇸 LaLiga", "fra.1": "🇫🇷 Ligue 1", "ned.1": "🇳🇱 Eredivisie",
    "por.1": "🇵🇹 Primeira Liga", "bel.1": "🇧🇪 Jupiler Pro League",
    "uefa.champions": "🏆 Champions League", "uefa.europa": "🏆 Europa League",
    "afc.champions": "🏆 AFC Champions", "afc.cup": "🏆 AFC Cup",
    "swe.1": "🇸🇪 Allsvenskan", "nor.1": "🇳🇴 Eliteserien", "den.1": "🇩🇰 Superliga",
    "usa.1": "🇺🇸 MLS", "bra.1": "🇧🇷 Brasileirão", "jpn.1": "🇯🇵 J1 League",
    "idn.1": "🇮🇩 Liga 1", "tha.1": "🇹🇭 Thai League", "mys.1": "🇲🇾 Liga Super",
    "sau.1": "🇸🇦 Pro League", "qat.1": "🇶🇦 Stars League", "uae.1": "🇦🇪 Pro League",
    "egy.1": "🇪🇬 Premier League", "nga.1": "🇳🇬 NPFL",
}

def pretty_league(s):
    if not s: return "-"
    if s in LEAGUE_MAP: return LEAGUE_MAP[s]
    sl = s.lower()
    if "afc" in sl: return f"🏆 {s.replace('afc.','AFC ').replace('.',' ').title()}"
    if "ita" in sl: return "🇮🇹 Serie A" if "1" in s else f"🇮🇹 {s.title()}"
    if "eng" in sl: return f"🏴󐁧󐁢󐁥󐁮󐁧󐁿 {s.replace('eng.','').title()}"
    if "ger" in sl: return f"🇩🇪 {s.replace('ger.','').title()}"
    if "esp" in sl: return f"🇪🇸 LaLiga" if "1" in s else f"🇪🇸 {s.title()}"
    if "swe" in sl or "allsvenskan" in sl: return "🇸🇪 Allsvenskan"
    return s.replace("."," ").replace("_"," ").title()

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
    except:
        pass
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

# AUTO-EXPIRE LOGIC - sejam lalu auto FT!
now_wita = datetime.now(WITA)
if not df_dash.empty and 'created_at' in df_dash.columns:
    try:
        df_dash['created_at_dt'] = pd.to_datetime(df_dash['created_at'], errors='coerce')
        df_dash['umur_menit'] = (now_wita - df_dash['created_at_dt'].dt.tz_localize(None).apply(lambda x: x.replace(tzinfo=WITA) if pd.notna(x) and x.tzinfo is None else x)).dt.total_seconds() / 60
        # Fallback kalau tz error
        df_dash['umur_menit'] = df_dash['umur_menit'].fillna(0)
    except:
        df_dash['umur_menit'] = 0
        df_dash['created_at_dt'] = now_wita
    
    # Tandai yang udah lewat 35 menit dari deteksi (90-77=13 + 35 = 48 menit total match, harusnya FT)
    def update_status(row):
        umur = row.get('umur_menit', 0)
        minute = row.get('minute', 0)
        if umur > 40:  # Lebih dari 40 menit sejak ke-detect -> pasti FT
            return f"✅ FT - Selesai ({umur:.0f}m lalu)"
        elif umur > 25:
            return f"⏳ Menit {min(90, minute + int(umur))}' - Hampir FT ({umur:.0f}m lalu)"
        else:
            return row.get('status', 'AKTIF')
    
    df_dash['status_real'] = df_dash.apply(update_status, axis=1)
    df_dash['is_expired'] = df_dash['umur_menit'] > 40
    
    # Filter: live cuma yang umur < 35 menit
    df_live = df_dash[~df_dash['is_expired']].copy()
    df_expired = df_dash[df_dash['is_expired']].copy()
else:
    df_dash['status_real'] = df_dash.get('status','')
    df_dash['is_expired'] = False
    df_live = df_dash.copy()
    df_expired = pd.DataFrame()

# Enrich
if not df_dash.empty:
    df_dash['liga_bener'] = df_dash['league'].apply(pretty_league)
    df_dash['match'] = df_dash['home_team'] + " vs " + df_dash['away_team']
if not df_live.empty:
    df_live['liga_bener'] = df_live['league'].apply(pretty_league)
    df_live['match'] = df_live['home_team'] + " vs " + df_live['away_team']
    df_live['rekomendasi'] = df_live['status_real'].apply(lambda x: '⚠️ HATI-HATI' if '⚠️' in str(x) else ('✅ FT' if 'FT' in str(x) else '✅ REKOMENDASI - Gas!'))

st.sidebar.title("⚙️ Filter & Tools")
st.sidebar.code(f"Dashboard: {source_dash}\nArchive: {source_all}")
st.sidebar.metric("WITA", now_wita.strftime("%H:%M:%S"))
st.sidebar.metric("Live / Expired", f"{len(df_live)} / {len(df_expired) if not df_expired.empty else 0}")

if st.sidebar.button("🔄 Clear Cache & Reload"):
    st.cache_data.clear()
    st.rerun()

auto_hide = st.sidebar.checkbox("Auto-hide FT >40 menit", value=True)

tab1, tab2, tab3 = st.tabs(["🔥 Live (Auto-Expire)", "📦 Expired / FT", "📅 All Time"])

with tab1:
    st.subheader(f"🔥 Live Trading - {len(df_live)} aktif - V9.3 Auto-Expire 40 menit")
    
    if df_live.empty:
        if not df_dash.empty and not df_expired.empty:
            st.warning(f"Semua {len(df_expired)} match sudah FT (lebih dari 40 menit lalu). Cek tab Expired!")
            st.dataframe(df_expired[['home_team','away_team','liga_bener','minute','status_real']].head(10) if 'liga_bener' in df_expired.columns else df_expired.head(10))
        else:
            st.info("Belum ada peluang 0-0 menit 50-80 - bot scan tiap 5 menit PASTI!")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🔥 Live", len(df_live))
        c2.metric("✅ Rekomendasi", len(df_live[~df_live['status_real'].str.contains('⚠️', na=False)]))
        c3.metric("⏱️ Umur rata", f"{df_live['umur_menit'].mean():.0f}m" if 'umur_menit' in df_live.columns else "-")
        c4.metric("📅", now_wita.strftime("%d %b"))
        
        st.success(f"✅ Ada {len(df_live)} peluang LIVE (umur <40 menit)!")
        
        display_df = df_live.copy()
        cols_show = ['match', 'liga_bener', 'minute', 'score', 'status_real', 'umur_menit']
        if 'created_at' in display_df.columns:
            try:
                display_df['waktu'] = pd.to_datetime(display_df['created_at']).dt.strftime('%H:%M WITA')
                cols_show.append('waktu')
            except:
                pass
        
        st.dataframe(
            display_df[cols_show].rename(columns={
                'match': '⚽ Match', 'liga_bener': '🏆 Liga', 'minute': '⏱️ Menit Awal',
                'score': '📊 Skor', 'status_real': '📋 Status Real', 'umur_menit': '⏳ Umur', 'waktu': '🕐 Deteksi'
            }),
            use_container_width=True,
            height=400
        )
        
        # Detail
        for idx, row in df_live.head(3).iterrows():
            umur = row.get('umur_menit',0)
            st.info(f"🔥 {row['home_team']} vs {row['away_team']} - {row['liga_bener']} - Deteksi menit {row['minute']}' - Umur {umur:.0f} menit lalu - Status: {row['status_real']}")

with tab2:
    st.subheader(f"📦 Expired / FT - {len(df_expired)} match")
    if df_expired.empty:
        st.info("Belum ada yang expired")
    else:
        st.warning(f"{len(df_expired)} match sudah lewat >40 menit, otomatis FT - ga usah trading!")
        st.dataframe(
            df_expired[['home_team','away_team','liga_bener','minute','score','status_real','umur_menit']].rename(columns={
                'home_team': 'Home', 'away_team': 'Away', 'liga_bener': 'Liga'
            }) if 'liga_bener' in df_expired.columns else df_expired,
            use_container_width=True
        )

with tab3:
    st.subheader(f"📅 All Time - {source_all}")
    if df_all.empty:
        st.info("Archive kosong")
    else:
        df_all['liga_bener'] = df_all['league'].apply(pretty_league)
        st.dataframe(df_all[['home_team','away_team','liga_bener','minute','score','wita_date']].head(200), use_container_width=True)
        st.bar_chart(df_all['liga_bener'].value_counts().head(10))
        csv = df_all.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, f"skor60_{now_wita.strftime('%Y%m%d')}.csv", "text/csv")

st.caption("V9.3 AUTO-EXPIRE - Live cuma <40 menit, lebih dari itu auto FT - Parma 03:04 di 03:42 auto FT 38m lalu")
