
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, glob, io, requests

WITA = timezone(timedelta(hours=8))

st.set_page_config(page_title="Trading Bola Menit 60 - Full", page_icon="⚽", layout="wide", initial_sidebar_state="expanded")
st.title("⚽ Trading Bola Menit 60 - Last Goal System")
st.caption(f"V8.7 FIX WEB KOSONG - GitHub RAW Fallback | 200 Terbaru + Archive UNLIMITED + Export | {datetime.now(WITA).strftime('%d %b %Y %H:%M WITA')}")

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/muslih156-dot/skor60/main"

@st.cache_data(ttl=15)
def load_dashboard():
    # 1. Coba local dulu
    for p in ["data/matches.json", "matches.json", "./data/matches.json"]:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    if isinstance(j, list) and j:
                        real = [x for x in j if "TEST" not in str(x.get("match_id",""))]
                        if real:
                            print(f"Loaded {len(real)} from local {p}")
                            return pd.DataFrame(real), f"LOCAL {p} ({len(real)} match)"
        except Exception as e:
            print(f"Local {p} error {e}")
    
    # 2. Fallback: ambil langsung dari GitHub RAW biar ga kosong!
    try:
        url = f"{GITHUB_RAW_BASE}/data/matches.json"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            j = r.json()
            if isinstance(j, list) and j:
                real = [x for x in j if "TEST" not in str(x.get("match_id",""))]
                if real:
                    return pd.DataFrame(real), f"GITHUB RAW ({len(real)} match) - {url}"
    except Exception as e:
        print(f"GitHub RAW matches.json error {e}")
    
    return pd.DataFrame(), "NO DATA - Belum ada di local maupun GitHub RAW"

@st.cache_data(ttl=30)
def load_all_archive():
    all_data = []
    source_info = []
    
    # 1. Coba local archive bulanan
    archives = glob.glob("data/archive/2026-*.json")
    archives = [a for a in archives if "all_time" not in a]
    for arch in sorted(archives):
        try:
            with open(arch, "r", encoding="utf-8") as f:
                j = json.load(f)
                if isinstance(j, list):
                    all_data.extend(j)
                    source_info.append(f"{arch}: {len(j)}")
        except:
            pass
    
    # 2. Coba local all_time
    if not all_data:
        try:
            if os.path.exists("data/archive/all_time.json"):
                with open("data/archive/all_time.json", "r", encoding="utf-8") as f:
                    j = json.load(f)
                    if isinstance(j, list):
                        all_data = j
                        source_info.append(f"local all_time: {len(j)}")
        except:
            pass
    
    # 3. Fallback GitHub RAW all_time
    if not all_data:
        try:
            url = f"{GITHUB_RAW_BASE}/data/archive/all_time.json"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, list):
                    all_data = j
                    source_info.append(f"GITHUB RAW all_time: {len(j)}")
        except Exception as e:
            print(f"GitHub RAW all_time error {e}")
    
    # 4. Fallback GitHub RAW monthly
    if not all_data:
        try:
            # Coba bulan ini
            month_key = datetime.now(WITA).strftime("%Y-%m")
            url = f"{GITHUB_RAW_BASE}/data/archive/{month_key}.json"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, list):
                    all_data = j
                    source_info.append(f"GITHUB RAW {month_key}: {len(j)}")
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
    return df, " | ".join(source_info)

def is_rekomendasi(row):
    status = str(row.get('status', ''))
    if '⚠️' in status:
        return False
    return True

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Matches')
    return output.getvalue()

df_dash, source_dash = load_dashboard()
df_all, source_all = load_all_archive()

# SIDEBAR
st.sidebar.title("⚙️ Filter & Tools")
st.sidebar.caption(f"V8.7 FIX WEB KOSONG")
st.sidebar.markdown(f"**Data Source:**")
st.sidebar.code(f"Dashboard: {source_dash}\nArchive: {source_all}")

all_leagues = []
if not df_all.empty and 'league' in df_all.columns:
    all_leagues = sorted(df_all['league'].dropna().unique().tolist())
elif not df_dash.empty and 'league' in df_dash.columns:
    all_leagues = sorted(df_dash['league'].dropna().unique().tolist())

selected_leagues = st.sidebar.multiselect("🏆 Filter Liga", all_leagues, default=[])
filter_rekom = st.sidebar.selectbox("💡 Filter Rekomendasi", ["Semua", "✅ Rekomendasi Only", "⚠️ Warning Only"])
search_team = st.sidebar.text_input("🔍 Cari Tim (Home/Away)", "")

