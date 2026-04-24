"""
MySpencers Rewards (MSR) Dashboard — Dark Edition
==================================================
Features:
  - Dark mode only (high-contrast, clearly-visible labels)
  - Multi-file upload & consolidation
  - AWS RDS live connection (MySQL / PostgreSQL)
  - Date normalisation (dd-mm-yyyy) on ingestion
  - Enrollment logic:
       * MTD Enrollment  = MSR customers whose calendar_day's mmm-yy == msr_month's mmm-yy
       * Previous Enroll = MSR customers whose calendar_day > msr_month (already members)
  - Conversion %  = unique MSR members enrolled this month / total unique customer base
  - Bills >2K / ≤2K = count of NON-MSR bills only (MSR member bills excluded)
  - Export CSV / Excel

Run:
    pip install streamlit pandas plotly openpyxl xlsxwriter sqlalchemy pymysql psycopg2-binary
    streamlit run msr_dashboard.py
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ────────────────────────────────────────────────────────────────────────────
# Page config
# ────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MSR Dashboard | Spencer's Retail",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ────────────────────────────────────────────────────────────────────────────
# Dark-mode-only CSS — force every surface, label & input to be visible
# ────────────────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
    :root {
        --bg:         #0a0e1a;
        --bg-elev:    #111827;
        --bg-card:    #1a2233;
        --bg-input:   #0f1524;
        --border:     #2a3447;
        --border-lt:  #3a4660;
        --text:       #e8eef5;
        --text-mut:   #a6b4c8;
        --text-dim:   #7689a3;
        --gold:       #D4A017;
        --gold-lt:    #f5c646;
        --blue:       #4a8fe0;
        --blue-dk:    #1C4B82;
        --green:      #2A9D8F;
        --red:        #E76F51;
    }

    /* ── Global surfaces ───────────────────────────────────────────── */
    html, body,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    .stApp {
        background: var(--bg) !important;
        color: var(--text) !important;
    }
    .main .block-container {
        padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1440px;
        background: transparent !important;
    }
    html, body, [class*="css"] {
        font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif !important;
        color: var(--text);
    }

    /* ── Headings, paragraphs, captions ────────────────────────────── */
    h1, h2, h3, h4, h5, h6, p, span, label, div, li {
        color: var(--text);
    }
    .stMarkdown, .stCaption, .stText {
        color: var(--text) !important;
    }
    [data-testid="stCaptionContainer"] {
        color: var(--text-mut) !important;
    }
    code {
        background: var(--bg-elev) !important;
        color: var(--gold-lt) !important;
        padding: 2px 6px;
        border-radius: 4px;
    }

    /* ── Sidebar ───────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0e1526 0%, #0a0e1a 100%) !important;
        border-right: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] *,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {
        color: var(--text) !important;
        opacity: 1 !important;
    }
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: var(--gold-lt) !important;
        font-weight: 700 !important;
        margin-top: 1.1rem;
        margin-bottom: .4rem;
        padding-bottom: .35rem;
        border-bottom: 1px solid var(--border);
        letter-spacing: .3px;
    }
    section[data-testid="stSidebar"] .stMarkdown hr {
        border-color: var(--border);
        margin: .8rem 0;
    }

    /* ── Form inputs (universal dark) ──────────────────────────────── */
    input, textarea, select,
    [data-baseweb="input"] > div,
    [data-baseweb="select"] > div,
    [data-baseweb="textarea"] > div,
    .stTextInput > div > div,
    .stNumberInput > div > div,
    .stDateInput > div > div,
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background: var(--bg-input) !important;
        color: var(--text) !important;
        border-color: var(--border-lt) !important;
        border-radius: 8px !important;
    }
    input::placeholder, textarea::placeholder {
        color: var(--text-dim) !important;
        opacity: 1 !important;
    }

    /* multiselect pills */
    [data-baseweb="tag"] {
        background: var(--blue) !important;
        color: #fff !important;
        border-radius: 6px !important;
    }
    /* dropdown menu (popover) */
    [data-baseweb="popover"], [role="listbox"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-lt) !important;
    }
    [role="option"] {
        color: var(--text) !important;
    }
    [role="option"]:hover {
        background: var(--bg-elev) !important;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        background: var(--bg-card) !important;
        border: 1.5px dashed var(--border-lt) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
    }
    [data-testid="stFileUploader"] * { color: var(--text) !important; }
    [data-testid="stFileUploaderDropzone"] {
        background: var(--bg-elev) !important;
        border-color: var(--border-lt) !important;
    }

    /* ── Buttons ───────────────────────────────────────────────────── */
    .stButton > button {
        background: linear-gradient(135deg, var(--blue) 0%, var(--blue-dk) 100%) !important;
        color: #fff !important;
        border: 1px solid rgba(255,255,255,.08) !important;
        border-radius: 8px !important;
        padding: .55rem 1.1rem !important;
        font-weight: 600 !important;
        transition: all .2s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 18px rgba(74,143,224,.35);
    }
    .stButton > button:disabled {
        background: var(--bg-elev) !important;
        color: var(--text-dim) !important;
        cursor: not-allowed !important;
    }
    .stDownloadButton > button {
        background: var(--bg-card) !important;
        color: var(--gold-lt) !important;
        border: 1.5px solid var(--gold) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        width: 100% !important;
    }
    .stDownloadButton > button:hover {
        background: var(--gold) !important;
        color: #1a1100 !important;
    }

    /* ── Hero banner ───────────────────────────────────────────────── */
    .hero {
        background: linear-gradient(135deg, #13315C 0%, #1C4B82 55%, #0B2545 100%);
        color: #fff; padding: 1.5rem 1.9rem; border-radius: 14px;
        margin-bottom: 1.2rem; border: 1px solid rgba(255,255,255,.08);
        box-shadow: 0 12px 36px rgba(0,0,0,.55);
        display: flex; align-items: center; justify-content: space-between;
    }
    .hero h1 { margin:0; font-size:1.65rem; font-weight:700; letter-spacing:-0.5px; color:#fff; }
    .hero .tag { font-size:0.88rem; opacity:0.88; margin-top:0.25rem; color:#d9e3f2; }
    .hero .badge {
        background: rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.22);
        padding: 0.4rem 0.9rem; border-radius:999px; font-size:0.78rem; font-weight:500;
        color:#fff;
    }

    /* ── KPI cards ─────────────────────────────────────────────────── */
    .kpi-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 14px; padding: 1.15rem 1.25rem;
        transition: transform .18s ease, box-shadow .18s ease;
        height: 100%;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 26px rgba(0,0,0,.5);
        border-color: var(--border-lt);
    }
    .kpi-label {
        font-size:.76rem; text-transform:uppercase; letter-spacing:1.2px;
        color:var(--text-mut); font-weight:600; margin-bottom:.45rem;
    }
    .kpi-value { font-size:1.95rem; font-weight:800; color:var(--text); line-height:1.1; }
    .kpi-sub   { font-size:.78rem; color:var(--text-dim); margin-top:.4rem; }
    .kpi-accent-blue  { border-top:4px solid var(--blue); }
    .kpi-accent-gold  { border-top:4px solid var(--gold); }
    .kpi-accent-green { border-top:4px solid var(--green); }
    .kpi-accent-red   { border-top:4px solid var(--red); }

    /* ── Section titles ────────────────────────────────────────────── */
    .section-title {
        font-size:1.08rem; font-weight:700; color:var(--gold-lt);
        margin:1.6rem 0 .75rem 0; padding-bottom:.45rem;
        border-bottom: 1px solid var(--border); display:flex; align-items:center; gap:.55rem;
    }
    .section-title .dot {
        width:9px; height:9px; border-radius:50%;
        background: linear-gradient(135deg, var(--gold), var(--gold-lt));
        box-shadow: 0 0 8px rgba(212,160,23,.6);
    }

    /* ── Tabs ──────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: .5rem;
        border-bottom: 1px solid var(--border);
        background: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        color: var(--text-mut) !important;
        font-weight: 600 !important;
        border-radius: 6px 6px 0 0 !important;
        padding: .55rem 1rem !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--gold-lt) !important;
        border-bottom: 2px solid var(--gold) !important;
    }

    /* ── DataFrame ─────────────────────────────────────────────────── */
    [data-testid="stDataFrame"],
    [data-testid="stDataFrameResizable"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }
    [data-testid="stDataFrame"] * {
        color: var(--text) !important;
    }

    /* Alerts / info / warning / success / error boxes */
    [data-testid="stAlert"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-lt) !important;
        border-radius: 10px !important;
    }
    [data-testid="stAlert"] * { color: var(--text) !important; }

    /* Expander */
    [data-testid="stExpander"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }
    [data-testid="stExpander"] summary { color: var(--gold-lt) !important; font-weight: 600 !important; }

    /* Plotly container */
    [data-testid="stPlotlyChart"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        padding: .3rem !important;
    }

    /* Hide only Streamlit's menu + toolbar + footer — KEEP the header
       so the native sidebar-toggle arrow remains clickable. */
    #MainMenu, footer { visibility: hidden; height: 0; }
    [data-testid="stToolbar"] { visibility: hidden; height: 0; }
    [data-testid="stHeader"] {
        background: transparent !important;
        visibility: visible !important;
        height: auto !important;
    }

    /* ── Sidebar collapse/expand controls — make them obvious ─────── */
    /* Arrow shown INSIDE the open sidebar to collapse it */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapseButton"] button,
    button[kind="headerNoPadding"] {
        visibility: visible !important;
        display: inline-flex !important;
        background: var(--bg-card) !important;
        color: var(--gold-lt) !important;
        border: 1px solid var(--border-lt) !important;
        border-radius: 6px !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="collapsedControl"] svg {
        color: var(--gold-lt) !important;
        fill: var(--gold-lt) !important;
    }

    /* Floating pill shown when the sidebar IS collapsed — this is the
       button that was getting hidden. Force it visible + prominent. */
    [data-testid="collapsedControl"] {
        visibility: visible !important;
        display: block !important;
        position: fixed !important;
        top: .9rem !important;
        left: .9rem !important;
        z-index: 999999 !important;
        background: linear-gradient(135deg, var(--blue) 0%, var(--blue-dk) 100%) !important;
        border: 1px solid var(--gold) !important;
        border-radius: 8px !important;
        padding: .35rem .55rem !important;
        box-shadow: 0 6px 16px rgba(0,0,0,.55) !important;
    }
    [data-testid="collapsedControl"] button {
        background: transparent !important;
        color: #fff !important;
    }
    [data-testid="collapsedControl"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 22px rgba(74,143,224,.45) !important;
    }

    /* Scrollbar (webkit) */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--border-lt); border-radius: 5px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--blue); }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Palettes (dark-mode friendly)
PALETTE   = {
    "navy":"#0B2545","blue":"#4a8fe0","gold":"#D4A017","gold_lt":"#f5c646",
    "teal":"#2A9D8F","red":"#E76F51","grey":"#8A9BB4",
}
SEQ_BLUE  = ["#1e3558","#27466f","#305787","#3a699e","#4a7db5","#6194cc","#7badde","#9bc6ec"]
SEQ_GOLD  = ["#3a2a07","#5c430b","#825d0f","#a87c0a","#D4A017","#e2b93a","#f1cd62","#f9dd8a"]

REQUIRED_COLS = [
    "store_code","store_name","mobile_number","bill_no",
    "grs_sales","msr_number","msr_month","noc_tagging","msr_tagging","asm_name",
]
DATE_COLS = ["calendar_day","month_name"]

# ────────────────────────────────────────────────────────────────────────────
# Session state
# ────────────────────────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "raw_df": None,
        "data_loaded": False,
        "data_source": None,
        "page": "landing",
        "uploaded_files_info": [],
        "rds_connected": False,
        "rds_config": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
_init_state()

# ────────────────────────────────────────────────────────────────────────────
# Date helpers
# ────────────────────────────────────────────────────────────────────────────
def _parse_flexible_date(series: pd.Series) -> pd.Series:
    """Try many date formats; return a datetime64 Series.
    Picks the format that parses the MOST non-null values (not just >50%),
    so a half-null msr_month column still gets its good values recognised.
    """
    s = series.astype(str).str.strip()
    # A row is "parse-worthy" if it isn't obviously null
    candidate_mask = ~s.str.lower().isin(
        {"nan", "none", "null", "nat", "na", ""}
    )
    total_candidates = max(int(candidate_mask.sum()), 1)

    formats = [
        # full dates
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%m-%d-%Y", "%m/%d/%Y",
        "%d-%b-%Y", "%d %b %Y", "%d/%b/%Y", "%d-%B-%Y", "%d %B %Y",
        # month-year only (mmm-yy, mmm-yyyy, full month, numeric)
        "%b-%y", "%b %y", "%b/%y",
        "%b-%Y", "%b %Y", "%b/%Y",
        "%B-%y", "%B %y", "%B-%Y", "%B %Y",
        "%Y-%m", "%Y/%m", "%m/%Y", "%m-%Y",
    ]

    best_parsed, best_hits = None, 0
    for fmt in formats:
        try:
            parsed = pd.to_datetime(s, format=fmt, errors="coerce")
            hits = int(parsed.notna().sum())
            if hits > best_hits:
                best_hits, best_parsed = hits, parsed
            # Early exit if we've already matched ≥95% of candidates
            if hits >= 0.95 * total_candidates:
                return parsed
        except Exception:
            continue

    if best_parsed is not None and best_hits >= 0.5 * total_candidates:
        return best_parsed

    # Last-resort fallback — let pandas guess, day-first (Indian convention)
    return pd.to_datetime(s, errors="coerce", dayfirst=True)

def _to_dd_mm_yyyy(series: pd.Series) -> pd.Series:
    return series.dt.strftime("%d-%m-%Y")

# ────────────────────────────────────────────────────────────────────────────
# File loading
# ────────────────────────────────────────────────────────────────────────────
def load_single(file_bytes: bytes, filename: str) -> pd.DataFrame:
    buf = io.BytesIO(file_bytes)
    lower = filename.lower()
    if lower.endswith((".xlsx",".xls",".xlsm")):
        return pd.read_excel(buf)
    for sep in [",",";","\t","|"]:
        try:
            buf.seek(0)
            df = pd.read_csv(buf, sep=sep, low_memory=False)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    buf.seek(0)
    return pd.read_csv(buf, low_memory=False)

# ────────────────────────────────────────────────────────────────────────────
# AWS RDS connector
# ────────────────────────────────────────────────────────────────────────────
def load_from_rds(engine_type: str, host: str, port: int, database: str,
                  user: str, password: str, query: str) -> pd.DataFrame:
    """Load data from an AWS RDS (MySQL / PostgreSQL) instance."""
    from urllib.parse import quote_plus
    try:
        from sqlalchemy import create_engine, text
    except ImportError as e:
        raise RuntimeError(
            "SQLAlchemy is required for RDS connections. "
            "Install: pip install sqlalchemy pymysql psycopg2-binary"
        ) from e

    pw = quote_plus(password or "")
    if engine_type.lower() in ("mysql", "mariadb", "aurora-mysql"):
        url = f"mysql+pymysql://{user}:{pw}@{host}:{port}/{database}"
    elif engine_type.lower() in ("postgresql", "postgres", "aurora-postgres"):
        url = f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{database}"
    else:
        raise ValueError(f"Unsupported engine: {engine_type}")

    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    return df

# ────────────────────────────────────────────────────────────────────────────
# Data processing
# ────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def process_data(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df.columns = [str(c).strip().lower().replace(" ","_") for c in df.columns]

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}. Available: {list(df.columns)}")

    # Trim strings
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip()

    # NULL strings → NaN
    null_strs = {"NULL","null","Null","nan","NaN","None","none","","na","NA"}
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].where(~df[c].isin(null_strs), other=pd.NA)

    # ── Date parsing ─────────────────────────────────────────────────────
    if "calendar_day" in df.columns:
        df["calendar_day_dt"] = _parse_flexible_date(df["calendar_day"].astype(str))
        df["calendar_day"]    = _to_dd_mm_yyyy(df["calendar_day_dt"])

    if "month_name" in df.columns:
        df["month_name_dt"]   = _parse_flexible_date(df["month_name"].astype(str))
        df["reporting_month"] = df["month_name_dt"].dt.strftime("%b-%y")

    if "msr_month" in df.columns:
        df["msr_month_dt"]  = _parse_flexible_date(df["msr_month"].astype(str))
        df["enroll_month"]  = df["msr_month_dt"].dt.strftime("%b-%y")
        df["enroll_period"] = df["msr_month_dt"].dt.to_period("M")

    if "calendar_day_dt" in df.columns and df["calendar_day_dt"].notna().any():
        df["shopping_date"] = df["calendar_day_dt"]
    elif "month_name_dt" in df.columns:
        df["shopping_date"] = df["month_name_dt"]
    else:
        df["shopping_date"] = pd.NaT

    df["shopping_month"]  = df["shopping_date"].dt.strftime("%b-%y")
    df["shopping_period"] = df["shopping_date"].dt.to_period("M")

    # Exclude invalid mobile numbers
    mob = pd.to_numeric(df["mobile_number"], errors="coerce")
    df = df[mob.notna() & (mob > 0)].copy()

    # Drop Untagged NOC
    before = len(df)
    df = df[df["noc_tagging"].astype(str).str.lower() != "untagged"].copy()
    df.attrs["dropped_untagged"] = before - len(df)

    # ── MSR flag ─────────────────────────────────────────────────────────
    msr_num_valid = pd.to_numeric(df["msr_number"], errors="coerce").fillna(0) > 0
    df["is_msr"] = msr_num_valid

    # ── NEW: MTD / previous enrollment flags (per row) ───────────────────
    #   MTD Enrollment : is_msr AND calendar_day.mmm-yy == msr_month.mmm-yy
    #   Previous Enroll: is_msr AND calendar_day is AFTER msr_month (already a member)
    #   Future Enroll  : is_msr AND calendar_day is BEFORE msr_month (will enroll later)
    if "shopping_period" in df.columns and "enroll_period" in df.columns:
        cal_per = df["shopping_period"]
        msr_per = df["enroll_period"]
        df["is_mtd_enrollment"]  = df["is_msr"] & cal_per.notna() & msr_per.notna() & (cal_per == msr_per)
        df["is_prev_enrollment"] = df["is_msr"] & cal_per.notna() & msr_per.notna() & (cal_per > msr_per)
        df["is_fut_enrollment"]  = df["is_msr"] & cal_per.notna() & msr_per.notna() & (cal_per < msr_per)
    else:
        df["is_mtd_enrollment"]  = False
        df["is_prev_enrollment"] = False
        df["is_fut_enrollment"]  = False

    # DAY-level enrollment: msr_month formatted as dd-mm-yyyy must match calendar_day exactly
    if "msr_month_dt" in df.columns and "calendar_day" in df.columns:
        msr_day_str = df["msr_month_dt"].dt.strftime("%d-%m-%Y")
        df["is_day_enrollment"] = (
            df["is_msr"]
            & msr_day_str.notna()
            & df["calendar_day"].notna()
            & (msr_day_str == df["calendar_day"].astype(str))
        )
    else:
        df["is_day_enrollment"] = False

    # Numeric coercions
    for c in ["grs_sales","nob_ach","billed_qty"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    return df

# ────────────────────────────────────────────────────────────────────────────
# Metrics
# ────────────────────────────────────────────────────────────────────────────
def _latest_period(df):
    per = df["shopping_period"].dropna() if "shopping_period" in df.columns else pd.Series(dtype="object")
    return per.max() if not per.empty else None

def _count_bills(sub: pd.DataFrame, group: list) -> pd.Series:
    """Count non-MSR bills. Uses bill_no nunique if available, else row count."""
    if sub.empty:
        return pd.Series(dtype=int)
    if "bill_no" in sub.columns and sub["bill_no"].notna().any():
        return sub.groupby(group)["bill_no"].nunique()
    return sub.groupby(group).size()

@st.cache_data(show_spinner=False)
def calculate_metrics(df: pd.DataFrame, mtd_month_label: Optional[str] = None) -> pd.DataFrame:
    """Store-level summary."""
    if df.empty:
        return pd.DataFrame()

    group_cols = [c for c in ["store_code","store_name","asm_name"] if c in df.columns]

    # MTD mask: customers whose calendar_day's month == msr_month's month
    # If a specific reporting-month label is pinned, additionally restrict
    mtd_mask = df["is_mtd_enrollment"] if "is_mtd_enrollment" in df.columns else pd.Series(False, index=df.index)
    if mtd_month_label and mtd_month_label != "All" and "enroll_month" in df.columns:
        mtd_mask = mtd_mask & (df["enroll_month"] == mtd_month_label)

    # Core counts
    total_cust = df.groupby(group_cols)["mobile_number"].nunique().rename("Total NOC")
    mtd        = df[mtd_mask].groupby(group_cols)["mobile_number"].nunique().rename("MTD Enrollment")
    msr_cnt    = df[df["is_msr"]].groupby(group_cols)["mobile_number"].nunique().rename("Unique MSR Members")
    non_msr    = df[~df["is_msr"]].groupby(group_cols)["mobile_number"].nunique().rename("Unique Non-MSR Members")

    # NEW Bills logic — count NON-MSR bills only (MSR member bills excluded)
    non_msr_df = df[~df["is_msr"]].copy()
    gt_df = non_msr_df[non_msr_df["grs_sales"] >  2000]
    lt_df = non_msr_df[non_msr_df["grs_sales"] <= 2000]
    nob_gt = _count_bills(gt_df, group_cols).rename("Bills >2K")
    nob_lt = _count_bills(lt_df, group_cols).rename("Bills ≤2K")

    metrics = (pd.concat([total_cust, mtd, msr_cnt, non_msr, nob_gt, nob_lt], axis=1)
                 .fillna(0).astype(int, errors="ignore").reset_index())

    # NEW Conversion = MTD Enrollment / Total NOC × 100
    metrics["Conversion %"] = np.where(
        metrics["Total NOC"] > 0,
        (metrics["MTD Enrollment"] / metrics["Total NOC"] * 100).round(2),
        0.0,
    )

    rename = {"store_code":"Store Code","store_name":"Store Name","asm_name":"ASM Name"}
    metrics = metrics.rename(columns=rename)
    order = (list(rename.values()) +
             ["Total NOC","MTD Enrollment","Unique MSR Members","Unique Non-MSR Members",
              "Conversion %","Bills >2K","Bills ≤2K"])
    cols = [c for c in order if c in metrics.columns]
    return metrics[cols].sort_values("Total NOC", ascending=False)


@st.cache_data(show_spinner=False)
def calculate_drilldown(df: pd.DataFrame, mtd_month_label: Optional[str] = None) -> pd.DataFrame:
    """Day × Store drill-down."""
    if df.empty or "shopping_date" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df["Day"] = df["shopping_date"].dt.strftime("%d-%m-%Y")

    group = [c for c in ["Day","store_code","store_name"] if c in df.columns]

    # DAY Enrollment: use day-exact match (msr_month dd-mm-yyyy == calendar_day)
    day_mask = df["is_day_enrollment"] if "is_day_enrollment" in df.columns else pd.Series(False, index=df.index)

    total_noc  = df.groupby(group)["mobile_number"].nunique().rename("Total NOC")
    enrollment = df[day_mask].groupby(group)["mobile_number"].nunique().rename("DAY Enrollment")
    msr_cnt    = df[df["is_msr"]].groupby(group)["mobile_number"].nunique().rename("Unique MSR Members")
    non_msr    = df[~df["is_msr"]].groupby(group)["mobile_number"].nunique().rename("Unique Non-MSR Members")

    # NEW Bills — non-MSR only, count of bills
    non_msr_df = df[~df["is_msr"]].copy()
    gt_df = non_msr_df[non_msr_df["grs_sales"] >  2000]
    lt_df = non_msr_df[non_msr_df["grs_sales"] <= 2000]
    nob_gt = _count_bills(gt_df, group).rename("Bills >2K")
    nob_lt = _count_bills(lt_df, group).rename("Bills ≤2K")

    dd = (pd.concat([total_noc, enrollment, msr_cnt, non_msr, nob_gt, nob_lt], axis=1)
            .fillna(0).astype(int, errors="ignore").reset_index())

    dd["Conversion %"] = np.where(
        dd["Total NOC"] > 0,
        (dd["DAY Enrollment"] / dd["Total NOC"] * 100).round(2),
        0.0,
    )

    rename = {"store_code":"Store Code","store_name":"Store Name"}
    dd = dd.rename(columns=rename)
    order = ["Day","Store Code","Store Name","Total NOC","DAY Enrollment","Unique MSR Members",
             "Unique Non-MSR Members","Conversion %","Bills >2K","Bills ≤2K"]
    cols = [c for c in order if c in dd.columns]
    return dd[cols].sort_values(["Day","Store Code"], ascending=[False, True])

# ────────────────────────────────────────────────────────────────────────────
# Filters
# ────────────────────────────────────────────────────────────────────────────
def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    out = df.copy()
    for col, sel in filters.get("multi", {}).items():
        if sel and col in out.columns:
            out = out[out[col].isin(sel)]

    date_from = filters.get("date_from")
    date_to   = filters.get("date_to")
    if date_from and date_to and "shopping_date" in out.columns:
        out = out[(out["shopping_date"] >= pd.Timestamp(date_from)) &
                  (out["shopping_date"] <= pd.Timestamp(date_to))]

    enroll_months = filters.get("enroll_months") or []
    if enroll_months and "enroll_month" in out.columns:
        out = out[out["enroll_month"].isin(enroll_months)]

    shop_months = filters.get("shopping_months") or []
    if shop_months and "shopping_month" in out.columns:
        out = out[out["shopping_month"].isin(shop_months)]

    q = (filters.get("search") or "").strip()
    if q:
        mask = np.zeros(len(out), dtype=bool)
        for c in ["store_code","msr_number","mobile_number"]:
            if c in out.columns:
                mask |= out[c].astype(str).str.contains(q, case=False, na=False)
        out = out[mask]
    return out

# ────────────────────────────────────────────────────────────────────────────
# Exports
# ────────────────────────────────────────────────────────────────────────────
def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "MSR Metrics") -> bytes:
    buf = io.BytesIO()
    try:
        import xlsxwriter  # noqa
        engine = "xlsxwriter"
    except ImportError:
        engine = "openpyxl"
    with pd.ExcelWriter(buf, engine=engine) as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        if engine == "xlsxwriter":
            ws = writer.sheets[sheet_name]
            for i, col in enumerate(df.columns):
                w = max(12, min(32, int(df[col].astype(str).map(len).max() or 10) + 2))
                ws.set_column(i, i, w)
    buf.seek(0)
    return buf.getvalue()


def to_pdf_bytes(df: pd.DataFrame, title: str = "MSR Report") -> bytes:
    """Generate a styled PDF table from a DataFrame using reportlab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A3, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (Paragraph, SimpleDocTemplate,
                                        Spacer, Table, TableStyle)
    except ImportError:
        raise ImportError(
            "reportlab is required for PDF export. "
            "Install: pip install reportlab"
        )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A3),
                            leftMargin=1*cm, rightMargin=1*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    title_style.textColor = colors.HexColor("#D4A017")
    title_style.fontSize = 14
    title_style.spaceAfter = 10

    elements = []
    elements.append(Paragraph(f"Spencer's Retail — {title}", title_style))
    from datetime import datetime as _dt
    elements.append(Paragraph(
        f"Generated: {_dt.now().strftime('%d-%m-%Y %H:%M')}  |  Rows: {len(df):,}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 0.4*cm))

    # Build table data
    col_names = [str(c) for c in df.columns]
    data = [col_names]
    for _, row in df.iterrows():
        data.append([str(v) for v in row])

    # Compute column widths proportionally
    page_w = landscape(A3)[0] - 2*cm
    n_cols = len(col_names)
    col_w  = page_w / n_cols

    tbl = Table(data, colWidths=[col_w] * n_cols, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Header
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#0B2545")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.HexColor("#f5c646")),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 7),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",      (0, 0), (-1, 0), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING",  (0, 0), (-1, 0), 6),
        # Body
        ("BACKGROUND",  (0, 1), (-1, -1), colors.HexColor("#1a2233")),
        ("TEXTCOLOR",   (0, 1), (-1, -1), colors.HexColor("#e8eef5")),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 6.5),
        ("ALIGN",       (0, 1), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 1), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#1a2233"), colors.HexColor("#111827")]),
        # Grid
        ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#2a3447")),
        ("LINEBELOW",   (0, 0), (-1, 0), 1.2, colors.HexColor("#D4A017")),
        # Padding
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("TOPPADDING",  (0, 1), (-1, -1), 4),
    ]))
    elements.append(tbl)
    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


