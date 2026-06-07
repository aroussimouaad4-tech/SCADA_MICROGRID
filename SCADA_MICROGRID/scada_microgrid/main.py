"""SCADA Microgrid dashboard."""

from __future__ import annotations

import logging
import time

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from alarms import AlarmManager
from analytics import compute_energy_kpi, detect_solar_drift, predict_battery
from config import Config
from historian import Historian
from UDP import CommProtocol, LinkStatus, PLC, PLCMode
from synoptic import draw_synoptic

logger = logging.getLogger(__name__)


st.set_page_config(
    page_title="SCADA Microgrid ER",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
      :root {
        --bg-0: #061017;
        --bg-1: #0b1820;
        --bg-2: #11232c;
        --surface-0: rgba(10, 20, 28, 0.9);
        --surface-1: rgba(13, 26, 34, 0.96);
        --surface-2: rgba(17, 34, 44, 0.9);
        --stroke-soft: rgba(126, 158, 149, 0.18);
        --stroke-strong: rgba(141, 177, 163, 0.34);
        --text-main: #f5fbf7;
        --text-soft: #a5c0b7;
        --text-faint: #7d9a92;
        --accent-green: #5ae0a2;
        --accent-gold: #f6c15a;
        --accent-blue: #6cc8ff;
        --accent-red: #ff7f79;
      }
      .block-container {
        padding-top: 2.4rem;
        padding-bottom: 3rem;
        max-width: 1440px;
      }
      .stButton {
        margin-top: 0.25rem;
        margin-bottom: 0.35rem;
      }
      .stApp {
        background:
          radial-gradient(circle at 100% 0%, rgba(90, 224, 162, 0.15), transparent 26%),
          radial-gradient(circle at 0% 18%, rgba(246, 193, 90, 0.1), transparent 24%),
          radial-gradient(circle at 55% 100%, rgba(108, 200, 255, 0.11), transparent 25%),
          linear-gradient(180deg, var(--bg-0) 0%, #08131b 34%, #071019 100%);
        color: var(--text-main);
        font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      }
      .stSidebar {
        background:
          radial-gradient(circle at top, rgba(84, 210, 141, 0.08), transparent 28%),
          linear-gradient(180deg, #0c1718 0%, #0f1d1f 100%);
      }
      .stSidebar [data-testid="stSidebarUserContent"] {
        padding-top: 0.6rem;
      }
      .stSidebar div[data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(180deg, rgba(10, 20, 24, 0.92), rgba(8, 16, 20, 0.82));
        border: 1px solid rgba(101, 129, 118, 0.32);
        border-radius: 20px;
        padding: 0.15rem 0.35rem 0.45rem 0.35rem;
        margin-bottom: 0.9rem;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
      }
      .stSidebar [data-testid="stMarkdownContainer"] h2,
      .stSidebar [data-testid="stMarkdownContainer"] h3 {
        letter-spacing: 0.03em;
      }
      .stSidebar label,
      .stSidebar p,
      .stSidebar span,
      .stSidebar div {
        color: #e8f5ef;
      }
      .sidebar-title {
        color: #7fa196;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 0.72rem;
        margin-bottom: 6px;
      }
      .sidebar-heading {
        color: #f3faf6;
        font-size: 1.02rem;
        font-weight: 700;
        margin-bottom: 10px;
      }
      .sidebar-status {
        border-radius: 16px;
        background: linear-gradient(180deg, rgba(14, 31, 26, 0.95), rgba(8, 18, 22, 0.9));
        border: 1px solid rgba(84, 210, 141, 0.25);
        padding: 12px 13px;
        margin-bottom: 12px;
      }
      .sidebar-status .value {
        color: #f5fbf8;
        font-size: 1.1rem;
        font-weight: 700;
        margin-top: 4px;
      }
      .sidebar-status .sub {
        color: #91b1a6;
        font-size: 0.84rem;
        margin-top: 4px;
      }
      .stSidebar [data-baseweb="input"],
      .stSidebar [data-baseweb="select"],
      .stSidebar [data-baseweb="base-input"] {
        background: rgba(8, 18, 24, 0.92) !important;
        border-radius: 14px !important;
        border: 1px solid rgba(101, 129, 118, 0.36) !important;
      }
      .stSidebar .stSlider,
      .stSidebar .stRadio,
      .stSidebar .stCheckbox,
      .stSidebar .stNumberInput,
      .stSidebar .stTextInput {
        padding-top: 0.15rem;
        padding-bottom: 0.25rem;
      }
      .scan-action {
        margin-top: 1rem;
        padding-top: 0.85rem;
        border-top: 1px solid rgba(101, 129, 118, 0.22);
      }
      .stSidebar details {
        background: rgba(7, 16, 21, 0.72);
        border: 1px solid rgba(101, 129, 118, 0.24);
        border-radius: 16px;
        padding: 4px 8px;
      }
      .stSidebar hr {
        margin: 0.7rem 0 0.95rem 0;
        border-color: rgba(101, 129, 118, 0.2);
      }
      [data-testid="stHeadingWithActionElements"] h1,
      [data-testid="stHeadingWithActionElements"] h2,
      [data-testid="stHeadingWithActionElements"] h3,
      .hero h1,
      .section-heading {
        font-family: Georgia, "Times New Roman", serif;
      }
      [data-testid="stMetric"] {
        background:
          linear-gradient(180deg, rgba(13, 26, 34, 0.94), rgba(8, 17, 24, 0.82));
        border: 1px solid rgba(102, 132, 121, 0.32);
        border-radius: 22px;
        padding: 12px 14px 10px 14px;
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.04),
          0 18px 34px rgba(0, 0, 0, 0.14);
        min-height: 132px;
      }
      [data-testid="stMetricValue"] {
        color: var(--text-main);
      }
      div[data-testid="metric-container"] label {
        color: #8fb4aa !important;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-size: 0.74rem !important;
      }
      .panel {
        position: relative;
        overflow: hidden;
        background:
          radial-gradient(circle at top right, rgba(90, 224, 162, 0.08), transparent 26%),
          linear-gradient(180deg, rgba(12, 24, 32, 0.95), rgba(7, 17, 24, 0.94));
        border: 1px solid rgba(104, 136, 124, 0.28);
        border-radius: 26px;
        padding: 22px 22px 20px 22px;
        margin-bottom: 18px;
        box-shadow: 0 24px 46px rgba(0, 0, 0, 0.2);
      }
      .panel::before {
        content: "";
        position: absolute;
        inset: 0 auto auto 0;
        width: 180px;
        height: 3px;
        background: linear-gradient(90deg, var(--accent-green), rgba(244, 183, 74, 0.2));
      }
      .hero {
        position: relative;
        overflow: hidden;
        padding: 26px 28px;
        border-radius: 32px;
        border: 1px solid rgba(122, 160, 120, 0.2);
        background:
          radial-gradient(circle at top right, rgba(84, 210, 141, 0.24), transparent 28%),
          radial-gradient(circle at 20% 20%, rgba(244, 183, 74, 0.15), transparent 22%),
          linear-gradient(135deg, rgba(12, 42, 36, 0.98), rgba(8, 20, 32, 0.98));
        box-shadow: 0 30px 60px rgba(0, 0, 0, 0.22);
        margin-bottom: 16px;
      }
      .hero::after {
        content: "";
        position: absolute;
        right: -60px;
        top: -50px;
        width: 220px;
        height: 220px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255,255,255,0.08), transparent 68%);
      }
      .hero-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.7fr) minmax(260px, 0.9fr);
        gap: 20px;
        align-items: stretch;
      }
      .hero-topline {
        color: #90b2a7;
        text-transform: uppercase;
        letter-spacing: 0.22em;
        font-size: 0.72rem;
        margin-bottom: 10px;
      }
      .hero h1 {
        margin: 0;
        color: #f3faf5;
        font-size: 2.35rem;
        line-height: 1.08;
        letter-spacing: 0.01em;
        max-width: 18ch;
      }
      .hero p {
        margin: 10px 0 0 0;
        color: #9dc0b6;
        max-width: 58ch;
      }
      .hero-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 16px;
      }
      .hero-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-radius: 999px;
        background: rgba(8, 19, 26, 0.54);
        border: 1px solid rgba(137, 170, 157, 0.24);
        color: var(--text-main);
        font-size: 0.86rem;
      }
      .hero-pill .dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: var(--accent-green);
        box-shadow: 0 0 18px rgba(90, 224, 162, 0.55);
      }
      .hero-aside {
        position: relative;
        border-radius: 24px;
        padding: 18px;
        background: linear-gradient(180deg, rgba(7, 18, 25, 0.62), rgba(6, 15, 21, 0.5));
        border: 1px solid rgba(132, 167, 154, 0.18);
        backdrop-filter: blur(8px);
      }
      .hero-aside-label {
        color: var(--text-soft);
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 0.72rem;
      }
      .hero-aside-value {
        color: var(--text-main);
        font-size: 2rem;
        line-height: 1;
        font-weight: 800;
        margin-top: 10px;
      }
      .hero-aside-sub {
        color: var(--text-soft);
        margin-top: 8px;
        font-size: 0.92rem;
      }
      .hero-mini-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin-top: 16px;
      }
      .hero-mini-card {
        border-radius: 18px;
        padding: 12px;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(140, 170, 159, 0.15);
      }
      .hero-mini-card .k {
        color: var(--text-faint);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
      }
      .hero-mini-card .v {
        color: var(--text-main);
        font-size: 1.02rem;
        font-weight: 700;
        margin-top: 6px;
      }
      .status-strip {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-top: 18px;
      }
      .status-card {
        background: linear-gradient(180deg, rgba(6, 16, 24, 0.84), rgba(6, 14, 20, 0.68));
        border: 1px solid rgba(95, 126, 114, 0.3);
        border-radius: 18px;
        padding: 14px 16px;
        backdrop-filter: blur(4px);
      }
      .status-card .label {
        color: #88a79e;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }
      .status-card .value {
        color: #f5fbf7;
        font-size: 1.25rem;
        font-weight: 700;
        margin-top: 6px;
      }
      .status-card .sub {
        color: #89a59d;
        font-size: 0.88rem;
        margin-top: 4px;
      }
      .signal-ribbon {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin: 16px 0 18px 0;
      }
      .signal-card {
        position: relative;
        overflow: hidden;
        border-radius: 20px;
        padding: 14px 16px;
        background: linear-gradient(180deg, rgba(10, 20, 28, 0.92), rgba(7, 16, 22, 0.76));
        border: 1px solid rgba(99, 128, 120, 0.24);
      }
      .signal-card::after {
        content: "";
        position: absolute;
        inset: auto -30px -40px auto;
        width: 110px;
        height: 110px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255,255,255,0.06), transparent 70%);
      }
      .signal-card .eyebrow {
        color: #87a99d;
        text-transform: uppercase;
        font-size: 0.74rem;
        letter-spacing: 0.18em;
      }
      .signal-card .big {
        color: #f7fcf9;
        margin-top: 8px;
        font-size: 1.35rem;
        font-weight: 700;
      }
      .signal-card .small {
        color: #88a79e;
        margin-top: 6px;
        font-size: 0.88rem;
      }
      .metric-band {
        margin: 10px 0 12px 0;
        padding: 12px 14px;
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(9, 18, 25, 0.92), rgba(7, 15, 22, 0.8));
        border: 1px solid rgba(98, 126, 118, 0.24);
      }
      .metric-band-title {
        color: #f3faf6;
        font-size: 1rem;
        font-weight: 700;
      }
      .metric-band-subtitle {
        color: #88a79e;
        font-size: 0.86rem;
        margin-top: 4px;
      }
      .section-header {
        margin-bottom: 14px;
        padding: 10px 14px 12px 14px;
        border-radius: 16px;
        background: linear-gradient(180deg, rgba(10, 22, 28, 0.88), rgba(7, 17, 24, 0.72));
        border: 1px solid rgba(100, 130, 119, 0.22);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
      }
      .section-header::after {
        content: "";
        display: block;
        width: 100%;
        height: 1px;
        margin-top: 10px;
        background: linear-gradient(90deg, rgba(84,210,141,0.65), rgba(87,183,255,0.14), transparent 82%);
      }
      .section-kicker {
        color: #8fb5a6;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 0.68rem;
        font-weight: 700;
        margin-bottom: 5px;
      }
      .section-heading {
        color: #f7fcf9;
        font-size: 1.3rem;
        font-weight: 800;
        line-height: 1.1;
        margin-bottom: 0;
      }
      .mqtt-badge {
        border-radius: 20px;
        padding: 14px 16px;
        font-family: Consolas, monospace;
        border: 1px solid rgba(130, 151, 143, 0.3);
        background: linear-gradient(180deg, rgba(8, 18, 25, 0.88), rgba(6, 15, 21, 0.74));
      }
      .mqtt-online { box-shadow: inset 0 0 0 1px rgba(63,185,80,0.25); }
      .mqtt-connected { box-shadow: inset 0 0 0 1px rgba(210,153,34,0.25); }
      .mqtt-offline { box-shadow: inset 0 0 0 1px rgba(255,123,114,0.25); }
      .mqtt-simulation { box-shadow: inset 0 0 0 1px rgba(139,148,158,0.2); }
      .alarm {
        border-radius: 14px;
        padding: 10px 12px;
        margin-bottom: 8px;
        border-left: 4px solid transparent;
        background: rgba(7, 16, 24, 0.78);
      }
      .alarm-critical { border-color: #ff6b6b; }
      .alarm-alarm { border-color: #ff9f43; }
      .alarm-warning { border-color: #ffd166; }
      .alarm-info { border-color: #4dabf7; }
      .kpi-list {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }
      .kpi-item {
        border-radius: 14px;
        background: rgba(5, 14, 22, 0.62);
        border: 1px solid rgba(98, 126, 118, 0.28);
        padding: 12px 14px;
      }
      .kpi-item .k {
        color: #90b2a7;
        font-size: 0.82rem;
      }
      .kpi-item .v {
        color: #f5fbf7;
        font-size: 1.05rem;
        font-weight: 700;
        margin-top: 4px;
      }
      .diag-item {
        border-radius: 16px;
        padding: 13px 14px;
        background: linear-gradient(180deg, rgba(7, 16, 24, 0.86), rgba(6, 14, 20, 0.68));
        border: 1px solid rgba(98, 126, 118, 0.2);
        margin-bottom: 12px;
      }
      .diag-item strong {
        color: #f4fbf7;
      }
      [data-testid="stPlotlyChart"] {
        margin-top: 0.2rem;
      }
      [data-testid="stPlotlyChart"] > div {
        border-radius: 20px;
        overflow: hidden;
        border: 1px solid rgba(104, 136, 124, 0.18);
        background: linear-gradient(180deg, rgba(7, 16, 23, 0.72), rgba(5, 12, 18, 0.62));
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.025);
      }
      [data-testid="stProgressBar"] > div > div {
        background: linear-gradient(90deg, var(--accent-green), var(--accent-blue)) !important;
      }
      [data-baseweb="tab-list"] {
        gap: 10px;
        margin-bottom: 0.55rem;
      }
      button[data-baseweb="tab"] {
        border-radius: 999px !important;
        min-height: 40px !important;
        background: linear-gradient(180deg, rgba(9, 18, 24, 0.86), rgba(7, 15, 20, 0.76)) !important;
        border: 1px solid rgba(93, 122, 111, 0.18) !important;
        color: #89aba1 !important;
        padding: 6px 14px !important;
        font-weight: 600 !important;
        transition: all 0.18s ease !important;
      }
      button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(180deg, rgba(24, 54, 41, 0.96), rgba(16, 42, 31, 0.96)) !important;
        color: #f7fcf9 !important;
        border-color: rgba(93, 201, 118, 0.42) !important;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(93, 201, 118, 0.08) !important;
      }
      button[data-baseweb="tab"]:hover {
        border-color: rgba(115, 150, 138, 0.34) !important;
        color: #cfe5dd !important;
      }
      .stButton > button {
        border-radius: 999px;
        border: 1px solid rgba(93, 201, 118, 0.55);
        background: linear-gradient(180deg, #183f2a, #123222);
        color: #edf6f3;
        font-weight: 600;
      }
      .stButton > button:hover {
        border-color: rgba(112, 222, 137, 0.8);
        color: #ffffff;
      }
      @media (max-width: 1100px) {
        .hero-grid {
          grid-template-columns: 1fr;
        }
        .status-strip, .kpi-list, .signal-ribbon {
          grid-template-columns: 1fr 1fr;
        }
      }
      @media (max-width: 700px) {
        .status-strip, .kpi-list, .signal-ribbon {
          grid-template-columns: 1fr;
        }
        .hero {
          padding: 22px 20px;
        }
        .hero h1 {
          font-size: 1.9rem;
        }
        .hero-mini-grid {
          grid-template-columns: 1fr;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


if "plc_mode" not in st.session_state:
    st.session_state.plc_mode = "STOP"
if "ems_mode" not in st.session_state:
    st.session_state.ems_mode = "AUTO"
if "puissance_batt_manuelle" not in st.session_state:
    st.session_state.puissance_batt_manuelle = 0.0
if "historian" not in st.session_state:
    st.session_state.historian = Historian()
if "alarm_manager" not in st.session_state:
    st.session_state.alarm_manager = AlarmManager()
if "udp_local_host_input" not in st.session_state:
    st.session_state.udp_local_host_input = Config.udp.LOCAL_HOST
if "udp_local_port_input" not in st.session_state:
    st.session_state.udp_local_port_input = Config.udp.LOCAL_PORT
if "udp_local_host" not in st.session_state:
    st.session_state.udp_local_host = Config.udp.LOCAL_HOST
if "udp_local_port" not in st.session_state:
    st.session_state.udp_local_port = Config.udp.LOCAL_PORT
if "udp_auto_refresh" not in st.session_state:
    st.session_state.udp_auto_refresh = True
if "pv_cut" not in st.session_state:
    st.session_state.pv_cut = False

# Create PLC instance with persistent historian and alarm manager
if "plc" not in st.session_state:
    st.session_state.plc = PLC()
    st.session_state.plc.hist = st.session_state.historian
    st.session_state.plc.alarm = st.session_state.alarm_manager
plc = st.session_state.plc

# Initialize with session state values, but allow local changes to override
plc.mode_ems = st.session_state.ems_mode
plc.puissance_batt_manuelle = st.session_state.puissance_batt_manuelle
plc.mode = st.session_state.plc_mode
if not hasattr(plc, "pv_cut"):
    plc.pv_cut = False
plc.set_pv_cut(st.session_state.pv_cut)

# Apply persistent UDP configuration only when the current bridge differs from the desired config
if (plc.bridge.local_host != st.session_state.udp_local_host or
        plc.bridge.local_port != st.session_state.udp_local_port):
    try:
        logger.info(f"Applying persistent UDP config: {st.session_state.udp_local_host}:{st.session_state.udp_local_port}")
        plc.bridge.reconfigure(st.session_state.udp_local_host, st.session_state.udp_local_port)
        logger.info("UDP reconfiguration applied successfully")
    except Exception as e:
        logger.warning(f"Failed to apply persistent UDP config: {e}")


_LINK_META = {
    LinkStatus.ONLINE: ("●", "mqtt-online", "Simulink online"),
    LinkStatus.LISTENING: ("◐", "mqtt-connected", "Listening for UDP data"),
    LinkStatus.DISCONNECTED: ("●", "mqtt-offline", "UDP link offline"),
    LinkStatus.SIMULATION: ("○", "mqtt-simulation", "Simulation mode"),
}


def render_link_badge(status: str) -> None:
    icon, css, label = _LINK_META.get(status, ("○", "mqtt-simulation", status))
    endpoint_info = getattr(plc.bridge, "display_endpoint", "No endpoint")
    age = plc.bridge.last_rx_age_s
    age_text = f"Last packet: {age}s" if age is not None else "No packet received"
    st.markdown(
        f"""
        <div class="mqtt-badge {css}">
          <div><strong>{icon} {label}</strong></div>
          <div style="margin-top:6px; color:#9cb5ad;">{endpoint_info}</div>
          <div style="margin-top:4px; color:#7f9a92;">{age_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_delta(value: float) -> str:
    return "Import" if value > 0 else "Export"


def get_trend_chart_config() -> dict:
    return {
        "displaylogo": False,
        "displayModeBar": "hover",
        "modeBarButtonsToRemove": [
            "lasso2d",
            "select2d",
            "autoScale2d",
            "toggleSpikelines",
        ],
    }


def apply_trend_chart_theme(
    fig: go.Figure,
    *,
    height: int,
    yaxis_title: str | None = None,
    legend: bool = True,
    hovermode: str = "x unified",
    top_margin: int = 34,
) -> None:
    fig.update_layout(
        template=None,
        height=height,
        margin=dict(t=top_margin, b=20, l=18, r=18),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(7,16,23,0.9)",
        hovermode=hovermode,
        hoverdistance=40,
        bargap=0.28,
        font=dict(color="#eaf4ef", family='"Segoe UI", "Trebuchet MS", sans-serif'),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.0,
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(size=12, color="#d7e7e1"),
            itemwidth=42,
        ),
        hoverlabel=dict(
            bgcolor="rgba(8,18,24,0.96)",
            bordercolor="rgba(125,151,141,0.45)",
            font=dict(color="#f4fbf7", size=12),
        ),
        modebar=dict(bgcolor="rgba(7,16,23,0.22)", color="#8fb5a6", activecolor="#eaf4ef"),
        showlegend=legend,
    )
    fig.update_xaxes(
        showgrid=False,
        showline=True,
        linecolor="rgba(122, 150, 139, 0.35)",
        linewidth=1,
        tickfont=dict(color="#bdd2ca", size=11),
        title_font=dict(color="#cfe0d9", size=12),
        tickformat="%H:%M:%S\n%b %d",
        ticks="outside",
        tickcolor="rgba(122, 150, 139, 0.30)",
        ticklen=6,
        automargin=True,
        zeroline=False,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(120, 145, 137, 0.18)",
        gridwidth=1,
        showline=True,
        linecolor="rgba(122, 150, 139, 0.24)",
        linewidth=1,
        zeroline=True,
        zerolinecolor="rgba(211, 227, 220, 0.34)",
        zerolinewidth=1,
        tickfont=dict(color="#bdd2ca", size=11),
        title_font=dict(color="#cfe0d9", size=12),
        ticks="outside",
        tickcolor="rgba(122, 150, 139, 0.28)",
        ticklen=6,
        automargin=True,
    )
    if yaxis_title:
        fig.update_yaxes(title_text=yaxis_title)
    fig.update_annotations(font=dict(color="#dcebe5", size=12))


def add_threshold_line(
    fig: go.Figure,
    *,
    y: float,
    label: str | None = None,
    row: int | None = None,
    col: int | None = None,
    color: str = "rgba(255, 127, 121, 0.55)",
    dash: str = "dot",
) -> None:
    fig.add_hline(
        y=y,
        line_dash=dash,
        line_color=color,
        line_width=1.2,
        annotation_text=label,
        annotation_position="top left",
        annotation_font_color="#a9c1b8",
        annotation_font_size=11,
        row=row,
        col=col,
    )


def render_section_header(kicker: str, title: str) -> None:
    st.markdown(
        f"""
        <div class="section-header">
          <div class="section-kicker">{kicker}</div>
          <div class="section-heading">{title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_band(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="metric-band">
          <div class="metric-band-title">{title}</div>
          <div class="metric-band-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_header(kicker: str, title: str) -> None:
    st.markdown(
        f"""
        <div class="sidebar-title">{kicker}</div>
        <div class="sidebar-heading">{title}</div>
        """,
        unsafe_allow_html=True,
    )


with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-status">
          <div class="sidebar-title">Console</div>
          <div class="value">{plc.get_tag("SOURCE_DONNEES")}</div>
          <div class="sub">EMS: {st.session_state.ems_mode} | Historian: {plc.hist.count():,} records</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        render_sidebar_header("Controls", "Operator controls")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Start", width="stretch", key="start_btn"):
                st.session_state.plc_mode = PLCMode.RUN
                plc.mode = PLCMode.RUN
        with col_b:
            if st.button("Stop", width="stretch", key="stop_btn"):
                st.session_state.plc_mode = PLCMode.STOP
                plc.mode = PLCMode.STOP

        ems_mode = st.radio(
            "Control mode",
            ["AUTO", "MANUAL"],
            index=0 if st.session_state.ems_mode == "AUTO" else 1,
            key="ems_mode_radio",
        )
        st.session_state.ems_mode = ems_mode
        plc.mode_ems = ems_mode

        if ems_mode == "MANUAL":
            p_batt_man = st.slider(
                "Battery power setpoint (W)",
                -int(Config.batterie.PUISSANCE_MAX_DECHARGE),
                int(Config.batterie.PUISSANCE_MAX_CHARGE),
                int(st.session_state.puissance_batt_manuelle),
                step=5,
            )
            if p_batt_man != st.session_state.puissance_batt_manuelle:
                st.session_state.puissance_batt_manuelle = float(p_batt_man)
            st.caption("Positive = charge, negative = discharge")

    with st.container(border=True):
        render_sidebar_header("Environment", "Weather")
        cloud = st.slider("Cloud cover (%)", 0, 100, 0, step=5)
        plc.set_tag("NUAGE_FACTOR", 1.0 - cloud / 100.0)
        st.caption(f"Irradiance factor: {1.0 - cloud / 100.0:.2f}")

    with st.container(border=True):
        render_sidebar_header("Connectivity", "UDP link")
        render_link_badge(plc.bridge.connection_status)

        with st.expander("Connection settings", expanded=False):
            udp_local_host = st.text_input(
                "Local bind address",
                value=st.session_state.udp_local_host_input,
                placeholder="0.0.0.0",
                key="udp_local_host_widget",
                help="Bind address for UDP receive. Use 0.0.0.0 to listen on all interfaces.",
            )
            udp_local_port = st.number_input(
                "Local UDP port",
                min_value=1,
                max_value=65535,
                value=st.session_state.udp_local_port_input,
                step=1,
                key="udp_local_port_widget",
            )

            apply_col, reset_col = st.columns(2)
            with apply_col:
                apply_clicked = st.button("Apply", width="stretch")
            with reset_col:
                reset_clicked = st.button("Default", width="stretch")

            if apply_clicked:
                try:
                    udp_local_host = str(udp_local_host).strip() or Config.udp.LOCAL_HOST
                    udp_local_port = int(udp_local_port)
                    if not (1 <= udp_local_port <= 65535):
                        raise ValueError("Port UDP invalide.")

                    st.session_state.udp_local_host = udp_local_host
                    st.session_state.udp_local_port = udp_local_port
                    st.session_state.udp_local_host_input = udp_local_host
                    st.session_state.udp_local_port_input = udp_local_port

                    status = plc.apply_udp_config(udp_local_host, udp_local_port)
                    st.success(f"UDP link updated: {udp_local_host}:{udp_local_port} ({status})")
                    logger.info(f"UDP status after apply: {plc.bridge.connection_status}, bound={plc.bridge._bound}, host={plc.bridge.local_host}, port={plc.bridge.local_port}")
                    if plc.bridge.connection_status == LinkStatus.DISCONNECTED:
                        st.error("UDP bind failed. Vérifiez l'adresse et le port.")
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Configuration failed: {exc}")

            if reset_clicked:
                try:
                    st.session_state.udp_local_host = Config.udp.LOCAL_HOST
                    st.session_state.udp_local_port = Config.udp.LOCAL_PORT
                    st.session_state.udp_local_host_input = Config.udp.LOCAL_HOST
                    st.session_state.udp_local_port_input = Config.udp.LOCAL_PORT

                    status = plc.apply_udp_config(Config.udp.LOCAL_HOST, Config.udp.LOCAL_PORT)
                    st.info(f"Reset to {Config.udp.LOCAL_HOST}:{Config.udp.LOCAL_PORT} ({status})")
                except Exception as exc:
                    st.error(f"Reset failed: {exc}")

            st.caption(
                "Incoming UDP payload from Simulink: JSON object with keys such as "
                "`P_PV`, `P_EOLIEN`, `P_CHARGE`, `P_BATTERIE`, `SOC`, `P_RESEAU`."
            )

    with st.container(border=True):
        render_sidebar_header("Safety", "Alarm handling")
        if plc.alarm.unacked_count > 0:
            if st.button(f"Acknowledge all ({plc.alarm.unacked_count})", width="stretch"):
                plc.alarm.ack_all()
        else:
            st.caption("No pending acknowledgements.")

    with st.container(border=True):
        render_sidebar_header("Execution", "Scan control")
        auto_refresh = st.checkbox("Auto refresh (1s)", value=st.session_state.udp_auto_refresh)
        st.session_state.udp_auto_refresh = auto_refresh
        nb_cycles = st.number_input("Scans per refresh", min_value=1, max_value=20, value=1)
        st.markdown('<div class="scan-action">', unsafe_allow_html=True)
        run_scan_clicked = st.button("Run scan", width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)

    with st.container(border=True):
        render_sidebar_header("Execution", "PowerPV control")
        pv_status = "COUPE" if st.session_state.pv_cut else "EN SERVICE"
        pv_status_color = "#ffb1ad" if st.session_state.pv_cut else "#8df0bd"
        st.markdown(
            f"""
            <div class="sidebar-status">
              <div class="sidebar-title">PV breaker</div>
              <div class="value" style="color:{pv_status_color};">{pv_status}</div>
              <div class="sub">Current PV power: {float(plc.get_tag("P_PV") or 0.0):.1f} W</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cut_col, decut_col = st.columns(2)
        with cut_col:
            if st.button("Couper PV", width="stretch", disabled=st.session_state.pv_cut, key="cut_pv_btn"):
                st.session_state.pv_cut = True
                plc.set_pv_cut(True)
                st.rerun()
        with decut_col:
            if st.button("Retablir PV", width="stretch", disabled=not st.session_state.pv_cut, key="decut_pv_btn"):
                st.session_state.pv_cut = False
                plc.set_pv_cut(False)
                st.rerun()
        st.caption("Couper force P_PV a 0 W; Retablir remet la production PV normale au prochain scan.")

        export_df = plc.hist.get_all()
        export_filename = f"scada_microgrid_data_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        st.download_button(
            "Download data",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name=export_filename,
            mime="text/csv",
            width="stretch",
            disabled=export_df.empty,
            key="download_historian_data_btn",
        )
        if export_df.empty:
            st.caption("Run a scan before downloading historian data.")
        else:
            st.caption(f"Download {len(export_df):,} historian records as CSV.")


if auto_refresh or run_scan_clicked:
    for _ in range(nb_cycles):
        plc.scan()


if st.session_state.plc_mode == "RUN" and plc.bridge.is_remote_online:
    plc.scan()


snap = plc.snapshot
link_status = plc.bridge.connection_status
source = plc.get_tag("SOURCE_DONNEES")
icon, _, link_label = _LINK_META.get(link_status, ("○", "", link_status))

st.markdown(
    f"""
    <div class="hero">
      <div class="hero-grid">
        <div>
          <div class="hero-topline">Operations cockpit</div>
          <h1>SCADA Microgrid Renewable Operations</h1>
          <p>Real-time supervision for solar, wind, storage and utility exchange with a calmer, more readable operator dashboard.</p>
          <div class="hero-pills">
            <div class="hero-pill"><span class="dot"></span> {icon} {link_label}</div>
            <div class="hero-pill">Source: {source}</div>
            <div class="hero-pill">Mode: {st.session_state.ems_mode}</div>
          </div>
        </div>
        <div class="hero-aside">
          <div class="hero-aside-label">Renewable availability</div>
          <div class="hero-aside-value">{snap['TAUX_ER']:.0f}%</div>
          <div class="hero-aside-sub">Current clean-energy contribution across the microgrid.</div>
          <div class="hero-mini-grid">
            <div class="hero-mini-card">
              <div class="k">Battery</div>
              <div class="v">{snap['SOC']:.0f}% SoC</div>
            </div>
            <div class="hero-mini-card">
              <div class="k">Grid flow</div>
              <div class="v">{metric_delta(snap['P_RESEAU'])}</div>
            </div>
            <div class="hero-mini-card">
              <div class="k">Scan time</div>
              <div class="v">{plc.last_scan_duration_ms:.1f} ms</div>
            </div>
            <div class="hero-mini-card">
              <div class="k">Records</div>
              <div class="v">{plc.hist.count():,}</div>
            </div>
          </div>
        </div>
      </div>
      <div class="status-strip">
        <div class="status-card">
          <div class="label">EMS strategy</div>
          <div class="value">{st.session_state.ems_mode}</div>
          <div class="sub">Battery dispatch configuration</div>
        </div>
        <div class="status-card">
          <div class="label">Data source</div>
          <div class="value">{source}</div>
          <div class="sub">{icon} {link_label}</div>
        </div>
        <div class="status-card">
          <div class="label">Scan health</div>
          <div class="value">{plc.last_scan_duration_ms:.1f} ms</div>
          <div class="sub">{plc.scan_count} scans executed</div>
        </div>
        <div class="status-card">
          <div class="label">Historian</div>
          <div class="value">{plc.hist.count():,}</div>
          <div class="sub">records stored</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="signal-ribbon">
      <div class="signal-card">
        <div class="eyebrow">Renewable share</div>
        <div class="big">{snap['TAUX_ER']:.0f}%</div>
        <div class="small">Instant contribution from PV and wind</div>
      </div>
      <div class="signal-card">
        <div class="eyebrow">Battery state</div>
        <div class="big">{snap['SOC']:.0f}%</div>
        <div class="small">{snap['ETAT_BATT']} at {snap['P_BATTERIE']:.1f} kW</div>
      </div>
      <div class="signal-card">
        <div class="eyebrow">Grid exchange</div>
        <div class="big">{metric_delta(snap['P_RESEAU'])}</div>
        <div class="small">{abs(snap['P_RESEAU']):.1f} W with utility network</div>
      </div>
      <div class="signal-card">
        <div class="eyebrow">Active alarms</div>
        <div class="big">{len(plc.alarm.active)}</div>
        <div class="small">{plc.alarm.unacked_count} awaiting acknowledgement</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

render_metric_band("Live measurements", "Core microgrid values from the current scan")
primary_metrics = st.columns(5)
primary_metrics[0].metric("PV power", f"{snap['P_PV']:.1f} W", f"{snap['IRRADIANCE']:.0f} W/m2")
primary_metrics[1].metric("Wind power", f"{snap['P_EOLIEN']:.1f} W", f"{snap['VITESSE_VENT']:.1f} m/s")
primary_metrics[2].metric("Battery", f"{snap['P_BATTERIE']:.1f} W", f"SoC {snap['SOC']:.0f}%")
primary_metrics[3].metric("Load", f"{snap['P_CHARGE']:.1f} W", f"RES share {snap['TAUX_ER']:.0f}%")
primary_metrics[4].metric("Grid", f"{snap['P_RESEAU']:.1f} W", metric_delta(snap["P_RESEAU"]))

render_metric_band("Session counters", "Accumulated energy and thermal indicators")
secondary_metrics = st.columns(5)
secondary_metrics[0].metric("PV energy", f"{snap['ENERGIE_PV']:.2f} Wh")
secondary_metrics[1].metric("Wind energy", f"{snap['ENERGIE_EOLIEN']:.2f} Wh")
secondary_metrics[2].metric("Imported", f"{snap['ENERGIE_IMPORTEE']:.2f} Wh")
secondary_metrics[3].metric("Exported", f"{snap['ENERGIE_EXPORTEE']:.2f} Wh")
secondary_metrics[4].metric("Battery temp", f"{snap['TEMP_BATTERIE']:.1f} deg C", str(snap["ETAT_BATT"]))

overview_col, status_col = st.columns([2.2, 1])
df = plc.hist.get_last_n(300)

with overview_col:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    render_section_header("Live topology", "Synoptic overview")
    svg = draw_synoptic(
        p_pv=snap["P_PV"],
        p_eolien=snap["P_EOLIEN"],
        soc=snap["SOC"],
        p_batterie=snap["P_BATTERIE"],
        p_charge=snap["P_CHARGE"],
        p_reseau=snap["P_RESEAU"],
        vitesse_vent=snap["VITESSE_VENT"],
        taux_er=snap["TAUX_ER"],
        mode=plc.mode,
        etat_batt=str(snap["ETAT_BATT"]),
    )
    st.markdown(svg, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    render_section_header("Generation split", "Session energy mix")
    if not df.empty and len(df) >= 5:
        e_pv = snap["ENERGIE_PV"]
        e_eol = snap["ENERGIE_EOLIEN"]
        e_imp = snap["ENERGIE_IMPORTEE"]
        e_exp = snap["ENERGIE_EXPORTEE"]
        labels = ["Solar PV", "Wind", "Grid import", "Grid export"]
        values = [e_pv, e_eol, e_imp, e_exp]
        colors = ["#f4b74a", "#57b7ff", "#ff7b72", "#55d88a"]

        if str(snap["ETAT_BATT"]).upper() == "DECHARGE":
            labels.append("Battery power")
            values.append(abs(snap["P_BATTERIE"]))
            colors.append("#b287ff")

        total = max(sum(values), 0.001)
        fig_pie = go.Figure(
            go.Pie(
                labels=labels,
                values=values,
                hole=0.58,
                marker_colors=colors,
                textinfo="label+percent",
            )
        )
        fig_pie.update_layout(
            template="plotly_dark",
            height=360,
            margin=dict(t=20, b=20, l=20, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            annotations=[
                {
                    "text": f"{(e_pv + e_eol) / total * 100:.0f}%<br>RES",
                    "showarrow": False,
                    "font": {"size": 18, "color": "#dff8ea"},
                }
            ],
        )
        st.plotly_chart(fig_pie, width="stretch")
    else:
        st.info("Energy mix appears after a short data history is available.")
    st.markdown("</div>", unsafe_allow_html=True)

with status_col:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    render_section_header("Quick checks", "Operational status")
    st.progress(float(max(0.0, min(100.0, snap["SOC"]))) / 100.0, text=f"Battery SoC {snap['SOC']:.0f}%")
    st.progress(float(max(0.0, min(100.0, snap["TAUX_ER"]))) / 100.0, text=f"Renewable share {snap['TAUX_ER']:.0f}%")
    st.metric("Simulated time", f"{snap.get('HEURE_SIMULEE', 0.0):.1f} h")
    st.metric("Module temp", f"{snap['TEMP_MODULE']:.1f} deg C")
    st.metric("Rotor speed", f"{snap['VITESSE_ROTOR']:.1f} rpm")
    st.metric("Grid voltage", f"{snap['TENSION_RESEAU']:.1f} V")
    st.metric("Grid frequency", f"{snap['FREQUENCE_RESEAU']:.2f} Hz")
    st.markdown("</div>", unsafe_allow_html=True)


st.markdown('<div class="panel">', unsafe_allow_html=True)
render_section_header("Historian", "Process trends")
if not df.empty:
    trend_tabs = st.tabs(["Energy balance", "Battery", "Grid quality", "Weather"])

    with trend_tabs[0]:
        fig = go.Figure()
        if "puissance_pv" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["ts"],
                    y=df["puissance_pv"],
                    name="PV",
                    mode="lines",
                    line=dict(color="#f4b74a", width=3),
                    hovertemplate="PV: %{y:,.1f} W<br>%{x|%H:%M:%S, %b %d}<extra></extra>",
                )
            )
        if "puissance_eolien" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["ts"],
                    y=df["puissance_eolien"],
                    name="Wind",
                    mode="lines",
                    line=dict(color="#57b7ff", width=3),
                    hovertemplate="Wind: %{y:,.1f} W<br>%{x|%H:%M:%S, %b %d}<extra></extra>",
                )
            )
        if "puissance_charge" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["ts"],
                    y=df["puissance_charge"],
                    name="Load",
                    mode="lines",
                    line=dict(color="#ff8e86", width=2.2, dash="dash"),
                    hovertemplate="Load: %{y:,.1f} W<br>%{x|%H:%M:%S, %b %d}<extra></extra>",
                )
            )
        if "puissance_reseau" in df.columns:
            fig.add_trace(
                go.Bar(
                    x=df["ts"],
                    y=df["puissance_reseau"],
                    name="Grid exchange",
                    marker=dict(
                        color="rgba(133, 160, 153, 0.24)",
                        line=dict(color="rgba(160, 187, 179, 0.22)", width=0.6),
                    ),
                    hovertemplate="Grid exchange: %{y:,.1f} W<br>%{x|%H:%M:%S, %b %d}<extra></extra>",
                )
            )
        apply_trend_chart_theme(fig, height=400, yaxis_title="Power (W)")
        st.plotly_chart(fig, width="stretch", config=get_trend_chart_config())

    with trend_tabs[1]:
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        if "soc" in df.columns:
            fig2.add_trace(
                go.Scatter(
                    x=df["ts"],
                    y=df["soc"],
                    name="SoC",
                    mode="lines",
                    line=dict(color="#54d28d", width=2.8),
                    fill="tozeroy",
                    fillcolor="rgba(84, 210, 141, 0.12)",
                    hovertemplate="SoC: %{y:.1f}%<br>%{x|%H:%M:%S, %b %d}<extra></extra>",
                ),
                secondary_y=False,
            )
            add_threshold_line(fig2, y=Config.batterie.SOC_MIN * 100, label="SoC min")
            add_threshold_line(
                fig2,
                y=Config.batterie.SOC_MAX * 100,
                label="SoC max",
                color="rgba(246, 193, 90, 0.52)",
            )
        if "puissance_batterie" in df.columns:
            fig2.add_trace(
                go.Scatter(
                    x=df["ts"],
                    y=df["puissance_batterie"],
                    name="Battery power",
                    mode="lines",
                    line=dict(color="#ffb86c", width=2.3),
                    hovertemplate="Battery power: %{y:,.1f} W<br>%{x|%H:%M:%S, %b %d}<extra></extra>",
                ),
                secondary_y=True,
            )
        fig2.update_yaxes(title_text="SoC (%)", secondary_y=False)
        fig2.update_yaxes(title_text="Power (W)", secondary_y=True)
        apply_trend_chart_theme(fig2, height=380)
        st.plotly_chart(fig2, width="stretch", config=get_trend_chart_config())

    with trend_tabs[2]:
        fig3 = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            subplot_titles=("Grid voltage", "Grid frequency"),
        )
        if "tension_reseau" in df.columns:
            fig3.add_trace(
                go.Scatter(
                    x=df["ts"],
                    y=df["tension_reseau"],
                    mode="lines",
                    line=dict(color="#57b7ff", width=2.6),
                    hovertemplate="Grid voltage: %{y:,.1f} V<br>%{x|%H:%M:%S, %b %d}<extra></extra>",
                ),
                row=1,
                col=1,
            )
            add_threshold_line(fig3, y=Config.alarms.TENSION_BASSE, row=1, col=1)
            add_threshold_line(fig3, y=Config.alarms.TENSION_HAUTE, row=1, col=1)
        if "frequence_reseau" in df.columns:
            fig3.add_trace(
                go.Scatter(
                    x=df["ts"],
                    y=df["frequence_reseau"],
                    mode="lines",
                    line=dict(color="#54d28d", width=2.6),
                    hovertemplate="Grid frequency: %{y:,.2f} Hz<br>%{x|%H:%M:%S, %b %d}<extra></extra>",
                ),
                row=2,
                col=1,
            )
            add_threshold_line(fig3, y=Config.alarms.FREQUENCE_BASSE, row=2, col=1)
            add_threshold_line(fig3, y=Config.alarms.FREQUENCE_HAUTE, row=2, col=1)
        apply_trend_chart_theme(fig3, height=420, legend=False, top_margin=46)
        fig3.update_yaxes(title_text="Voltage (V)", row=1, col=1)
        fig3.update_yaxes(title_text="Frequency (Hz)", row=2, col=1)
        st.plotly_chart(fig3, width="stretch", config=get_trend_chart_config())

    with trend_tabs[3]:
        fig4 = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            subplot_titles=("Solar irradiance", "Wind speed"),
        )
        if "irradiance" in df.columns:
            fig4.add_trace(
                go.Scatter(
                    x=df["ts"],
                    y=df["irradiance"],
                    mode="lines",
                    line=dict(color="#f4b74a", width=2.7),
                    fill="tozeroy",
                    fillcolor="rgba(244,183,74,0.12)",
                    hovertemplate="Solar irradiance: %{y:,.1f}<br>%{x|%H:%M:%S, %b %d}<extra></extra>",
                ),
                row=1,
                col=1,
            )
        if "vitesse_vent" in df.columns:
            fig4.add_trace(
                go.Scatter(
                    x=df["ts"],
                    y=df["vitesse_vent"],
                    mode="lines",
                    line=dict(color="#57b7ff", width=2.6),
                    hovertemplate="Wind speed: %{y:,.1f} m/s<br>%{x|%H:%M:%S, %b %d}<extra></extra>",
                ),
                row=2,
                col=1,
            )
            add_threshold_line(
                fig4,
                y=Config.eolien.VITESSE_DEMARRAGE,
                label="Start speed",
                row=2,
                col=1,
                color="rgba(84, 210, 141, 0.48)",
            )
            add_threshold_line(
                fig4,
                y=Config.eolien.VITESSE_COUPURE,
                label="Cut-out speed",
                row=2,
                col=1,
            )
        apply_trend_chart_theme(fig4, height=420, legend=False, top_margin=46)
        fig4.update_yaxes(title_text="Irradiance", row=1, col=1)
        fig4.update_yaxes(title_text="Wind speed (m/s)", row=2, col=1)
        st.plotly_chart(fig4, width="stretch", config=get_trend_chart_config())
else:
    st.info("Run a few scans to populate live trends.")
st.markdown("</div>", unsafe_allow_html=True)


kpi_left, kpi_col, kpi_right = st.columns([0.16, 0.68, 0.16])

with kpi_col:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    render_section_header("Performance", "Session KPIs")
    if not df.empty:
        kpis = compute_energy_kpi(
            df,
            energie_imp=snap["ENERGIE_IMPORTEE"],
            energie_exp=snap["ENERGIE_EXPORTEE"],
        )
        kpi_items = "".join(
            f'<div class="kpi-item"><div class="k">{key}</div><div class="v">{value}</div></div>'
            for key, value in kpis.items()
        )
        st.markdown(f'<div class="kpi-list">{kpi_items}</div>', unsafe_allow_html=True)

        autosuff = float(kpis.get("Taux autosuffisance (%)", 0))
        gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=autosuff,
                title={"text": "Autosufficiency", "font": {"size": 22, "color": "#f7fcf9"}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#54d28d"},
                    "steps": [
                        {"range": [0, 40], "color": "#1a2730"},
                        {"range": [40, 75], "color": "#183529"},
                        {"range": [75, 100], "color": "#1f4a2f"},
                    ],
                    "threshold": {"line": {"color": "#ff7b72", "width": 3}, "value": 95},
                },
            )
        )
        gauge.update_layout(
            template="plotly_dark",
            height=280,
            margin=dict(t=70, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        gauge_left, gauge_center, gauge_right = st.columns([0.12, 0.76, 0.12])
        with gauge_center:
            st.plotly_chart(gauge, width="stretch")
    else:
        st.info("KPIs are computed after the historian starts receiving scans.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="panel">', unsafe_allow_html=True)
render_section_header("Forecasting", "Diagnostics and prediction")
if not df.empty and len(df) >= 20:
    pred = predict_battery(df)
    drift = detect_solar_drift(df)
    wind_health = plc.eolien.etat_sante

    st.markdown(
        f"""
        <div class="diag-item">
          <strong>Battery outlook</strong><br>
          {pred['statut']}<br>
          Autonomy: {pred['heures_autonomie'] if pred['heures_autonomie'] is not None else 'Stable / charging'} h<br>
          SoC: {pred['soc_actuel']}% | Trend: {pred['tendance_par_h']:+.2f}%/h
        </div>
        <div class="diag-item">
          <strong>PV performance</strong><br>
          {drift['message']}
        </div>
        <div class="diag-item">
          <strong>Wind turbine health</strong><br>
          State: {wind_health}<br>
          Wear: {plc.eolien.usure * 100:.2f}%<br>
          Service hours: {plc.eolien.heures_service:.1f} h
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.info("Diagnostics unlock after at least 20 historian samples.")
st.markdown("</div>", unsafe_allow_html=True)


st.markdown('<div class="panel">', unsafe_allow_html=True)
render_section_header("Safety", "Alarm center")
summary = plc.alarm.summary
alarm_cols = st.columns(4)
alarm_cols[0].metric("Critical", summary.get("CRITICAL", 0))
alarm_cols[1].metric("Alarm", summary.get("ALARM", 0))
alarm_cols[2].metric("Warning", summary.get("WARNING", 0))
alarm_cols[3].metric("Info", summary.get("INFO", 0))

if plc.alarm.active:
    for evt in sorted(plc.alarm.active, key=lambda event: event.timestamp, reverse=True):
        css = {
            "CRITICAL": "alarm alarm-critical",
            "ALARM": "alarm alarm-alarm",
            "WARNING": "alarm alarm-warning",
            "INFO": "alarm alarm-info",
        }.get(evt.level, "alarm")
        ack_label = "ACK" if evt.acked else "Pending ACK"
        st.markdown(
            f'<div class="{css}"><strong>{evt.level}</strong> | {evt} | {ack_label}</div>',
            unsafe_allow_html=True,
        )
else:
    st.success("No active alarms.")

if plc.alarm.history:
    with st.expander(f"Alarm history ({len(plc.alarm.history)} events)"):
        for evt in reversed(plc.alarm.history[-50:]):
            st.markdown(f"- {evt}")
st.markdown("</div>", unsafe_allow_html=True)


if auto_refresh and st.session_state.plc_mode == "RUN":
    time.sleep(1)
    st.rerun()
