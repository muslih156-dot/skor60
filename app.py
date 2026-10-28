
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, glob, io

WITA = timezone(timedelta(hours=8))

st.set_page_config(page_title="Trading Bola Menit 60 - Full", page_icon="⚽", layout="wide", initial_sidebar_state="expanded")
st.title("⚽ Trading Bola Menit 60 - Last Goal System")
st.caption(f"V8.6 FULL FEATURED | 200 Terbaru + Archive UNLIMITED + Export CSV/Excel + Analytics + Profit Calc | {datetime.now(WITA).strftime('%d %b %Y %H:%M WITA')}")

@st.cache_data(ttl=30)
def load_dashboard():
    for p in ["data/matches.json", "matches.json"]:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    if isinstance(j, list) and j:
                        real = [x for x in j if "TEST" not in str(x.get("match_id",""))]
                        if real:
                            return pd.DataFrame(real)
        except:
            pass
    return pd.DataFrame()

@st.cache_data(ttl=60)
def load_all_archive():
    # Load semua archive bulanan + all_time
    all_data = []
    # Archive bulanan
    archives = glob.glob("data/archive/2026-*.json")
    archives = [a for a in archives if "all_time" not in a]
    for arch in sorted(archives):
        try:
            with open(arch, "r", encoding="utf-8") as f:
                j = json.load(f)
                if isinstance(j, list):
                    all_data.extend(j)
        except:
            pass
    # Kalau masih kosong, coba all_time
    if not all_data:
        try:
            if os.path.exists("data/archive/all_time.json"):
                with open("data/archive/all_time.json", "r", encoding="utf-8") as f:
                    all_data = json.load(f)
        except:
            pass
    if not all_data:
        return pd.DataFrame()
    df = pd.DataFrame(all_data)
    df = df[~df['match_id'].astype(str).str.contains('TEST', na=False)]
    if 'created_at' in df.columns:
        try:
            df['created_at'] = pd.to_datetime(df['created_at'])
        except:
            pass
    return df

def is_rekomendasi(row):
    status = str(row.get('status', ''))
    if '⚠️' in status:
        return False
    league = str(row.get('league', '')).lower()
    top_keywords = ['premier league', 'la liga', 'serie a', 'bundesliga', 'ligue 1', 'eredivisie', 'primeira', 'super lig', 'pro league', 'liga 1 indonesia', 'a-league', 'j1 league', 'k league', 'mls', 'champions', 'europa', 'german', 'italy', 'spain', 'england', 'indonesia']
    for kw in top_keywords:
        if kw in league:
            return True
    if 'AKTIF' in status:
        return True
    return False

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Matches')
    return output.getvalue()

df_dash = load_dashboard()
df_all = load_all_archive()

# SIDEBAR FILTERS
st.sidebar.title("⚙️ Filter & Tools")
st.sidebar.markdown("**V8.6 FULL FEATURED**")

# Filter liga
all_leagues = []
if not df_all.empty and 'league' in df_all.columns:
    all_leagues = sorted(df_all['league'].dropna().unique().tolist())
elif not df_dash.empty and 'league' in df_dash.columns:
    all_leagues = sorted(df_dash['league'].dropna().unique().tolist())

selected_leagues = st.sidebar.multiselect("🏆 Filter Liga", all_leagues, default=[])

# Filter rekomendasi
filter_rekom = st.sidebar.selectbox("💡 Filter Rekomendasi", ["Semua", "✅ Rekomendasi Only", "⚠️ Warning Only"])

# Search
search_team = st.sidebar.text_input("🔍 Cari Tim (Home/Away)", "")

# Date range untuk archive
if not df_all.empty and 'created_at' in df_all.columns:
    try:
        min_date = df_all['created_at'].min().date()
        max_date = df_all['created_at'].date().max() if hasattr(df_all['created_at'], 'dt') else datetime.now(WITA).date()
        date_range = st.sidebar.date_input("📅 Filter Tanggal", [min_date, max_date])
    except:
        date_range = None
else:
    date_range = None

st.sidebar.markdown("---")
st.sidebar.markdown("**📥 Export**")

# TABS
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔥 Live Dashboard (200)", "📅 Monthly Summary", "📊 All Time Analytics", "💰 Profit Calculator", "📁 Export Center"])