st.sidebar.markdown("---")
st.sidebar.markdown("**🔧 Debug**")
if st.sidebar.button("🔄 Clear Cache & Reload GitHub RAW"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info(f"Jam WITA: {datetime.now(WITA).strftime('%H:%M:%S')}\nDashboard: {len(df_dash)} match\nAll Time: {len(df_all)} match")

# TABS
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔥 Live Dashboard (200)", "📅 Monthly Summary", "📊 All Time Analytics", "💰 Profit Calculator", "📁 Export Center"])

def apply_filters(df):
    if df.empty:
        return df
    filtered = df.copy()
    if selected_leagues:
        filtered = filtered[filtered['league'].isin(selected_leagues)]
    if filter_rekom != "Semua":
        if filter_rekom == "✅ Rekomendasi Only":
            filtered = filtered[~filtered['status'].astype(str).str.contains('⚠️', na=False)]
        elif filter_rekom == "⚠️ Warning Only":
            filtered = filtered[filtered['status'].astype(str).str.contains('⚠️', na=False)]
    if search_team:
        mask = filtered['home_team'].astype(str).str.contains(search_team, case=False, na=False) | filtered['away_team'].astype(str).str.contains(search_team, case=False, na=False)
        filtered = filtered[mask]
    return filtered

with tab1:
    st.subheader("🔥 Live Dashboard - 200 Terbaru")
    st.caption(f"Source: {source_dash}")
    
    df_filtered = apply_filters(df_dash)
    
    if df_dash.empty:
        st.warning("📭 Dashboard kosong - cek GitHub RAW atau tunggu bot scan")
        st.info(f"Debug: {source_dash}\n\n{source_all}")
        st.markdown(f"""
        **Cek manual:**
        - Buka https://raw.githubusercontent.com/muslih156-dot/skor60/main/data/matches.json
        - Kalau ada data, klik **Clear Cache & Reload** di sidebar
        - Kalau kosong, bot belum nemu peluang menit 55-68 0-0
        """)
        # Tampilkan archive kalau dashboard kosong
        if not df_all.empty:
            st.success(f"Tapi archive ada {len(df_all)} match! Lihat di tab Monthly Summary")
            st.dataframe(df_all.head(20)[['created_at','home_team','away_team','league','minute','status']], use_container_width=True)
    else:
        if 'status' in df_filtered.columns:
            df_filtered['warning'] = df_filtered['status'].apply(lambda x: ' | '.join([p.strip() for p in str(x).split('|') if '⚠️' in p]) if '⚠️' in str(x) else '')
            df_filtered['status_bersih'] = df_filtered['status'].apply(lambda x: str(x).split('|')[0].strip() if '|' in str(x) else str(x))
            df_filtered['rekomendasi'] = df_filtered.apply(lambda r: '✅ REKOMENDASI - Gas!' if is_rekomendasi(r) else '⚠️ HATI-HATI', axis=1)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total (Filtered)", len(df_filtered), f"{len(df_dash)} total")
        col2.metric("✅ Rekomendasi", len(df_filtered[df_filtered['rekomendasi'].str.contains('REKOMENDASI', na=False)]) if 'rekomendasi' in df_filtered.columns else 0)
        col3.metric("⚠️ Warning", len(df_filtered[df_filtered['warning']!='']) if 'warning' in df_filtered.columns else 0)
        col4.metric("Source", source_dash.split("(")[0] if "(" in source_dash else source_dash)
        
        def highlight_row(row):
            rec = str(row.get('rekomendasi',''))
            if 'REKOMENDASI' in rec:
                return ['background-color: #d4edda; color: #155724; font-weight: bold'] * len(row)
            elif 'HATI-HATI' in rec:
                return ['background-color: #fff3cd; color: #856404'] * len(row)
            else:
                return [''] * len(row)
        
        cols_show = [c for c in ['created_at','home_team','away_team','league','minute','status_bersih','rekomendasi','warning'] if c in df_filtered.columns]
        show_df = df_filtered.head(50)[cols_show].copy()
        st.dataframe(show_df.style.apply(highlight_row, axis=1), use_container_width=True, hide_index=True, height=500)
        
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            st.download_button("📥 Download CSV (Filtered)", convert_df_to_csv(df_filtered), f"trading_menit60_filtered_{datetime.now(WITA).strftime('%Y%m%d_%H%M')}.csv", "text/csv")
        with col_exp2:
            st.download_button("📥 Download Excel (Filtered)", convert_df_to_excel(df_filtered), f"trading_menit60_filtered_{datetime.now(WITA).strftime('%Y%m%d_%H%M')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab2:
    st.subheader("📅 Monthly Summary - UNLIMITED")
    st.caption(f"Source: {source_all}")
    if df_all.empty:
        st.warning("Belum ada archive")
    else:
        df_all['month'] = pd.to_datetime(df_all['created_at']).dt.strftime('%Y-%m')
        df_all['date'] = pd.to_datetime(df_all['created_at']).dt.date
        monthly = df_all.groupby('month').size().reset_index(name='total_match')
        daily = df_all.groupby('date').size().reset_index(name='total_match')
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Bulan Ini", len(df_all[df_all['month']==datetime.now(WITA).strftime('%Y-%m')]))
        col2.metric("Total All Time", len(df_all))
        col3.metric("Rata-rata / Hari", f"{len(df_all)/max(len(daily),1):.1f}")
        col4.metric("Bulan Terbanyak", monthly.loc[monthly['total_match'].idxmax(), 'month'] if not monthly.empty else "-")
        
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.write("**Match per Bulan**")
            st.bar_chart(monthly.set_index('month'))
        with col_chart2:
            st.write("**Top 10 Liga**")
            if 'league' in df_all.columns:
                st.bar_chart(df_all['league'].value_counts().head(10))
        
        st.write("**Match per Hari**")
        st.line_chart(daily.tail(30).set_index('date'))
        
        for month in sorted(monthly['month'].unique(), reverse=True)[:6]:
            with st.expander(f"📅 {month} - {monthly[monthly['month']==month]['total_match'].values[0]} match"):
                month_df = df_all[df_all['month']==month]
                st.dataframe(month_df[['created_at','home_team','away_team','league','minute','status']].head(100), use_container_width=True)

with tab3:
    st.subheader("📊 All Time Analytics - UNLIMITED")
    if df_all.empty:
        st.info("Belum ada data")
    else:
        df_analytics = apply_filters(df_all)
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Top 15 Liga**")
            if 'league' in df_analytics.columns:
                st.bar_chart(df_analytics['league'].value_counts().head(15))
        with col2:
            st.write("**Distribusi Menit**")
            if 'minute' in df_analytics.columns:
                st.bar_chart(df_analytics['minute'].value_counts().sort_index())
        st.dataframe(df_analytics.head(200)[['created_at','home_team','away_team','league','minute','status']], use_container_width=True, height=400)

with tab4:
    st.subheader("💰 Profit Calculator")
    if df_all.empty:
        st.info("Butuh data")
    else:
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            stake = st.number_input("💵 Stake per Match (Rp)", min_value=10000, max_value=10000000, value=50000, step=10000)
        with col_p2:
            odds = st.number_input("📈 Odds Last Goal", min_value=1.1, max_value=10.0, value=2.5, step=0.1)
        with col_p3:
            win_rate = st.slider("🎯 Win Rate (%)", 0, 100, 65)
        total_matches = len(df_all)
        wins = int(total_matches * win_rate / 100)
        losses = total_matches - wins
        profit_per_win = stake * (odds - 1)
        total_profit = (wins * profit_per_win) - (losses * stake)
        roi = (total_profit / (total_matches * stake) * 100) if total_matches>0 else 0
        col_res1, col_res2, col_res3, col_res4 = st.columns(4)
        col_res1.metric("Total Match", total_matches)
        col_res2.metric("Est. Wins", wins, f"{win_rate}%")
        col_res3.metric("Total Profit", f"Rp {total_profit:,.0f}", f"{roi:.1f}% ROI")
        col_res4.metric("Profit / Bulan", f"Rp {total_profit/ max(len(df_all['month'].unique()),1):,.0f}")

with tab5:
    st.subheader("📁 Export Center")
    col_ec1, col_ec2 = st.columns(2)
    with col_ec1:
        st.markdown("**📥 Dashboard (200)**")
        if not df_dash.empty:
            st.download_button("CSV Dashboard", convert_df_to_csv(df_dash), f"dashboard_200_{datetime.now(WITA).strftime('%Y%m%d')}.csv", "text/csv", key="ec1")
            st.download_button("Excel Dashboard", convert_df_to_excel(df_dash), f"dashboard_200_{datetime.now(WITA).strftime('%Y%m%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="ec2")
    with col_ec2:
        st.markdown("**📥 All Time UNLIMITED**")
        if not df_all.empty:
            st.download_button("CSV All Time UNLIMITED", convert_df_to_csv(df_all), f"all_time_unlimited_{datetime.now(WITA).strftime('%Y%m%d')}.csv", "text/csv", key="ec3")
            st.download_button("Excel All Time", convert_df_to_excel(df_all), f"all_time_{datetime.now(WITA).strftime('%Y%m%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="ec4")
    
    st.markdown("---")
    if not df_all.empty and 'month' in df_all.columns:
        months = sorted(df_all['month'].unique(), reverse=True)
        selected_month_export = st.selectbox("Pilih Bulan", months)
        month_data = df_all[df_all['month']==selected_month_export]
        col_me1, col_me2 = st.columns(2)
        with col_me1:
            st.download_button(f"CSV {selected_month_export}", convert_df_to_csv(month_data), f"monthly_{selected_month_export}.csv", "text/csv", key=f"csv_{selected_month_export}")
        with col_me2:
            st.download_button(f"Excel {selected_month_export}", convert_df_to_excel(month_data), f"monthly_{selected_month_export}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"excel_{selected_month_export}")

st.sidebar.markdown("---")
st.sidebar.caption("V8.7 FIX WEB KOSONG - GitHub RAW Fallback")