# ── Display rename mappings ──────────────────────────────────────────────────
STORE_DISPLAY_RENAME = {
    "MTD Enrollment"        : "MTD Member Enrollment",
    "Unique MSR Members"    : "MTD Member Shopped",
    "Unique Non-MSR Members": "MTD Non Member Shopped",
    "Conversion %"          : "Member Enrollment Conversion %",
    "Bills >2K"             : "Non Member >2k Bill",
    "Bills ≤2K"             : "Non Member <2k Bill",
}

DRILL_DISPLAY_RENAME = {
    "DAY Enrollment"        : "DAY Enrollment",          # already correct
    "Unique MSR Members"    : "MTD Member Shopped",
    "Unique Non-MSR Members": "MTD Non Member Shopped",
    "Conversion %"          : "Member Enrollment Conversion %",
    "Bills >2K"             : "Non Member >2k Bill",
    "Bills ≤2K"             : "Non Member <2k Bill",
}

# ────────────────────────────────────────────────────────────────────────────
# UI helpers
# ────────────────────────────────────────────────────────────────────────────
def render_hero(subtitle="Customer & MSR Membership Performance"):
    badge = ""
    if st.session_state.data_loaded:
        src = st.session_state.data_source or "Data"
        badge = f'<div class="badge">● Live · {src}</div>'
    st.markdown(f"""
    <div class="hero">
        <div>
            <h1>🛒 MySpencers Rewards Dashboard</h1>
            <div class="tag">{subtitle}</div>
        </div>
        {badge}
    </div>""", unsafe_allow_html=True)