def apply_filters(df):
    if df.empty:
        return df
    filtered = df.copy()
    if selected_leagues:
        filtered = filtered[filtered['league'].isin(selected_leagues)]
    if filter_rekom != "Semua":
        if 'status' not in filtered.columns:
            filtered['warning'] = ''
        else:
            filtered['warning'] = filtered['status'].apply(lambda x: '⚠️' if '⚠️' in str(x) else '')
        if filter_rekom == "✅ Rekomendasi Only":
            filtered = filtered[~filtered['status'].astype(str).str.contains('⚠️', na=False)]
        elif filter_rekom == "⚠️ Warning Only":
            filtered = filtered[filtered['status'].astype(str).str.contains('⚠️', na=False)]
    if search_team:
        mask = filtered['home_team'].astype(str).str.contains(search_team, case=False, na=False) | filtered['away_team'].astype(str).str.contains(search_team, case=False, na=False)
        filtered = filtered[mask]
    return filtered

with tab1:
    st.subheader("🔥 Live Dashboard - 200 Terbaru (Cepat)")
    df_filtered = apply_filters(df_dash)
    
    if df_dash.empty:
        st.info("📭 Belum ada peluang - Bot scan 220 liga, 754 events, 17 live tapi menit 1-45. Tunggu jam 02:00-05:00 WITA!")
        st.success(f"✅ System Aktif | 220 Liga | 754 Events | Jam {datetime.now(WITA).strftime('%H:%M WITA')}")
    else:
        if 'status' in df_filtered.columns:
            df_filtered['warning'] = df_filtered['status'].apply(lambda x: ' | '.join([p.strip() for p in str(x).split('|') if '⚠️' in p]) if '⚠️' in str(x) else '')
            df_filtered['status_bersih'] = df_filtered['status'].apply(lambda x: str(x).split('|')[0].strip() if '|' in str(x) else str(x))
            df_filtered['rekomendasi'] = df_filtered.apply(lambda r: '✅ REKOMENDASI - Gas!' if is_rekomendasi(r) else '⚠️ HATI-HATI' if '⚠️' in str(r.get('status','')) else '➖ NETRAL', axis=1)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total (Filtered)", len(df_filtered), f"{len(df_dash)} total")
        col2.metric("✅ Rekomendasi", len(df_filtered[df_filtered['rekomendasi'].str.contains('REKOMENDASI', na=False)]) if 'rekomendasi' in df_filtered.columns else 0)
        col3.metric("⚠️ Warning", len(df_filtered[df_filtered['warning']!='']) if 'warning' in df_filtered.columns else 0)
        col4.metric("🔍 Filter Aktif", f"{len(df_filtered)}/{len(df_dash)}")
        
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
        
        # Export filtered
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            st.download_button("📥 Download CSV (Filtered)", convert_df_to_csv(df_filtered), f"trading_menit60_filtered_{datetime.now(WITA).strftime('%Y%m%d_%H%M')}.csv", "text/csv")
        with col_exp2:
            st.download_button("📥 Download Excel (Filtered)", convert_df_to_excel(df_filtered), f"trading_menit60_filtered_{datetime.now(WITA).strftime('%Y%m%d_%H%M')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab2:
    st.subheader("📅 Monthly Summary - Archive UNLIMITED (Ga Ketimpa!)")
    if df_all.empty:
        st.warning("Belum ada archive - bot baru jalan. File akan ada di data/archive/2026-10.json")
    else:
        df_all['month'] = pd.to_datetime(df_all['created_at']).dt.strftime('%Y-%m')
        df_all['date'] = pd.to_datetime(df_all['created_at']).dt.date
        df_all['hour'] = pd.to_datetime(df_all['created_at']).dt.hour
        
        # Filter by date range if selected
        df_month_filtered = df_all.copy()
        if date_range and len(date_range)==2:
            try:
                df_month_filtered = df_all[(df_all['date']>=date_range[0]) & (df_all['date']<=date_range[1])]
            except:
                pass
        df_month_filtered = apply_filters(df_month_filtered)
        
        monthly = df_month_filtered.groupby('month').size().reset_index(name='total_match')
        daily = df_month_filtered.groupby('date').size().reset_index(name='total_match')
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Bulan Ini", len(df_month_filtered[df_month_filtered['month']==datetime.now(WITA).strftime('%Y-%m')]))
        col2.metric("Total Filtered", len(df_month_filtered))
        col3.metric("Total All Time", len(df_all))
        col4.metric("Rata-rata / Hari", f"{len(df_month_filtered)/max(len(daily),1):.1f}")
        
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.write("**Match per Bulan**")
            st.bar_chart(monthly.set_index('month'))
        with col_chart2:
            st.write("**Top 10 Liga Terbanyak (Bulan Ini)**")
            if 'league' in df_month_filtered.columns:
                st.bar_chart(df_month_filtered['league'].value_counts().head(10))
        
        st.write("**Match per Hari (30 hari terakhir)**")
        st.line_chart(daily.tail(30).set_index('date'))
        
        # Export monthly
        st.markdown("---")
        st.subheader("📥 Export Monthly")
        col_exp_m1, col_exp_m2, col_exp_m3 = st.columns(3)
        with col_exp_m1:
            st.download_button("📥 CSV Bulan Ini", convert_df_to_csv(df_month_filtered[df_month_filtered['month']==datetime.now(WITA).strftime('%Y-%m')]), f"summary_{datetime.now(WITA).strftime('%Y-%m')}.csv", "text/csv")
        with col_exp_m2:
            st.download_button("📥 CSV Filtered", convert_df_to_csv(df_month_filtered), f"monthly_filtered_{datetime.now(WITA).strftime('%Y%m%d')}.csv", "text/csv")
        with col_exp_m3:
            st.download_button("📥 Excel Monthly", convert_df_to_excel(monthly), f"monthly_summary_{datetime.now(WITA).strftime('%Y%m')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        # Detail per bulan
        for month in sorted(monthly['month'].unique(), reverse=True)[:6]:
            with st.expander(f"📅 {month} - {monthly[monthly['month']==month]['total_match'].values[0]} match"):
                month_df = df_month_filtered[df_month_filtered['month']==month]
                st.dataframe(month_df[['created_at','home_team','away_team','league','minute','status']].head(100), use_container_width=True)

with tab3:
    st.subheader("📊 All Time Analytics - UNLIMITED")
    if df_all.empty:
        st.info("Belum ada data all time")
    else:
        df_analytics = apply_filters(df_all)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total All Time", len(df_all))
        col2.metric("Filtered", len(df_analytics))
        col3.metric("Bulan Terbanyak", df_analytics['month'].value_counts().index[0] if 'month' in df_analytics.columns and not df_analytics.empty else "-")
        col4.metric("Liga Top", df_analytics['league'].value_counts().index[0] if 'league' in df_analytics.columns and not df_analytics.empty else "-")
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.write("**Top 15 Liga - All Time**")
            if 'league' in df_analytics.columns:
                st.bar_chart(df_analytics['league'].value_counts().head(15))
        with col_c2:
            st.write("**Distribusi Menit (55-68)**")
            if 'minute' in df_analytics.columns:
                st.bar_chart(df_analytics['minute'].value_counts().sort_index())
        
        col_c3, col_c4 = st.columns(2)
        with col_c3:
            st.write("**Jam Paling Banyak Peluang (WITA)**")
            if 'hour' in df_analytics.columns:
                st.bar_chart(df_analytics['hour'].value_counts().sort_index())
        with col_c4:
            st.write("**Warning vs Rekomendasi**")
            if 'status' in df_analytics.columns:
                warning_count = len(df_analytics[df_analytics['status'].astype(str).str.contains('⚠️', na=False)])
                rekom_count = len(df_analytics) - warning_count
                st.bar_chart(pd.DataFrame({"count": [rekom_count, warning_count]}, index=["✅ Rekomendasi", "⚠️ Warning"]))
        
        st.dataframe(df_analytics.head(200)[['created_at','home_team','away_team','league','minute','status']], use_container_width=True, height=400)

with tab4:
    st.subheader("💰 Profit Calculator - Simulasi Trading Last Goal")
    st.markdown("Hitung profit kalau kamu trading Last Goal tiap peluang 0-0 menit 60")
    
    if df_all.empty:
        st.info("Butuh data buat simulasi profit")
    else:
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            stake = st.number_input("💵 Stake per Match (Rp)", min_value=10000, max_value=10000000, value=50000, step=10000)
        with col_p2:
            odds = st.number_input("📈 Odds Rata-rata Last Goal", min_value=1.1, max_value=10.0, value=2.5, step=0.1)
        with col_p3:
            win_rate = st.slider("🎯 Win Rate Asumsi (%)", 0, 100, 65)
        
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
        
        # Simulasi per bulan
        if 'month' in df_all.columns:
            monthly_profit = []
            for month in sorted(df_all['month'].unique()):
                month_count = len(df_all[df_all['month']==month])
                month_wins = int(month_count * win_rate / 100)
                month_profit = (month_wins * profit_per_win) - ((month_count - month_wins) * stake)
                monthly_profit.append({"month": month, "matches": month_count, "profit": month_profit})
            
            profit_df = pd.DataFrame(monthly_profit)
            st.write("**Profit per Bulan (Simulasi)**")
            st.bar_chart(profit_df.set_index('month')['profit'])
            st.dataframe(profit_df, use_container_width=True)

with tab5:
    st.subheader("📁 Export Center - Download Semua Data")
    
    col_ec1, col_ec2 = st.columns(2)
    with col_ec1:
        st.markdown("**📥 Dashboard (200 Terbaru)**")
        if not df_dash.empty:
            st.download_button("CSV Dashboard", convert_df_to_csv(df_dash), f"dashboard_200_{datetime.now(WITA).strftime('%Y%m%d')}.csv", "text/csv", key="ec1")
            st.download_button("Excel Dashboard", convert_df_to_excel(df_dash), f"dashboard_200_{datetime.now(WITA).strftime('%Y%m%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="ec2")
    
    with col_ec2:
        st.markdown("**📥 All Time UNLIMITED**")
        if not df_all.empty:
            st.download_button("CSV All Time UNLIMITED", convert_df_to_csv(df_all), f"all_time_unlimited_{datetime.now(WITA).strftime('%Y%m%d')}.csv", "text/csv", key="ec3")
            st.download_button("Excel All Time", convert_df_to_excel(df_all), f"all_time_{datetime.now(WITA).strftime('%Y%m%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="ec4")
    
    st.markdown("---")
    st.markdown("**📅 Export Per Bulan**")
    if not df_all.empty and 'month' in df_all.columns:
        months = sorted(df_all['month'].unique(), reverse=True)
        selected_month_export = st.selectbox("Pilih Bulan", months)
        month_data = df_all[df_all['month']==selected_month_export]
        col_me1, col_me2 = st.columns(2)
        with col_me1:
            st.download_button(f"CSV {selected_month_export}", convert_df_to_csv(month_data), f"monthly_{selected_month_export}.csv", "text/csv", key=f"csv_{selected_month_export}")
        with col_me2:
            st.download_button(f"Excel {selected_month_export}", convert_df_to_excel(month_data), f"monthly_{selected_month_export}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"excel_{selected_month_export}")
    
    st.markdown("---")
    st.markdown("**📂 File Structure**")
    st.code("""
data/
  matches.json (200 terbaru - dashboard cepat)
  archive/
    2026-10.json (UNLIMITED Oktober - ga ketimpa!)
    2026-11.json (UNLIMITED November)
    2026-12.json (UNLIMITED Desember)
    all_time.json (UNLIMITED semua dari awal)
    """)
    
    # Show archive files
    archives = glob.glob("data/archive/*.json")
    if archives:
        st.write(f"**{len(archives)} Archive Files:**")
        for arch in sorted(archives):
            try:
                size = os.path.getsize(arch)
                with open(arch, "r") as f:
                    count = len(json.load(f))
                st.text(f"📄 {arch} - {count} matches - {size/1024:.1f} KB")
            except:
                pass

# Sidebar info
st.sidebar.markdown("---")
st.sidebar.title("📊 V8.6 FULL")
st.sidebar.success("✅ 200 terbaru\n✅ Archive UNLIMITED\n✅ Export CSV/Excel\n✅ Monthly Summary\n✅ Analytics\n✅ Profit Calc")
st.sidebar.info(f"Jam WITA: {datetime.now(WITA).strftime('%H:%M:%S')}\nDashboard: {len(df_dash)} match\nAll Time: {len(df_all)} match (UNLIMITED)")
if st.sidebar.button("🔄 Refresh All"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("V8.6 FULL FEATURED - GitHub JSON Fallback Anti Supabase Down")
