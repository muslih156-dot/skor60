"""
app.py
Dashboard Streamlit Produksi untuk TRADING BOLA MENIT 60 – LAST GOAL SYSTEM.
Membaca langsung dari database operasional dan file histori yang tersimpan tanpa membuat
data dummy. Menampilkan pemisahan profit aktual vs simulasi, 5 kartu utama, 6 grafik Plotly,
ringkasan trading day (cut-off 12:00 WITA), tabel 20 pertandingan terbaru dengan filter,
dan panel penjelasan audit detail.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from zoneinfo import ZoneInfo

from config import (
    CURRENCY,
    DEFAULT_STAKE,
    MATCHES_JSON_PATH,
    MIN_SAMPLE_SIZE_RELIABLE,
    SIMULATED_ODDS,
    TIMEZONE_NAME,
)
from database import TradingDatabase, load_scan_metadata
from settlement import audit_result
from statistics import compute_full_dashboard_statistics

WITA_TZ = ZoneInfo(TIMEZONE_NAME)

st.set_page_config(
    page_title="TRADING BOLA MENIT 60 – LAST GOAL SYSTEM",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Styling CSS bersih & profesional untuk kartu dan badge status
st.markdown(
    """
    <style>
    .main-header {
        background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
        padding: 1.4rem 1.8rem;
        border-radius: 12px;
        border-left: 6px solid #10b981;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background-color: #1e293b;
        color: #f8fafc;
        padding: 1.1rem;
        border-radius: 10px;
        border: 1px solid #334155;
        height: 100%;
    }
    .metric-title {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94a3b8;
        margin-bottom: 0.35rem;
    }
    .metric-value {
        font-size: 1.45rem;
        font-weight: 700;
        color: #ffffff;
    }
    .metric-sub {
        font-size: 0.80rem;
        color: #cbd5e1;
        margin-top: 0.3rem;
    }
    .badge-win { background-color: #16a34a; color: white; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .badge-lose { background-color: #dc2626; color: white; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .badge-live { background-color: #2563eb; color: white; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .badge-pending { background-color: #ca8a04; color: white; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .badge-void { background-color: #64748b; color: white; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .badge-review { background-color: #ea580c; color: white; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


def format_idr(amount: int) -> str:
    """Memformat integer menjadi format Rupiah (contoh: Rp50.000 atau -Rp50.000)."""
    sign = "-" if amount < 0 else ""
    formatted = f"{abs(int(amount)):,}".replace(",", ".")
    return f"{sign}Rp{formatted}"


def get_peak_hours_label(now_wita: datetime) -> str:
    """Memberikan panduan informasi Peak Hours berdasarkan jam WITA saat ini (Bagian J)."""
    h = now_wita.hour
    if 13 <= h < 19:
        return "13:00–19:00 WITA: Jendela Potensi Pertandingan Asia"
    if h >= 20 or h < 2:
        return "20:00–02:00 WITA: Jendela Potensi Pertandingan Eropa"
    if 2 <= h < 7:
        return "02:00–07:00 WITA: Jendela Potensi Pertandingan Amerika"
    return "07:00–13:00 WITA: Jam Transisi (Aktivitas Pertandingan Reguler Rendah)"


def render_dashboard() -> None:
    db = TradingDatabase()
    all_records = db.get_all_matches()
    scan_meta = load_scan_metadata()
    stats = compute_full_dashboard_statistics(all_records)

    now_wita = datetime.now(timezone.utc).astimezone(WITA_TZ)
    last_scan_wita = scan_meta.get("scan_timestamp_wita") or "BELUM TERSEDIA"
    source_status = scan_meta.get("source_status") or "NEVER_SCANNED"

    if MATCHES_JSON_PATH.exists():
        mtime = datetime.fromtimestamp(MATCHES_JSON_PATH.stat().st_mtime, tz=timezone.utc).astimezone(WITA_TZ)
        last_db_update_str = mtime.strftime("%Y-%m-%d %H:%M:%S WITA")
    else:
        last_db_update_str = "BELUM ADA DATABASE"

    # =================================================================
    # 1. HEADER UTAMA (Bagian L.1)
    # =================================================================
    st.markdown(
        f"""
        <div class="main-header">
            <h2 style="margin:0; font-weight:800;">⚽ TRADING BOLA MENIT 60 — LAST GOAL SYSTEM</h2>
            <p style="margin:4px 0 10px 0; color:#94a3b8;">
                Market: <b>OVER 0.5 GOAL AFTER ENTRY (Menit 60'–66', Skor Entry 0-0)</b> |
                Cut-Off Trading Day: <b>12:00 WITA</b>
            </p>
            <div style="display:flex; flex-wrap:wrap; gap:18px; font-size:0.86rem;">
                <span><b>System Status:</b> {source_status}</span>
                <span><b>Data Source:</b> ESPN API (All + Multi-League)</span>
                <span><b>Last Successful Scan:</b> {last_scan_wita}</span>
                <span><b>Last DB Update:</b> {last_db_update_str}</span>
                <span><b>Current WITA:</b> {now_wita.strftime('%Y-%m-%d %H:%M:%S')}</span>
                <span><b>Total Matches Recorded:</b> {len(all_records)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(
        f"🕒 **Panduan Monitoring Jam Aktif (WITA):** {get_peak_hours_label(now_wita)} "
        f"*(Panduan monitoring, bukan jaminan jumlah pertandingan).* "
        f"Pertandingan LIVE terdeteksi pada scan terakhir: **{scan_meta.get('live_matches_seen', 0)}**"
    )

    sim_stats = stats["simulated"]
    act_stats = stats["actual"]
    major_stats = stats["by_league_tier"]["MAJOR"]

    # =================================================================
    # 2. LIMA KARTU UTAMA (Bagian L.2)
    # =================================================================
    cols = st.columns(5)

    with cols[0]:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">CARD 1 – MODAL PER MATCH</div>
                <div class="metric-value">{format_idr(DEFAULT_STAKE)}</div>
                <div class="metric-sub">Odds Simulasi: <b>{SIMULATED_ODDS:.2f}</b> ({CURRENCY})</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[1]:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">CARD 2 – TOTAL MODAL KELUAR</div>
                <div class="metric-value">{format_idr(sim_stats['total_stake_settled'])}</div>
                <div class="metric-sub">Settled: <b>{sim_stats['settled_matches']}</b> Match (Excl. Pending/Void)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[2]:
        act_profit_label = (
            f"{format_idr(act_stats['net_profit'])} (ROI {act_stats['roi']:.2f}%)"
            if act_stats["available"]
            else "ACTUAL ODDS: NOT AVAILABLE"
        )
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">CARD 3 – TOTAL PROFIT</div>
                <div class="metric-value">{format_idr(sim_stats['net_profit'])} <span style="font-size:0.8rem; color:#10b981;">(Sim)</span></div>
                <div class="metric-sub">
                    Sim ROI: <b>{sim_stats['roi']:.2f}%</b><br/>
                    Actual: <b>{act_profit_label}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[3]:
        ci_low, ci_high = sim_stats["wilson_ci_95"]
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">CARD 4 – WIN RATE</div>
                <div class="metric-value">{sim_stats['win_rate']:.2f}%</div>
                <div class="metric-sub">
                    <b>{sim_stats['win']}</b>W / <b>{sim_stats['lose']}</b>L /
                    <b>{sim_stats['void']}</b>V / <b>{sim_stats['pending']}</b>P<br/>
                    Wilson 95% CI: [{ci_low:.1f}%, {ci_high:.1f}%]
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[4]:
        major_badge = (
            "⚠️ LOW SAMPLE SIZE"
            if major_stats["settled_matches"] < MIN_SAMPLE_SIZE_RELIABLE
            else "✅ SAMPLE OK"
        )
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">CARD 5 – MAJOR PERFORMANCE</div>
                <div class="metric-value">{major_stats['win_rate']:.2f}% WR</div>
                <div class="metric-sub">
                    Profit (Sim): <b>{format_idr(major_stats['simulated_profit'])}</b> | ROI: <b>{major_stats['simulated_roi']:.2f}%</b><br/>
                    Sampel: <b>{major_stats['settled_matches']}</b> settled ({major_badge})
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    # =================================================================
    # 3. PEMISAHAN STATISTIK SIMULASI VS ACTUAL ODDS & KUALITAS STRATEGI (Bagian C.4, H, I)
    # =================================================================
    with st.expander("📊 Detail Statistik Kuantitatif, Break-Even, EV, & Klasifikasi Liga (Major / Minor / Unknown)", expanded=True):
        tab_sim, tab_act, tab_tier = st.tabs([
            "A. SIMULATED PERFORMANCE (Odds 1.80)",
            "B. ACTUAL ODDS PERFORMANCE",
            "C. Klasifikasi Liga (MAJOR / MINOR / UNKNOWN)",
        ])

        with tab_sim:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Break-Even Win Rate", f"{sim_stats['break_even_win_rate']:.2f}%" if sim_stats["break_even_win_rate"] else "N/A")
            c2.metric("Expected Value (EV / Match)", format_idr(int(sim_stats["expected_value_per_match"])) if sim_stats["expected_value_per_match"] is not None else "N/A")
            c3.metric("Maximum Drawdown", format_idr(sim_stats["max_drawdown"]))
            c4.metric("Profit Factor", f"{sim_stats['profit_factor']}" if sim_stats["profit_factor"] != float("inf") else "∞")

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Longest Winning Streak", f"{sim_stats['longest_winning_streak']} Match")
            c6.metric("Longest Losing Streak", f"{sim_stats['longest_losing_streak']} Match")
            c7.metric("Wilson 95% CI", f"{sim_stats['wilson_ci_95'][0]:.2f}% – {sim_stats['wilson_ci_95'][1]:.2f}%")
            c8.metric("Status Ukuran Sampel", sim_stats["sample_size_warning"])

        with tab_act:
            if not act_stats["available"]:
                st.warning("ACTUAL ODDS: NOT AVAILABLE — Belum ada kandidat pertandingan yang memiliki data odds aktual dari provider saat entry.")
            else:
                a1, a2, a3, a4 = st.columns(4)
                a1.metric("Settled Matches (Actual Odds)", act_stats["settled_matches"])
                a2.metric("Average Entry Odds", f"{act_stats['average_odds']:.3f}" if act_stats["average_odds"] else "N/A")
                a3.metric("Break-Even WR (Actual)", f"{act_stats['break_even_win_rate']:.2f}%" if act_stats["break_even_win_rate"] else "N/A")
                a4.metric("Actual Net Profit", format_idr(act_stats["net_profit"]))

        with tab_tier:
            tier_rows = []
            for tier_key in ("MAJOR", "MINOR", "UNKNOWN"):
                t_info = stats["by_league_tier"][tier_key]
                tier_rows.append({
                    "Kategori Liga": tier_key,
                    "Total Match": t_info["total_matches"],
                    "Settled": t_info["settled_matches"],
                    "WIN": t_info["win"],
                    "LOSE": t_info["lose"],
                    "VOID": t_info["void"],
                    "PENDING": t_info["pending"],
                    "Win Rate (%)": f"{t_info['win_rate']:.2f}%",
                    "Profit Simulasi": format_idr(t_info["simulated_profit"]),
                    "ROI Simulasi (%)": f"{t_info['simulated_roi']:.2f}%",
                    "Profit Aktual": format_idr(t_info["actual_profit"]) if t_info["actual_available"] else "NOT AVAILABLE",
                    "Validitas Sampel": t_info["sample_status"],
                })
            st.dataframe(pd.DataFrame(tier_rows), use_container_width=True, hide_index=True)

    # =================================================================
    # 4. GRAFIK VISUALISASI PLOTLY (Bagian L.3)
    # =================================================================
    st.subheader("📈 Visualisasi Performa & Distribusi")
    if len(all_records) == 0:
        st.info("NO LIVE MATCH FOUND / BELUM ADA DATA HISTORIS — Grafik akan ditampilkan otomatis setelah terdapat data pertandingan yang tercatat.")
    else:
        g_col1, g_col2, g_col3 = st.columns(3)

        # Chart 1: Donut WIN/LOSE/VOID/PENDING
        with g_col1:
            status_counts = {
                "WIN": sim_stats["win"],
                "LOSE": sim_stats["lose"],
                "VOID": sim_stats["void"],
                "PENDING": sim_stats["pending"],
                "REVIEW": sim_stats["unverified"],
            }
            non_zero_status = {k: v for k, v in status_counts.items() if v > 0}
            if non_zero_status:
                fig_donut = px.pie(
                    names=list(non_zero_status.keys()),
                    values=list(non_zero_status.values()),
                    hole=0.55,
                    title="Distribusi Status Pertandingan",
                    color=list(non_zero_status.keys()),
                    color_discrete_map={
                        "WIN": "#16a34a",
                        "LOSE": "#dc2626",
                        "VOID": "#64748b",
                        "PENDING": "#ca8a04",
                        "REVIEW": "#ea580c",
                    },
                )
                st.plotly_chart(fig_donut, use_container_width=True)
            else:
                st.caption("Data belum cukup untuk grafik distribusi status.")

        # Chart 2 & 3: Grafik Profit Harian & Cumulative Profit
        day_summaries = list(reversed(stats["by_trading_day"]))
        settled_days = [d for d in day_summaries if d["settled_matches"] > 0]

        with g_col2:
            if settled_days:
                df_days = pd.DataFrame(settled_days)
                fig_daily = px.bar(
                    df_days,
                    x="trading_day",
                    y="simulated_profit",
                    title="Grafik Profit Harian (Simulasi IDR)",
                    labels={"trading_day": "Trading Day (Cut-off 12:00 WITA)", "simulated_profit": "Net Profit (IDR)"},
                    color="simulated_profit",
                    color_continuous_scale=["#dc2626", "#16a34a"],
                )
                st.plotly_chart(fig_daily, use_container_width=True)
            else:
                st.caption("Belum ada pertandingan settled untuk grafik profit harian.")

        with g_col3:
            if settled_days:
                df_days = pd.DataFrame(settled_days)
                df_days["cumulative_profit"] = df_days["simulated_profit"].cumsum()
                fig_cum = px.line(
                    df_days,
                    x="trading_day",
                    y="cumulative_profit",
                    markers=True,
                    title="Grafik Cumulative Profit (Simulasi IDR)",
                    labels={"trading_day": "Trading Day", "cumulative_profit": "Cumulative Profit (IDR)"},
                )
                st.plotly_chart(fig_cum, use_container_width=True)
            else:
                st.caption("Belum ada pertandingan settled untuk grafik cumulative profit.")

        g_col4, g_col5, g_col6 = st.columns(3)

        # Chart 4: Performa Major vs Minor vs Unknown
        with g_col4:
            tier_list = [
                stats["by_league_tier"]["MAJOR"],
                stats["by_league_tier"]["MINOR"],
                stats["by_league_tier"]["UNKNOWN"],
            ]
            active_tiers = [t for t in tier_list if t["total_matches"] > 0]
            if active_tiers:
                df_tier = pd.DataFrame(active_tiers)
                fig_tier = px.bar(
                    df_tier,
                    x="tier",
                    y=["win", "lose"],
                    barmode="group",
                    title="Performa Major vs Minor vs Unknown",
                    labels={"tier": "Klasifikasi Liga", "value": "Jumlah Pertandingan"},
                )
                st.plotly_chart(fig_tier, use_container_width=True)
            else:
                st.caption("Data belum cukup untuk grafik Major vs Minor.")

        # Chart 5: Win Rate Berdasarkan Odds Aktual
        with g_col5:
            actual_settled = [
                r for r in all_records
                if r.get("odds_entry") is not None and r.get("result") in ("WIN", "LOSE")
            ]
            if len(actual_settled) >= 2:
                df_odds = pd.DataFrame(actual_settled)
                df_odds["is_win"] = (df_odds["result"] == "WIN").astype(int) * 100.0
                fig_odds = px.histogram(
                    df_odds,
                    x="odds_entry",
                    y="is_win",
                    histfunc="avg",
                    nbins=8,
                    title="Win Rate (%) Berdasarkan Odds Aktual",
                    labels={"odds_entry": "Odds Entry", "is_win": "Win Rate (%)"},
                )
                st.plotly_chart(fig_odds, use_container_width=True)
            else:
                st.caption("Data odds aktual belum cukup untuk grafik Win Rate berdasarkan odds.")

        # Chart 6: Distribusi Waktu Entry (Menit 60–66)
        with g_col6:
            entry_mins = [int(r["minute_detected"]) for r in all_records if r.get("minute_detected") is not None]
            if entry_mins:
                df_min = pd.DataFrame({"minute_detected": entry_mins})
                fig_min = px.histogram(
                    df_min,
                    x="minute_detected",
                    nbins=7,
                    title="Distribusi Menit Entry (60'–66')",
                    labels={"minute_detected": "Menit Deteksi Entry"},
                )
                fig_min.update_layout(bargap=0.2)
                st.plotly_chart(fig_min, use_container_width=True)
            else:
                st.caption("Data belum cukup untuk grafik distribusi menit entry.")

    # =================================================================
    # 5. RINGKASAN TRADING DAY (Bagian L.4)
    # =================================================================
    st.subheader("🗓️ Ringkasan Partisi Harian (Cut-Off 12:00 WITA)")
    if not stats["by_trading_day"]:
        st.caption("Belum ada riwayat trading day di database.")
    else:
        df_td = pd.DataFrame([
            {
                "Trading Day": d["trading_day"],
                "Rekor (W-L)": d["summary_text"],
                "Total Match": d["total_matches"],
                "Settled": d["settled_matches"],
                "VOID": d["void"],
                "PENDING": d["pending"],
                "Win Rate": f"{d['win_rate']:.2f}%",
                "Net Profit (Simulasi)": format_idr(d["simulated_profit"]),
                "ROI (Simulasi)": f"{d['simulated_roi']:.2f}%",
                "Net Profit (Aktual)": format_idr(d["actual_profit"]) if d["actual_profit"] is not None else "NOT AVAILABLE",
            }
            for d in stats["by_trading_day"]
        ])
        st.dataframe(df_td, use_container_width=True, hide_index=True)

    # =================================================================
    # 6. TABEL PERTANDINGAN & FILTER (Bagian L.5)
    # =================================================================
    st.subheader("📋 Daftar Pertandingan (20 Terbaru Sesuai Filter)")

    f_col1, f_col2 = st.columns([2, 1])
    with f_col1:
        status_filter = st.selectbox(
            "Filter Kategori / Status:",
            options=["Semua", "LIVE", "WIN", "LOSE", "PENDING", "VOID", "REVIEW", "MAJOR", "MINOR"],
            index=0,
        )
    with f_col2:
        available_days = ["Semua"] + [d["trading_day"] for d in stats["by_trading_day"]]
        day_filter = st.selectbox("Filter Trading Day:", options=available_days, index=0)

    filtered_records: List[Dict[str, Any]] = []
    for rec in all_records:
        if day_filter != "Semua" and rec.get("trading_day") != day_filter:
            continue

        res = str(rec.get("result") or "PENDING").upper()
        m_status = str(rec.get("match_status") or "").upper()
        s_status = str(rec.get("settlement_status") or "PENDING").upper()
        l_cat = str(rec.get("league_category") or ("MAJOR" if rec.get("is_major") else "UNKNOWN")).upper()

        if status_filter == "LIVE" and m_status not in ("FIRST HALF", "SECOND HALF", "HALFTIME", "LIVE", "EXTRA TIME", "PENALTIES"):
            continue
        elif status_filter == "WIN" and res != "WIN":
            continue
        elif status_filter == "LOSE" and res != "LOSE":
            continue
        elif status_filter == "PENDING" and res != "PENDING":
            continue
        elif status_filter == "VOID" and res != "VOID":
            continue
        elif status_filter == "REVIEW" and (s_status != "REVIEW" and res != "DATA UNVERIFIED"):
            continue
        elif status_filter == "MAJOR" and l_cat != "MAJOR":
            continue
        elif status_filter == "MINOR" and l_cat != "MINOR":
            continue

        filtered_records.append(rec)

    top_20 = filtered_records[:20]

    if not top_20:
        st.warning("NO LIVE MATCH FOUND — Tidak ada pertandingan yang cocok dengan filter saat ini.")
    else:
        table_rows = []
        for idx, rec in enumerate(top_20, start=1):
            res = str(rec.get("result") or "PENDING").upper()
            m_status = str(rec.get("match_status") or "")
            is_live_now = m_status in ("First Half", "Second Half", "Halftime", "Live", "Extra Time", "Penalties") and res == "PENDING"
            display_status = "LIVE" if is_live_now else (
                "REVIEW" if rec.get("settlement_status") == "REVIEW" else res
            )

            badge_tier = "MAJOR" if rec.get("is_major") else str(rec.get("league_category") or "UNKNOWN")
            odds_disp = f"{rec['odds_entry']:.2f} (Actual)" if rec.get("odds_entry") is not None else f"{SIMULATED_ODDS:.2f} (Sim)"
            pnl_val = rec.get("actual_profit") if rec.get("odds_entry") is not None else rec.get("simulated_profit", 0)

            table_rows.append({
                "No": idx,
                "Match ID": rec.get("match_id"),
                "Match": f"{rec.get('home_team')} vs {rec.get('away_team')}",
                "League": rec.get("league"),
                "Badge": badge_tier,
                "Minute Entry": f"{rec.get('minute_detected')}'",
                "Entry Score": rec.get("score_at_entry"),
                "Entry Odds": odds_disp,
                "Current Score": rec.get("current_score"),
                "Final Score": rec.get("final_score") or "-",
                "Result": display_status,
                "Profit": format_idr(int(pnl_val or 0)) if res in ("WIN", "LOSE", "VOID") else "Rp0 (Pending)",
                "Trading Day": rec.get("trading_day"),
                "Verification": rec.get("verification_status"),
            })

        df_table = pd.DataFrame(table_rows)

        def style_result_col(val: str) -> str:
            colors = {
                "WIN": "background-color: #16a34a; color: white; font-weight: bold;",
                "LOSE": "background-color: #dc2626; color: white; font-weight: bold;",
                "LIVE": "background-color: #2563eb; color: white; font-weight: bold;",
                "PENDING": "background-color: #ca8a04; color: white; font-weight: bold;",
                "VOID": "background-color: #64748b; color: white; font-weight: bold;",
                "REVIEW": "background-color: #ea580c; color: white; font-weight: bold;",
                "DATA UNVERIFIED": "background-color: #ea580c; color: white; font-weight: bold;",
            }
            return colors.get(str(val).upper(), "")

        st.dataframe(
            df_table.style.map(style_result_col, subset=["Result"]),
            use_container_width=True,
            hide_index=True,
        )

        # =================================================================
        # 7. PANEL AUDIT DETAIL PERTANDINGAN (Bagian L.6)
        # =================================================================
        st.subheader("🔍 Audit Trail & Penjelasan Hasil Pertandingan")
        match_options = {
            f"[{r.get('trading_day')}] {r.get('home_team')} vs {r.get('away_team')} (ID: {r.get('match_id')})": r
            for r in top_20
        }
        selected_label = st.selectbox("Pilih Pertandingan untuk Audit Mendalam:", options=list(match_options.keys()))
        if selected_label:
            sel_rec = match_options[selected_label]
            audit_info = audit_result(sel_rec)

            st.markdown(f"**Penjelasan Audit Otomatis:** {audit_info['explanation']}")
            if not audit_info["audit_passed"]:
                st.error(f"Temuan Audit: {', '.join(audit_info['issues'])}")

            a_col1, a_col2, a_col3 = st.columns(3)
            with a_col1:
                st.markdown("**1. Identitas & Waktu Entry**")
                st.write(f"- **Match ID:** `{sel_rec.get('match_id')}`")
                st.write(f"- **League Slug:** `{sel_rec.get('league_slug')}` ({sel_rec.get('league_category')})")
                st.write(f"- **Kickoff (WITA):** `{sel_rec.get('kickoff_wita')}`")
                st.write(f"- **Waktu Deteksi / Entry (UTC):** `{sel_rec.get('detected_at_utc')}`")
                st.write(f"- **Waktu Deteksi / Entry (WITA):** `{sel_rec.get('detected_at_wita')}`")
                st.write(f"- **Trading Day:** `{sel_rec.get('trading_day')}`")
            with a_col2:
                st.markdown("**2. Parameter Entry & Settlement**")
                st.write(f"- **Menit Entry:** `{sel_rec.get('minute_detected')}'`")
                st.write(f"- **Skor Entry:** `{sel_rec.get('score_at_entry')}`")
                st.write(f"- **Odds Entry Aktual:** `{sel_rec.get('odds_entry') or 'NOT AVAILABLE'}`")
                st.write(f"- **Sumber Odds:** `{sel_rec.get('odds_source')}`")
                st.write(f"- **Status Pertandingan:** `{sel_rec.get('match_status')}`")
                st.write(f"- **Status Settlement:** `{sel_rec.get('settlement_status')}` (`{sel_rec.get('result')}`)")
            with a_col3:
                st.markdown("**3. Perhitungan Profit & Verifikasi**")
                st.write(f"- **Stake:** `{format_idr(int(sel_rec.get('stake') or DEFAULT_STAKE))}`")
                st.write(f"- **Profit Simulasi (1.80):** `{format_idr(int(sel_rec.get('simulated_profit') or 0))}`")
                act_p = sel_rec.get("actual_profit")
                st.write(f"- **Profit Aktual:** `{format_idr(int(act_p)) if act_p is not None else 'NOT AVAILABLE'}`")
                st.write(f"- **Sumber Data:** `{sel_rec.get('source')}`")
                st.write(f"- **Status Verifikasi:** `{sel_rec.get('verification_status')}`")
                st.write(f"- **Terakhir Diverifikasi:** `{sel_rec.get('last_verified_at')}`")

            s_col1, s_col2 = st.columns(2)
            with s_col1:
                st.markdown("**Riwayat Snapshot Skor Berkala:**")
                snaps = sel_rec.get("snapshots") or []
                if snaps:
                    st.dataframe(pd.DataFrame(snaps), use_container_width=True, hide_index=True)
                else:
                    st.caption("Tidak ada snapshot.")

            with s_col2:
                st.markdown("**Bukti Event Gol / Perubahan Skor:**")
                g_events = sel_rec.get("goal_events") or []
                if g_events:
                    st.dataframe(pd.DataFrame(g_events), use_container_width=True, hide_index=True)
                else:
                    st.caption("Belum ada event gol tercatat.")

            revs = sel_rec.get("revision_history") or []
            if revs:
                st.markdown("**Riwayat Perubahan / Koreksi Resmi Provider (Revision History):**")
                st.dataframe(pd.DataFrame(revs), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    render_dashboard()