def kpi(label, value, sub="", accent="blue"):
    st.markdown(f"""
    <div class="kpi-card kpi-accent-{accent}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

def section(title, icon="📊"):
    st.markdown(f'<div class="section-title"><span class="dot"></span>{icon} {title}</div>',
                unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────────────────
# Data diagnostics — open this when MTD / Conversion looks wrong
# ────────────────────────────────────────────────────────────────────────────
def render_diagnostics(df: pd.DataFrame):
    """Show date-parsing status, period distributions and row-flag counts.
    This is the fastest way to explain an MTD Enrollment == 0 result.
    """
    total = len(df)
    msr_rows = int(df["is_msr"].sum()) if "is_msr" in df.columns else 0
    mtd_rows = int(df["is_mtd_enrollment"].sum()) if "is_mtd_enrollment" in df.columns else 0
    prev_rows = int(df["is_prev_enrollment"].sum()) if "is_prev_enrollment" in df.columns else 0
    fut_rows = int(df["is_fut_enrollment"].sum()) if "is_fut_enrollment" in df.columns else 0
    cal_ok = int(df["calendar_day_dt"].notna().sum()) if "calendar_day_dt" in df.columns else 0
    msr_month_ok = int(df["msr_month_dt"].notna().sum()) if "msr_month_dt" in df.columns else 0
    msr_rows_with_month = int((df["is_msr"] & df["msr_month_dt"].notna()).sum()) \
        if "msr_month_dt" in df.columns and "is_msr" in df.columns else 0

    # Prominent banner if MTD is 0
    if mtd_rows == 0 and msr_rows > 0:
        st.markdown(
            f"""<div style="background:#4a1a1f;border:1px solid #ff8b8b;color:#ffd4d4;
                  padding:.9rem 1.1rem;border-radius:10px;margin:.6rem 0 1rem 0;">
                  <b>⚠️ MTD Enrollment is 0.</b> Of {msr_rows:,} MSR rows,
                  {msr_rows_with_month:,} have a parseable <code>msr_month</code>
                  and none of them land in the same calendar month as their <code>calendar_day</code>.
                  Open the panel below to see exactly why.
               </div>""",
            unsafe_allow_html=True,
        )

    with st.expander("🔧 Data Diagnostics — date parsing & enrollment flags",
                     expanded=(mtd_rows == 0 and msr_rows > 0)):
        a, b, c = st.columns(3)
        with a:
            st.metric("Rows after processing", f"{total:,}")
            st.metric("MSR rows (is_msr=True)", f"{msr_rows:,}")
        with b:
            st.metric("calendar_day parsed OK", f"{cal_ok:,} / {total:,}")
            st.metric("msr_month parsed OK", f"{msr_month_ok:,} / {total:,}")
        with c:
            st.metric("MTD enrollment rows", f"{mtd_rows:,}")
            st.metric("Previous enrollment rows", f"{prev_rows:,}")
            st.metric("Future enrollment rows", f"{fut_rows:,}")

        # Show unparsed msr_month examples if any
        if "msr_month" in df.columns and "msr_month_dt" in df.columns:
            failed_mask = df["msr_month"].notna() & df["msr_month_dt"].isna()
            if failed_mask.any():
                samples = df.loc[failed_mask, "msr_month"].astype(str).unique()[:15]
                st.warning(
                    f"⚠️ {int(failed_mask.sum()):,} rows have an `msr_month` value "
                    f"that couldn't be parsed. Sample values: {list(samples)}"
                )

        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**Top shopping months (from `calendar_day`)**")
            if "shopping_period" in df.columns:
                vc = df["shopping_period"].astype(str).value_counts().head(10)
                st.dataframe(vc.rename_axis("period").reset_index(name="rows"),
                             use_container_width=True)
        with cc2:
            st.markdown("**Top enrollment months (from `msr_month`, MSR rows only)**")
            if "enroll_period" in df.columns and "is_msr" in df.columns:
                vc = df.loc[df["is_msr"], "enroll_period"].astype(str).value_counts().head(10)
                st.dataframe(vc.rename_axis("period").reset_index(name="rows"),
                             use_container_width=True)

        st.markdown("**Sample MSR rows — compare `shopping_period` vs `enroll_period`:**")
        sample_cols = ["calendar_day", "shopping_period", "msr_month",
                       "enroll_period", "is_msr",
                       "is_mtd_enrollment", "is_prev_enrollment", "is_fut_enrollment"]
        sample_cols = [c for c in sample_cols if c in df.columns]
        if "is_msr" in df.columns and df["is_msr"].any():
            samp = df.loc[df["is_msr"], sample_cols].head(20).copy()
            # stringify periods for clean display
            for c in ["shopping_period", "enroll_period"]:
                if c in samp.columns:
                    samp[c] = samp[c].astype(str)
            st.dataframe(samp, use_container_width=True)
        else:
            st.info("No MSR rows to sample.")

        st.caption(
            "**How MTD Enrollment is defined:** a row is counted if `is_msr` is True "
            "AND `shopping_period == enroll_period` (same month-year on both sides). "
            "If every MSR customer enrolled in months **before** their shopping date, "
            "MTD will legitimately be 0 — they'd all show up in *Previous enrollment* instead."
        )

# ────────────────────────────────────────────────────────────────────────────
# Conversion % colouring (dark-mode palette)
# ────────────────────────────────────────────────────────────────────────────
def color_conversion(val):
    try:
        v = float(str(val).replace("%",""))
    except Exception:
        return ""
    if v >= 15:
        return "background-color:#1e4430; color:#8ff0a8; font-weight:700"
    elif v >= 8:
        return "background-color:#4d3a0a; color:#ffd47a; font-weight:700"
    else:
        return "background-color:#4a1a1f; color:#ff8b8b; font-weight:700"

def style_metrics(df: pd.DataFrame):
    s = df.style
    conv_col = next((c for c in df.columns if "Conversion" in c or "conversion" in c), None)
    if conv_col:
        s = s.map(color_conversion, subset=[conv_col])
    # overall dark styling for the styler
    s = s.set_table_styles([
        {"selector": "th", "props": [("background-color", "#111827"),
                                      ("color", "#f5c646"),
                                      ("font-weight", "700"),
                                      ("border-color", "#2a3447")]},
        {"selector": "td", "props": [("background-color", "#1a2233"),
                                      ("color", "#e8eef5"),
                                      ("border-color", "#2a3447")]},
    ])
    return s

# ────────────────────────────────────────────────────────────────────────────
# Landing page — Upload + AWS RDS
# ────────────────────────────────────────────────────────────────────────────
def landing_page():
    render_hero("Connect a data source to begin")
    st.write("")

    tab_upload, tab_rds, tab_sample = st.tabs([
        "📁 Upload Files",
        "🗄️ AWS RDS (Live DB)",
        "🧪 Sample Data",
    ])

    # ── File Upload ────────────────────────────────────────────────────────
    with tab_upload:
        st.markdown("""
        <div style="background:var(--bg-card);border:1px solid var(--border);
                    border-radius:14px;padding:1.4rem;margin-bottom:1rem;">
            <h3 style="color:#f5c646;margin:0 0 .5rem 0;">📁 Upload CSV / Excel</h3>
            <p style="color:#a6b4c8;margin:0;font-size:.9rem;">
                Upload one or <b>multiple files</b> — they will be consolidated automatically.
                <br>Supported: <code>.csv</code>, <code>.xlsx</code>, <code>.xls</code>, <code>.xlsm</code>
            </p>
        </div>""", unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "Drop one or more files here",
            type=["csv","xlsx","xls","xlsm"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

        if uploaded:
            st.success(f"**{len(uploaded)} file(s)** selected: {', '.join(f.name for f in uploaded)}")

        if st.button("🚀 Load & Analyse", use_container_width=True,
                     disabled=not uploaded, key="btn_load_files"):
            dfs, info = [], []
            for f in uploaded:
                try:
                    with st.spinner(f"Parsing {f.name}…"):
                        raw = load_single(f.getvalue(), f.name)
                    dfs.append(raw); info.append(f.name)
                except Exception as e:
                    st.error(f"Could not load {f.name}: {e}")
            if dfs:
                consolidated = pd.concat(dfs, ignore_index=True)
                st.session_state.raw_df = consolidated
                st.session_state.data_loaded = True
                st.session_state.data_source = f"Upload · {len(dfs)} file(s)"
                st.session_state.uploaded_files_info = info
                st.session_state.page = "dashboard"
                st.success(f"Consolidated {len(dfs)} file(s) → {len(consolidated):,} rows")
                st.rerun()

    # ── AWS RDS ────────────────────────────────────────────────────────────
    with tab_rds:
        st.markdown("""
        <div style="background:var(--bg-card);border:1px solid var(--border);
                    border-radius:14px;padding:1.4rem;margin-bottom:1rem;">
            <h3 style="color:#f5c646;margin:0 0 .5rem 0;">🗄️ Connect to AWS RDS</h3>
            <p style="color:#a6b4c8;margin:0;font-size:.9rem;">
                Live-load your MSR data from an AWS RDS instance (MySQL, MariaDB, Aurora-MySQL, PostgreSQL, Aurora-Postgres).
                <br>Ensure the RDS security group allows inbound connections from this host's IP.
                <br><b>Prereq:</b> <code>pip install sqlalchemy pymysql psycopg2-binary</code>
            </p>
        </div>""", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            engine_type = st.selectbox(
                "Engine",
                ["mysql", "postgresql"],
                index=0,
                help="Pick the RDS engine type",
            )
            host = st.text_input(
                "Host / Endpoint",
                placeholder="your-db.abcd1234.ap-south-1.rds.amazonaws.com",
                value=st.session_state.rds_config.get("host", ""),
            )
            database = st.text_input(
                "Database",
                placeholder="spencers_msr",
                value=st.session_state.rds_config.get("database", ""),
            )
        with c2:
            default_port = 3306 if engine_type == "mysql" else 5432
            port = st.number_input(
                "Port", min_value=1, max_value=65535,
                value=int(st.session_state.rds_config.get("port", default_port)),
            )
            user = st.text_input(
                "Username",
                placeholder="admin",
                value=st.session_state.rds_config.get("user", ""),
            )
            password = st.text_input(
                "Password",
                type="password",
                value=st.session_state.rds_config.get("password", ""),
            )

        default_query = st.session_state.rds_config.get(
            "query",
            "SELECT calendar_day, store_code, store_name, mobile_number, bill_no,\n"
            "       grs_sales, msr_number, msr_month, noc_tagging, msr_tagging,\n"
            "       asm_name, month_name, nob_ach, billed_qty\n"
            "FROM msr_transactions\n"
            "WHERE calendar_day >= DATE_SUB(CURRENT_DATE, INTERVAL 90 DAY);",
        )
        query = st.text_area(
            "SQL Query",
            value=default_query, height=160,
            help="Must return the required columns. You can schedule this in cron / Airflow for scheduled refreshes.",
        )

        b1, b2 = st.columns([1, 1])
        with b1:
            test_btn = st.button("🔌 Test Connection", use_container_width=True, key="btn_test_rds")
        with b2:
            load_btn = st.button("🚀 Connect & Load", use_container_width=True, key="btn_load_rds")

        # Persist form for UX
        st.session_state.rds_config = {
            "engine_type": engine_type, "host": host, "port": int(port),
            "database": database, "user": user, "password": password, "query": query,
        }

        if test_btn:
            try:
                with st.spinner("Testing RDS connection…"):
                    _ = load_from_rds(engine_type, host, int(port), database, user, password, "SELECT 1 AS ok")
                st.success("✅ Connection successful. Credentials & network reachable.")
            except Exception as e:
                st.error(f"❌ Connection failed: {e}")

        if load_btn:
            try:
                with st.spinner("Running query on RDS…"):
                    df_rds = load_from_rds(engine_type, host, int(port), database, user, password, query)
                if df_rds.empty:
                    st.warning("Query returned no rows.")
                else:
                    st.session_state.raw_df = df_rds
                    st.session_state.data_loaded = True
                    st.session_state.data_source = f"RDS · {engine_type}@{host.split('.')[0]}"
                    st.session_state.uploaded_files_info = [f"RDS: {database}"]
                    st.session_state.rds_connected = True
                    st.session_state.page = "dashboard"
                    st.success(f"Loaded {len(df_rds):,} rows from RDS.")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Load failed: {e}")

    # ── Sample ─────────────────────────────────────────────────────────────
    with tab_sample:
        st.markdown("""
        <div style="background:var(--bg-card);border:1px solid var(--border);
                    border-radius:14px;padding:1.4rem;margin-bottom:1rem;">
            <h3 style="color:#f5c646;margin:0 0 .5rem 0;">🧪 Explore with sample data</h3>
            <p style="color:#a6b4c8;margin:0;font-size:.9rem;">
                Generates 3,000 synthetic transactions across 8 stores so you can play with the dashboard.
            </p>
        </div>""", unsafe_allow_html=True)
        if st.button("🧪 Load Sample Data", use_container_width=True, key="btn_sample"):
            st.session_state.raw_df = _sample_data()
            st.session_state.data_loaded = True
            st.session_state.data_source = "Sample data"
            st.session_state.page = "dashboard"
            st.rerun()

# ────────────────────────────────────────────────────────────────────────────
# Sample data
# ────────────────────────────────────────────────────────────────────────────
def _sample_data(n=3000):
    rng = np.random.default_rng(42)
    stores = [
        ("S070","Gariahat","Sagar SenGupta"),
        ("S071","Park Street","Sagar SenGupta"),
        ("S120","Koramangala","Anitha Rao"),
        ("S121","Indiranagar","Anitha Rao"),
        ("S210","Bandra West","Rahul Mehta"),
        ("S211","Powai","Rahul Mehta"),
        ("S310","CP Delhi","Preeti Arora"),
        ("S311","Gurgaon Cyber","Preeti Arora"),
    ]
    rows = []
    for _ in range(n):
        s = stores[rng.integers(0, len(stores))]
        sold = pd.Timestamp("2026-01-01") + pd.Timedelta(days=int(rng.integers(0,120)))
        mob  = int(7000000000 + rng.integers(0,99999999))
        is_msr = rng.random() < 0.55
        msr_num = mob if is_msr else np.nan
        # Enrollment: 40% same month as shopping, 60% previous
        if is_msr:
            if rng.random() < 0.4:
                enroll = sold  # same month
            else:
                enroll = sold - pd.Timedelta(days=int(rng.integers(30, 180)))
        else:
            enroll = pd.NaT
        sales = int(rng.integers(150,6000))
        rows.append({
            "calendar_day" : sold.strftime("%d-%m-%Y"),
            "store_code"   : s[0],
            "store_name"   : s[1],
            "mobile_number": mob,
            "bill_no"      : int(2000000000 + rng.integers(0,99999999)),
            "nob_ach"      : 1,
            "billed_qty"   : int(rng.integers(1,8)),
            "grs_sales"    : sales,
            "bill_type"    : "Non_Liq" if rng.random()<.85 else "Liq",
            "bill_slab"    : ">_2K" if sales>2000 else "<_2K",
            "msr_number"   : msr_num,
            "msr_month"    : enroll.strftime("%b-%y") if pd.notna(enroll) else np.nan,
            "noc_tagging"  : "Tagged" if rng.random()<.9 else "Untagged",
            "msr_tagging"  : "MSR_MEMBER" if is_msr else "NON_MSR_MEMBER",
            "month_name"   : sold.strftime("%b-%y"),
            "asm_name"     : s[2],
        })
    return pd.DataFrame(rows)

# ────────────────────────────────────────────────────────────────────────────
# Sidebar
# ────────────────────────────────────────────────────────────────────────────
def render_sidebar(df: pd.DataFrame, metrics_df: pd.DataFrame, dd_df: pd.DataFrame) -> dict:
    st.sidebar.markdown("## ⚙️ Controls")

    if st.sidebar.button("🔄 Change / Add Files", use_container_width=True):
        st.session_state.page = "landing"
        st.rerun()

    if st.session_state.uploaded_files_info:
        st.sidebar.caption("📦 Loaded: " + " | ".join(st.session_state.uploaded_files_info))

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔎 Search")
    search = st.sidebar.text_input("Store Code / MSR / Mobile",
                                   placeholder="e.g. S070",
                                   label_visibility="collapsed")

    st.sidebar.markdown("### 🎛️ Filters")
    multi_filters = {}
    for col, label in [("store_name","Store Name"),("asm_name","ASM Name")]:
        if col in df.columns:
            opts = sorted(df[col].dropna().unique().tolist())
            if opts:
                multi_filters[col] = st.sidebar.multiselect(label, opts, default=[])

    st.sidebar.markdown("### 📅 Date Range")
    date_from = date_to = None
    if "shopping_date" in df.columns and df["shopping_date"].notna().any():
        min_d = df["shopping_date"].min().date()
        max_d = df["shopping_date"].max().date()
        dr = st.sidebar.date_input(
            "Shopping Date Range",
            value=(min_d, max_d), min_value=min_d, max_value=max_d,
            format="DD/MM/YYYY",
        )
        if isinstance(dr, (list,tuple)) and len(dr) == 2:
            date_from, date_to = dr

    shop_opts = sorted(df["shopping_month"].dropna().unique().tolist(),
                       key=lambda s: pd.to_datetime(s, format="%b-%y", errors="coerce")) \
                       if "shopping_month" in df.columns else []
    shopping_months = st.sidebar.multiselect("Shopping Month", shop_opts, default=[])

    enroll_opts = sorted(df["enroll_month"].dropna().unique().tolist(),
                         key=lambda s: pd.to_datetime(s, format="%b-%y", errors="coerce")) \
                         if "enroll_month" in df.columns else []
    enroll_months = st.sidebar.multiselect("Enroll Month (MTD)", enroll_opts, default=[])

    report_opts = sorted(df["reporting_month"].dropna().unique().tolist(),
                         key=lambda s: pd.to_datetime(s, format="%b-%y", errors="coerce")) \
                         if "reporting_month" in df.columns else []
    reporting_month = st.sidebar.selectbox("Reporting Month", ["All"] + report_opts)

    # Exports
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📤 Export Summary")
    if not metrics_df.empty:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        st.sidebar.download_button("⬇️ CSV – Summary", to_csv_bytes(metrics_df),
            f"msr_summary_{ts}.csv", "text/csv", use_container_width=True)
        try:
            st.sidebar.download_button("⬇️ Excel – Summary",
                to_excel_bytes(metrics_df, "Summary"),
                f"msr_summary_{ts}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)
        except Exception as e:
            st.sidebar.caption(f"Excel: {e}")

    st.sidebar.markdown("### 📤 Export Drill-Down")
    if not dd_df.empty:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        st.sidebar.download_button("⬇️ CSV – Drill-Down", to_csv_bytes(dd_df),
            f"msr_drilldown_{ts}.csv", "text/csv", use_container_width=True)
        try:
            st.sidebar.download_button("⬇️ Excel – Drill-Down",
                to_excel_bytes(dd_df, "DrillDown"),
                f"msr_drilldown_{ts}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)
        except Exception as e:
            st.sidebar.caption(f"Excel: {e}")

    return {
        "multi"           : multi_filters,
        "date_from"       : date_from,
        "date_to"         : date_to,
        "shopping_months" : shopping_months,
        "enroll_months"   : enroll_months,
        "reporting_month" : reporting_month,
        "search"          : search,
    }

# ────────────────────────────────────────────────────────────────────────────
# KPIs
# ────────────────────────────────────────────────────────────────────────────
def render_kpis(metrics_df, filtered_df, mtd_label):
    total    = int(metrics_df["Total NOC"].sum())            if not metrics_df.empty else 0
    msr_mem  = int(metrics_df["Unique MSR Members"].sum())   if not metrics_df.empty else 0
    mtd_reg  = int(metrics_df["MTD Enrollment"].sum())       if not metrics_df.empty else 0
    gt2k     = int(metrics_df["Bills >2K"].sum())            if not metrics_df.empty else 0
    conv     = (mtd_reg / total * 100) if total > 0 else 0.0
    n_stores = int(metrics_df.shape[0])

    c = st.columns(4, gap="medium")
    with c[0]: kpi("Total Unique NOC", f"{total:,}",
                   f"Across {n_stores} stores", "blue")
    with c[1]: kpi("Members Shopped", f"{msr_mem:,}",
                   f"MTD Enrollment: {mtd_reg:,} ({mtd_label})", "gold")
    with c[2]: kpi("Conversion %", f"{conv:.1f}%",
                   "MTD Enrollment / Total NOC", "green")
    with c[3]: kpi("Bills >₹2K (Non-MSR)", f"{gt2k:,}",
                   "Non-MSR bills only", "red")

# ────────────────────────────────────────────────────────────────────────────
# Charts — dark themed
# ────────────────────────────────────────────────────────────────────────────
def _layout(fig, h=380):
    fig.update_layout(
        height=h, margin=dict(l=10,r=10,t=44,b=10),
        plot_bgcolor="#111827", paper_bgcolor="#1a2233",
        font=dict(family="Inter,Helvetica,Arial", color="#e8eef5", size=12),
        title_font=dict(size=14, color="#f5c646"),
        hoverlabel=dict(bgcolor="#0B2545", font_color="#fff",
                        bordercolor="#4a8fe0"),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center",
                    bgcolor="rgba(0,0,0,0)", font=dict(color="#e8eef5")),
    )
    fig.update_xaxes(showgrid=False, linecolor="#2a3447",
                     tickfont=dict(color="#a6b4c8"),
                     title_font=dict(color="#a6b4c8"))
    fig.update_yaxes(gridcolor="#2a3447", linecolor="#2a3447",
                     tickfont=dict(color="#a6b4c8"),
                     title_font=dict(color="#a6b4c8"))
    return fig

def render_charts(metrics_df, filtered_df):
    if metrics_df.empty: return
    top = metrics_df.head(10).copy()
    top["label"] = top["Store Name"] + " (" + top["Store Code"] + ")"

    c1, c2 = st.columns((1.4,1))
    with c1:
        fig = px.bar(top.sort_values("Total NOC"), x="Total NOC", y="label",
                     orientation="h", title="Top 10 Stores – Total NOC",
                     color="Total NOC", color_continuous_scale=SEQ_BLUE,
                     text="Total NOC")
        fig.update_traces(textposition="outside", cliponaxis=False,
                          textfont_color="#e8eef5")
        fig.update_layout(coloraxis_showscale=False,
                          yaxis_title=None, xaxis_title=None)
        st.plotly_chart(_layout(fig, 430), use_container_width=True)
    with c2:
        msr_t = int(metrics_df["Unique MSR Members"].sum())
        non_t = int(metrics_df["Unique Non-MSR Members"].sum())
        fig = go.Figure(data=[go.Pie(
            labels=["MSR Members","Non-MSR"],
            values=[msr_t, non_t], hole=0.6,
            marker=dict(colors=[PALETTE["gold"], PALETTE["grey"]],
                        line=dict(color="#0a0e1a", width=2)),
            textinfo="label+percent",
            textfont=dict(color="#fff"),
        )])
        fig.update_layout(title="MSR vs Non-MSR Split",
                          annotations=[dict(text=f"<b>{msr_t:,}</b><br>MSR",
                                            x=0.5, y=0.5, showarrow=False,
                                            font=dict(size=14, color="#f5c646"))])
        st.plotly_chart(_layout(fig, 430), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        long = top.melt(id_vars=["label"],
                        value_vars=["Unique MSR Members","Unique Non-MSR Members"],
                        var_name="Segment", value_name="Count")
        fig = px.bar(long, x="label", y="Count", color="Segment", barmode="group",
                     title="MSR vs Non-MSR by Store (Top 10)",
                     color_discrete_map={"Unique MSR Members": PALETTE["gold"],
                                         "Unique Non-MSR Members": PALETTE["grey"]})
        fig.update_layout(xaxis_title=None, yaxis_title=None, xaxis_tickangle=-30)
        st.plotly_chart(_layout(fig), use_container_width=True)
    with c4:
        long2 = top.melt(id_vars=["label"], value_vars=["Bills >2K","Bills ≤2K"],
                         var_name="Slab", value_name="Count")
        fig = px.bar(long2, x="label", y="Count", color="Slab", barmode="stack",
                     title="Bills >2K vs ≤2K (Non-MSR, Top 10)",
                     color_discrete_map={"Bills >2K": PALETTE["blue"],
                                         "Bills ≤2K": PALETTE["teal"]})
        fig.update_layout(xaxis_title=None, yaxis_title=None, xaxis_tickangle=-30)
        st.plotly_chart(_layout(fig), use_container_width=True)

    # Monthly conversion trend
    if "shopping_month" in filtered_df.columns and filtered_df["shopping_month"].notna().any():
        trend = (
            filtered_df.groupby(["shopping_period","shopping_month"])
            .apply(lambda g: pd.Series({
                "Total": g["mobile_number"].nunique(),
                "MTD"  : g.loc[g["is_mtd_enrollment"],"mobile_number"].nunique()
                         if "is_mtd_enrollment" in g.columns else 0,
            }), include_groups=False).reset_index().sort_values("shopping_period")
        )
        trend["Conversion %"] = np.where(trend["Total"] > 0,
                                          trend["MTD"] / trend["Total"] * 100, 0).round(2)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend["shopping_month"], y=trend["Conversion %"],
            mode="lines+markers", name="Conversion %",
            line=dict(color=PALETTE["blue"], width=3),
            marker=dict(size=11, color=PALETTE["gold"],
                        line=dict(width=2, color="#0a0e1a")),
            fill="tozeroy", fillcolor="rgba(74,143,224,.12)",
        ))
        fig.update_layout(title="Monthly Conversion Trend",
                          yaxis_title="Conversion %", xaxis_title=None)
        st.plotly_chart(_layout(fig), use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# Table display
# ────────────────────────────────────────────────────────────────────────────
def render_table(metrics_df, label="Store-level"):
    if metrics_df.empty:
        st.info("No records match the current filters.")
        return
    display = metrics_df.copy().rename(columns=STORE_DISPLAY_RENAME)
    conv_col = "Member Enrollment Conversion %"
    if conv_col in display.columns:
        display[conv_col] = display[conv_col].apply(lambda v: f"{v:.2f}%")
    styled = style_metrics(display)
    st.dataframe(styled, use_container_width=True, height=480)

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    dl1, dl2 = st.columns(2)
    with dl1:
        try:
            pdf_b = to_pdf_bytes(display, "Store Level Metrics")
            st.download_button(
                "⬇️ Download PDF – Store Metrics", pdf_b,
                f"store_metrics_{ts}.pdf", "application/pdf",
                use_container_width=True, key=f"pdf_store_{ts}"
            )
        except Exception as e:
            st.caption(f"PDF unavailable: {e}")

def render_drilldown_table(dd_df):
    if dd_df.empty:
        st.info("No drill-down data for current filters.")
        return
    display = dd_df.copy().rename(columns=DRILL_DISPLAY_RENAME)
    conv_col = "Member Enrollment Conversion %"
    if conv_col in display.columns:
        display[conv_col] = display[conv_col].apply(lambda v: f"{v:.2f}%")
    styled = style_metrics(display)
    st.dataframe(styled, use_container_width=True, height=540)

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    dl1, dl2 = st.columns(2)
    with dl1:
        try:
            pdf_b = to_pdf_bytes(display, "Day Level Metrics")
            st.download_button(
                "⬇️ Download PDF – Day Metrics", pdf_b,
                f"day_metrics_{ts}.pdf", "application/pdf",
                use_container_width=True, key=f"pdf_day_{ts}"
            )
        except Exception as e:
            st.caption(f"PDF unavailable: {e}")

# ────────────────────────────────────────────────────────────────────────────
# Dashboard page
# ────────────────────────────────────────────────────────────────────────────
def dashboard_page():
    raw = st.session_state.raw_df
    if raw is None or raw.empty:
        st.warning("No data loaded.")
        st.session_state.page = "landing"
        st.rerun()
        return

    try:
        df = process_data(raw)
    except Exception as e:
        st.error(f"Processing failed: {e}")
        if st.button("← Back"):
            st.session_state.page = "landing"; st.rerun()
        return

    render_hero("Store-level Customer & MSR Performance")

    if df.attrs.get("dropped_untagged", 0):
        st.caption(f"ℹ️ Removed {df.attrs['dropped_untagged']:,} 'Untagged' NOC rows.")

    # Diagnostics panel — open automatically when MTD is 0
    render_diagnostics(df)

    tab_summary, tab_drill = st.tabs(["📊 Summary Dashboard",
                                       "🔍 Drill-Down (Day × Store)"])

    with tab_summary:
        metrics_all = calculate_metrics(df)
        dd_all      = calculate_drilldown(df)
        filters     = render_sidebar(df, metrics_all, dd_all)

        filtered = apply_filters(df, filters)
        if filtered.empty:
            st.warning("No rows match the current filters.")
            return

        rep_month = filters.get("reporting_month", "All")
        if rep_month and rep_month != "All":
            mtd_label = rep_month
        elif filters.get("enroll_months"):
            mtd_label = filters["enroll_months"][-1]
        else:
            cur = _latest_period(filtered)
            mtd_label = cur.strftime("%b-%y") if cur else "—"

        metrics = calculate_metrics(filtered, mtd_month_label=mtd_label)
        dd_df   = calculate_drilldown(filtered, mtd_month_label=mtd_label)

        section("Executive Summary", "📌")
        render_kpis(metrics, filtered, mtd_label)

        section("Visual Analytics", "📈")
        render_charts(metrics, filtered)

        section("Store-level Metrics Table", "🏬")
        st.caption(
            f"Showing **{len(metrics):,}** stores · "
            f"**{len(filtered):,}** transactions · "
            f"**{filtered['mobile_number'].nunique():,}** unique customers · "
            f"MTD Month: **{mtd_label}**"
        )
        render_table(metrics)

    with tab_drill:
        section("Day-wise × Store-wise Drill-Down", "🔍")
        st.markdown("""
        This table shows **day-wise** and **store-wise** breakdown of:
        Total NOC, Enrollment (MTD), Unique MSR/Non-MSR members, Conversion %,
        and Bills >₹2K / ≤₹2K (non-MSR bills only).
        """)

        try:
            filtered_drill = filtered
            dd_df_display  = dd_df
        except NameError:
            filtered_drill = df
            dd_df_display  = calculate_drilldown(df)

        stores_available = sorted(dd_df_display["Store Code"].dropna().unique().tolist()) \
            if not dd_df_display.empty and "Store Code" in dd_df_display.columns else []
        sel_stores = st.multiselect("Filter by Store (Drill-Down only)",
                                    ["All"] + stores_available, default=["All"])
        if sel_stores and "All" not in sel_stores and not dd_df_display.empty:
            dd_df_display = dd_df_display[dd_df_display["Store Code"].isin(sel_stores)]

        st.caption(f"Showing **{len(dd_df_display):,}** rows")
        render_drilldown_table(dd_df_display)

        c1, c2 = st.columns(2)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        with c1:
            st.download_button("⬇️ Export CSV", to_csv_bytes(dd_df_display),
                               f"drilldown_{ts}.csv", "text/csv",
                               use_container_width=True)
        with c2:
            try:
                st.download_button("⬇️ Export Excel",
                                   to_excel_bytes(dd_df_display, "DrillDown"),
                                   f"drilldown_{ts}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)
            except Exception as e:
                st.caption(f"Excel unavailable: {e}")

# ────────────────────────────────────────────────────────────────────────────
# Router
# ────────────────────────────────────────────────────────────────────────────
def main():
    if st.session_state.page == "landing" or not st.session_state.data_loaded:
        landing_page()
    else:
        dashboard_page()

if __name__ == "__main__":
    main()
