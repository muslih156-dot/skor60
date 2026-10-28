
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os

WITA = timezone(timedelta(hours=8))

st.set_page_config(page_title="Trading Bola Menit 60 - Last Goal System", page_icon="⚽", layout="wide")
st.title("⚽ Trading Bola Menit 60 - Last Goal System")
st.caption(f"Detektor peluang Last Goal menit 60 skor 0-0 | 220 Liga Dunia + Warning + Rekomendasi | {datetime.now(WITA).strftime('%d %b %Y %H:%M WITA')}")

@st.cache_data(ttl=30)
def load_data():
    for p in ["data/matches.json", "matches.json"]:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    if j:
                        return pd.DataFrame(j)
        except:
            pass
    return pd.DataFrame()

df = load_data()

# Fungsi cek rekomendasi
def is_rekomendasi(row):
    status = str(row.get('status', ''))
    league = str(row.get('league', '')).lower()
    # Kalau ada warning = bukan rekomendasi
    if '⚠️' in status:
        return False
    # Liga top tanpa warning = rekomendasi
    top_keywords = ['premier league', 'la liga', 'serie a', 'bundesliga', 'ligue 1', 'eredivisie', 'primeira liga', 'super lig', 'pro league',
                    'liga 1 indonesia', 'a-league', 'j1 league', 'k league', 'mls', 'brasileirao', 'liga mx',
                    'champions league', 'europa league', 'conference league', 'nations league', 'champions', 'europa']
    # Cek apakah liga termasuk top
    for kw in top_keywords:
        if kw in league:
            return True
    # Kalau status AKTIF tanpa warning dan liga tidak aneh = rekomendasi ringan
    if 'AKTIF' in status and '⚠️' not in status:
        return True
    return False

if df.empty:
    st.info("📭 Belum ada peluang Last Goal - bot scan 220 liga dunia tiap 5 menit. Data akan muncul otomatis pas ada bola menit 60 0-0")
    st.success(f"✅ Last Goal System aktif | 220 Liga Dunia | Bot jalan tiap 5 menit | Jam: {datetime.now(WITA).strftime('%H:%M WITA')}")
    st.caption("Jam rame: Liga Indo & Australia sore 16:30-20:00 WITA | Eropa 00:45-03:00 WITA")
else:
    # Tambah kolom warning dan rekomendasi
    if 'status' in df.columns:
        df['warning'] = df['status'].apply(lambda x: ' | '.join([p.strip() for p in str(x).split('|') if '⚠️' in p]) if '⚠️' in str(x) else '')
        df['status_bersih'] = df['status'].apply(lambda x: str(x).split('|')[0].strip() if '|' in str(x) else str(x))
        df['rekomendasi'] = df.apply(lambda row: '✅ REKOMENDASI - Gas Trading!' if is_rekomendasi(row) else '⚠️ HATI-HATI - Cek odds dulu' if '⚠️' in str(row.get('status','')) else '➖ NETRAL', axis=1)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Peluang", len(df))
    rekomendasi_df = df[df['rekomendasi'].str.contains('REKOMENDASI', na=False)] if 'rekomendasi' in df.columns else pd.DataFrame()
    col2.metric("✅ Rekomendasi", len(rekomendasi_df))
    warning_df = df[df['warning'] != ''] if 'warning' in df.columns else pd.DataFrame()
    col3.metric("⚠️ Warning", len(warning_df))
    aktif = df[df['status'].astype(str).str.contains('AKTIF', na=False)] if 'status' in df.columns else pd.DataFrame()
    col4.metric("AKTIF 🔥", len(aktif))
    
    st.subheader("📋 20 Peluang Last Goal Terakhir - Rekomendasi & Warning")
    
    # Highlight: Hijau untuk rekomendasi, Kuning untuk warning
    def highlight_row(row):
        rec = str(row.get('rekomendasi', ''))
        if 'REKOMENDASI' in rec:
            return ['background-color: #d4edda; color: #155724; font-weight: bold'] * len(row)
        elif 'HATI-HATI' in rec or '⚠️' in str(row.get('status', '')):
            return ['background-color: #fff3cd; color: #856404'] * len(row)
        else:
            return [''] * len(row)
    
    cols_show = []
    for c in ['created_at','home_team','away_team','league','minute','status_bersih','rekomendasi','warning','shots_total','dangerous_attacks','final_status','goal_after_60']:
        if c in df.columns:
            cols_show.append(c)
    
    show_df = df.head(20)[cols_show].copy()
    if 'created_at' in show_df.columns:
        try:
            show_df['created_at'] = pd.to_datetime(show_df['created_at']).dt.strftime('%d/%m %H:%M')
        except:
            pass
    
    show_df = show_df.rename(columns={'status_bersih': 'status', 'warning': '⚠️ WARNING', 'rekomendasi': '💡 REKOMENDASI'})
    
    st.dataframe(show_df.style.apply(highlight_row, axis=1), use_container_width=True, hide_index=True)
    
    # Legend
    col_legend1, col_legend2 = st.columns(2)
    with col_legend1:
        st.success("✅ **REKOMENDASI - Gas Trading!**\n\n- Tanpa warning\n- Liga top: Premier League, La Liga, Liga 1 Indo, A-League, UCL, Europa League\n- Odds liquid, aman buat Last Goal")
    with col_legend2:
        st.warning("⚠️ **HATI-HATI - Cek odds dulu**\n\n- Ada warning: LIGA WANITA, TIM MUDA, DIVISI BAWAH, LIGA MINOR, TIM II/III, CUP\n- Cek market dan odds dulu, jangan all-in")
    
    with st.expander("📖 Detail Arti WARNING"):
        st.markdown("""
        - ⚠️ **LIGA WANITA** = Liquiditas rendah
        - ⚠️ **TIM MUDA/CADANGAN** = U17, U19, U21, Youth, Reserves, II/III
        - ⚠️ **DIVISI BAWAH** = Liga 2, Serie C/D
        - ⚠️ **LIGA MINOR/ANEH** = Futsal, Beach, Friendly, Gulf, NextGen, Pokalen, Corners
        - ⚠️ **TIM II/III** = Tim kedua/ketiga
        - ⚠️ **CUP** = Piala - Kadang sengit
        - ⚠️ **LIGA KECIL** = Bukan liga top
        """)

st.sidebar.title("Last Goal System")
st.sidebar.success("Phase 1 ✅ Memory\nPhase 2 ✅ Tracking\nPhase 3 ✅ Dashboard\nPhase 4 ⏳ ML Model")
st.sidebar.markdown("**V8.3 FULL 220 LIGA + REKOMENDASI**")
st.sidebar.markdown("- ✅ Hijau = Rekomendasi Gas!")
st.sidebar.markdown("- ⚠️ Kuning = Hati-hati")
st.sidebar.markdown("- 220 liga dunia")
st.sidebar.markdown("- Liga Indo, SEA, Australia, Europa")
st.sidebar.info(f"Jam WITA: {datetime.now(WITA).strftime('%H:%M:%S')}\nBot scan tiap 5 menit")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
