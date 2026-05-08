"""
MySpencers Rewards (MSR) Dashboard — Spencer's Red & White Edition
==================================================================
Features:
  - Light mode only — Spencer's Retail red & white theme
  - Public viewer mode — anyone with the Streamlit URL can see the insights
  - **Admin authentication** (see auth.py) — only signed-in admins can
    upload new CSVs and manage the data table
  - Multi-file upload & consolidation (admin only)
  - **Persistent SQLite storage** — every uploaded CSV is auto-appended to a
    local `msr_data.db` table. All KPIs, charts and drill-downs ALWAYS run on
    the full accumulated dataset (today's upload + every previous day).
  - Date normalisation (dd-mm-yyyy) on ingestion
  - **Indian Standard Time (IST)** clock shown in the header; Last-Day
    metrics use IST to decide what "today" means.
  - Enrollment logic:
       * MTD Enrollment  = MSR customers whose calendar_day's mmm-yy == msr_month's mmm-yy
       * Previous Enroll = MSR customers whose calendar_day > msr_month (already members)
       * Last Day        = most recent calendar_day ≤ today (IST)
  - Conversion %  = unique MSR members enrolled this month / total unique customer base
  - Bills >2K / ≤2K = count of NON-MSR bills only (MSR member bills excluded)
  - Export CSV / Excel / PDF

Run:
    pip install streamlit pandas plotly openpyxl xlsxwriter reportlab
    streamlit run msr_dashboard.py
"""

from __future__ import annotations

import hashlib
import io
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import auth  # ← separate admin authentication module (auth.py)

# ────────────────────────────────────────────────────────────────────────────
# Indian Standard Time helpers
# ────────────────────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Current wall-clock time in India Standard Time."""
    return datetime.now(IST)


def today_ist() -> pd.Timestamp:
    """Today's date (IST), as a naive pandas Timestamp at midnight."""
    n = now_ist()
    return pd.Timestamp(year=n.year, month=n.month, day=n.day)

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
# Light-mode CSS — Spencer's Retail Red & White theme (matches AMS Migration)
# ────────────────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
    :root {
        --bg:         #ffffff;
        --bg-elev:    #fafafa;
        --bg-card:    #ffffff;
        --bg-input:   #ffffff;
        --bg-soft:    #fff5f5;
        --border:     #e6e6e6;
        --border-lt:  #d0d0d0;
        --text:       #1a1a1a;
        --text-mut:   #4a4a4a;
        --text-dim:   #7a7a7a;
        --red:        #C8102E;
        --red-dk:     #9e0c24;
        --red-lt:     #ec1c3c;
        --red-soft:   #fde8ec;
        --green:      #2e7d32;
        --amber:      #c77700;
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
        background: var(--red-soft) !important;
        color: var(--red-dk) !important;
        padding: 2px 6px;
        border-radius: 4px;
    }

    /* ── Sidebar ───────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: #ffffff !important;
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
        color: var(--red) !important;
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

    /* ── Form inputs (universal light) ─────────────────────────────── */
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
        background: var(--red) !important;
        color: #fff !important;
        border-radius: 6px !important;
    }
    /* dropdown menu (popover) */
    [data-baseweb="popover"], [role="listbox"] {
        background: #ffffff !important;
        border: 1px solid var(--border-lt) !important;
    }
    [role="option"] {
        color: var(--text) !important;
    }
    [role="option"]:hover {
        background: var(--red-soft) !important;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        background: var(--bg-elev) !important;
        border: 1.5px dashed var(--red-lt) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
    }
    [data-testid="stFileUploader"] * { color: var(--text) !important; }
    [data-testid="stFileUploaderDropzone"] {
        background: #ffffff !important;
        border-color: var(--red-lt) !important;
    }

    /* ── Buttons ───────────────────────────────────────────────────── */
    .stButton > button {
        background: linear-gradient(135deg, var(--red) 0%, var(--red-dk) 100%) !important;
        color: #fff !important;
        border: 1px solid var(--red-dk) !important;
        border-radius: 8px !important;
        padding: .55rem 1.1rem !important;
        font-weight: 600 !important;
        transition: all .2s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 18px rgba(200,16,46,.28);
        background: linear-gradient(135deg, var(--red-lt) 0%, var(--red) 100%) !important;
    }
    .stButton > button:disabled {
        background: #e8e8e8 !important;
        color: var(--text-dim) !important;
        border-color: var(--border-lt) !important;
        cursor: not-allowed !important;
    }
    .stDownloadButton > button {
        background: #ffffff !important;
        color: var(--red) !important;
        border: 1.5px solid var(--red) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        width: 100% !important;
    }
    .stDownloadButton > button:hover {
        background: var(--red) !important;
        color: #fff !important;
    }

    /* ── Hero banner ───────────────────────────────────────────────── */
    .hero {
        background: linear-gradient(135deg, #C8102E 0%, #9e0c24 100%);
        color: #fff; padding: 1.5rem 1.9rem; border-radius: 14px;
        margin-bottom: 1.2rem; border: 1px solid rgba(255,255,255,.08);
        box-shadow: 0 8px 24px rgba(200,16,46,.18);
        display: flex; align-items: center; justify-content: space-between;
    }
    .hero h1 { margin:0; font-size:1.65rem; font-weight:700; letter-spacing:-0.5px; color:#fff; }
    .hero .tag { font-size:0.88rem; opacity:0.92; margin-top:0.25rem; color:#fff5f5; }
    .hero .badge {
        background: rgba(255,255,255,0.18); border:1px solid rgba(255,255,255,0.32);
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
        box-shadow: 0 1px 3px rgba(0,0,0,.04);
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 22px rgba(200,16,46,.10);
        border-color: var(--red-lt);
    }
    .kpi-label {
        font-size:.76rem; text-transform:uppercase; letter-spacing:1.2px;
        color:var(--text-mut); font-weight:600; margin-bottom:.45rem;
    }
    .kpi-value { font-size:1.95rem; font-weight:800; color:var(--text); line-height:1.1; }
    .kpi-sub   { font-size:.78rem; color:var(--text-dim); margin-top:.4rem; }
    .kpi-accent-blue  { border-top:4px solid var(--red); }
    .kpi-accent-gold  { border-top:4px solid #1a1a1a; }
    .kpi-accent-green { border-top:4px solid var(--green); }
    .kpi-accent-red   { border-top:4px solid var(--red); }

    /* ── Section titles ────────────────────────────────────────────── */
    .section-title {
        font-size:1.08rem; font-weight:700; color:var(--red);
        margin:1.6rem 0 .75rem 0; padding-bottom:.45rem;
        border-bottom: 1px solid var(--border); display:flex; align-items:center; gap:.55rem;
    }
    .section-title .dot {
        width:9px; height:9px; border-radius:50%;
        background: var(--red);
        box-shadow: 0 0 6px rgba(200,16,46,.4);
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
        color: var(--red) !important;
        border-bottom: 2px solid var(--red) !important;
    }

    /* ── DataFrame ─────────────────────────────────────────────────── */
    [data-testid="stDataFrame"],
    [data-testid="stDataFrameResizable"] {
        background: #ffffff !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }
    [data-testid="stDataFrame"] * {
        color: var(--text) !important;
    }

    /* Alerts / info / warning / success / error boxes */
    [data-testid="stAlert"] {
        background: var(--bg-elev) !important;
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
    [data-testid="stExpander"] summary { color: var(--red) !important; font-weight: 600 !important; }

    /* Plotly container */
    [data-testid="stPlotlyChart"] {
        background: #ffffff !important;
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
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapseButton"] button,
    button[kind="headerNoPadding"] {
        visibility: visible !important;
        display: inline-flex !important;
        background: #ffffff !important;
        color: var(--red) !important;
        border: 1px solid var(--border-lt) !important;
        border-radius: 6px !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="collapsedControl"] svg {
        color: var(--red) !important;
        fill: var(--red) !important;
    }

    /* Floating pill shown when the sidebar IS collapsed */
    [data-testid="collapsedControl"] {
        visibility: visible !important;
        display: block !important;
        position: fixed !important;
        top: .9rem !important;
        left: .9rem !important;
        z-index: 999999 !important;
        background: linear-gradient(135deg, var(--red) 0%, var(--red-dk) 100%) !important;
        border: 1px solid var(--red-dk) !important;
        border-radius: 8px !important;
        padding: .35rem .55rem !important;
        box-shadow: 0 6px 16px rgba(200,16,46,.32) !important;
    }
    [data-testid="collapsedControl"] button {
        background: transparent !important;
        color: #fff !important;
    }
    [data-testid="collapsedControl"] svg {
        color: #fff !important;
        fill: #fff !important;
    }
    [data-testid="collapsedControl"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 22px rgba(200,16,46,.40) !important;
    }

    /* Scrollbar (webkit) */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: #f5f5f5; }
    ::-webkit-scrollbar-thumb { background: var(--border-lt); border-radius: 5px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--red); }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Palettes (Spencer's red & white)
PALETTE   = {
    "navy":"#1a1a1a","blue":"#C8102E","gold":"#1a1a1a","gold_lt":"#9e0c24",
    "teal":"#2e7d32","red":"#C8102E","grey":"#8A8A8A",
}
SEQ_RED   = ["#fde8ec","#f9c0c8","#f198a4","#e96f80","#df4357","#C8102E","#9e0c24","#700718"]
SEQ_BLUE  = SEQ_RED  # alias for chart code that references SEQ_BLUE
SEQ_GOLD  = ["#cccccc","#b3b3b3","#999999","#808080","#666666","#4d4d4d","#333333","#1a1a1a"]

REQUIRED_COLS = [
    "store_code","store_name","mobile_number","bill_no",
    "grs_sales","msr_number","msr_month","noc_tagging","msr_tagging","asm_name",
]
DATE_COLS = ["calendar_day","month_name"]

# ────────────────────────────────────────────────────────────────────────────
# Store Director directory (sourced from store_director.csv)
# Maps Store Code → Store Director Name. Used by the Detailed View tab so the
# director column auto-populates. Codes are matched case-insensitively and
# trimmed of whitespace before lookup. Trailing spaces in names from the
# source CSV are preserved exactly as supplied.
# ────────────────────────────────────────────────────────────────────────────
STORE_DIRECTORS: dict[str, str] = {
    "D070": "Raju Ghosh",
    "D087": "Bikash Bhagat",
    "D089": "Jayanta Karmakar",
    "D104": "Chinmay Mondal",
    "D166": "Swapan Sen",
    "D202": "Partha Sarathi Banerjee",
    "D263": "Shoaib Ahmad",
    "D265": "Krishneshwar Kumar Tiwari",
    "D266": "Shadab Ahmad",
    "D269": "Shankar Sah",
    "D270": "Sagar Chaturvedi",
    "D278": "Vinay Tiwari",
    "D333": "Karuna Shanker",
    "D345": "Ajay Kumar",
    "D346": "Amar Srivastava",
    "D354": "Sanju Medda",
    "D357": "Tariq Mahmood",
    "D359": "Bankin Mondal",
    "D360": "Karuna Shanker",
    "D362": "Shivam Singh (TL-Temprory)",
    "D365": "Amit Bhuiya",
    "D371": "Mahadeb Das",
    "D374": "Suman Dutta",
    "D375": "Rajesh Mistry",
    "D378": "Sandip Sikdar",
    "D379": "Sanjoy Rajbanshi",
    "D386": "Neeraj Kumar Dwivedi",
    "D388": "Suman Das",
    "D390": "Km Sonia",
    "D391": "Loknath Mondal(Dm)",
    "D394": "Bheem Singh",
    "D400": "Rajkumar Banerjee",
    "D410": "Priyanka Chatterjee",
    "D418": "Sardha Pradhan",
    "H009": "Sachidanand Prasad",
    "H012": "Rohit Karmakar",
    "H013": "Somnath Singha",
    "H030": "Jitendra Kumar Yadav",
    "H042": "Prabuna Chhetri",
    "H048": "Virendra Yadav",
    "H049": "Md Noor Asif",
    "H069": "Debojit Roy Bardhan",
    "H072": "Sayantan Mishra",
    "H081": "Arindam Chakraborty",
    "H090": "Amit Shaw",
    "H100": "Sandeep Sharma",
    "H104": "Ramakrishna",
    "H115": "Imon Dutta",
    "H126": "Jitendra Rajput",
    "H129": "Jai Kanojia",
    "H139": "Bimalendu Das",
    "H143": "Sumit Sharma",
    "M053": "Trisha",
    "S004": "Sarwar Hussain",
    "S040": "Vyas Mani Pandey",
    "S041": "Asit Senapati",
    "S046": "Sailen Chakraborty",
    "S053": "Shiv Kumar Upadhyay",
    "S055": "Satyendra Kumar",
    "S056": "Biswajit Roy",
    "S059": "Kuntal Das",
    "S060": "Sk Aktar Hossain",
    "S062": "Atanu Sarkar",
    "S064": "Tirtha Sen",
    "S065": "Bibhas Das",
    "S066": "Bapi Bose",
    "S070": "Surendra Nath Dey",
    "S077": "Arup Manna",
    "S080": "Subhendu Ghosh",
    "S083": "Amod Kumar",
    "S085": "Subhajit Palit",
    "S088": "Rajesh Kumar Dubey",
    "S089": "Uttam Chaubey",
    "S090": "Rajib Ghosh",
    "S091": "Santosh Patel",
    "S095": "Chandan Paul",
    "S100": "Jhuma Sengupta",
    "S106": "Vikram Kumar Singh",
    "S110": "Ratnakar Dwivedi",
    "S111": "Sudipta Das",
    "S113": "Shyam Sundar Yadav",
    "S117": "Mayur Dilipkumar Mudiraj",
    "S119": "Purka Thapa",
    "S120": "Shisir Dhar",
    "S121": "Mohd Anees",
    "V010": "Harishanker Patel",
    "X011": "Salma Khatun",
    "X015": "Anowar Khan",
    "X017": "Dipankar Purkait",
    "X019": "Shyamal Halder",
}


def lookup_store_director(store_code: str) -> str:
    """Return the Store Director name for a given store code, or '-' if unknown."""
    if store_code is None:
        return "-"
    key = str(store_code).strip().upper()
    return STORE_DIRECTORS.get(key, "-")

# ────────────────────────────────────────────────────────────────────────────
# 💾 Persistent storage (SQLite)
# ────────────────────────────────────────────────────────────────────────────
# Every uploaded CSV is appended into `msr_transactions` inside msr_data.db.
# All downstream analysis (KPIs, charts, drill-down) reads from this table, so
# a daily upload simply grows the dataset automatically.
# ────────────────────────────────────────────────────────────────────────────
DB_PATH         = Path("msr_data.db")
DATA_TABLE      = "msr_transactions"
UPLOAD_LOG_TBL  = "upload_log"
# Composite key used to detect duplicate rows across uploads.
# (These four together uniquely identify a transaction line in practice.)
DEDUP_KEYS      = ["bill_no", "mobile_number", "calendar_day", "store_code"]


def _db_connect() -> sqlite3.Connection:
    """Open a SQLite connection (creates file on first call)."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    # Improve concurrency & speed a bit
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous  = NORMAL;")
    return conn


def init_storage() -> None:
    """Create the upload_log table if missing. Data table is created lazily
    on first append (so its schema matches whatever the user's CSV contains)."""
    with _db_connect() as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {UPLOAD_LOG_TBL} (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                filename         TEXT,
                file_hash        TEXT,
                upload_timestamp TEXT,
                rows_in_file     INTEGER,
                rows_appended    INTEGER,
                rows_duplicate   INTEGER
            )
        """)
        conn.commit()


def _file_hash(file_bytes: bytes) -> str:
    """MD5 of the raw file bytes — lets us detect an identical re-upload."""
    return hashlib.md5(file_bytes).hexdigest()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
        (table,),
    )
    return cur.fetchone() is not None


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase, strip, underscore — so schema stays consistent across uploads."""
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out


def append_upload_to_db(df: pd.DataFrame, filename: str,
                        file_bytes: bytes) -> dict:
    """Append a freshly-uploaded DataFrame into the persistent table.

    Behaviour:
      • Column names are normalised (lower/strip/underscore) first.
      • Rows whose (bill_no, mobile_number, calendar_day, store_code) already
        exist in the table are skipped — so re-uploading the same file is safe.
      • Adds `_source_file` and `_upload_ts` tracking columns.
      • Returns a summary dict: {rows_in_file, rows_appended, rows_duplicate}.
    """
    if df is None or df.empty:
        return {"rows_in_file": 0, "rows_appended": 0, "rows_duplicate": 0}

    df = _normalise_columns(df)

    # Add tracking columns
    df["_source_file"] = filename
    df["_upload_ts"]   = datetime.now().isoformat(timespec="seconds")

    rows_in_file = len(df)
    rows_duplicate = 0

    with _db_connect() as conn:
        # If the data table already exists, filter out rows whose dedup keys
        # are already present — this is the "safe re-upload" behaviour.
        if _table_exists(conn, DATA_TABLE):
            existing_cols = [r[1] for r in conn.execute(
                f"PRAGMA table_info({DATA_TABLE});"
            ).fetchall()]
            usable_keys = [k for k in DEDUP_KEYS
                           if k in df.columns and k in existing_cols]
            if usable_keys:
                # Build an in-memory set of existing composite keys
                existing = pd.read_sql(
                    f"SELECT {', '.join(usable_keys)} FROM {DATA_TABLE}",
                    conn,
                )
                if not existing.empty:
                    exist_tuples = set(map(tuple, existing.astype(str).values))
                    cand_tuples  = list(map(tuple, df[usable_keys].astype(str).values))
                    dup_mask = pd.Series(
                        [t in exist_tuples for t in cand_tuples],
                        index=df.index,
                    )
                    rows_duplicate = int(dup_mask.sum())
                    df = df.loc[~dup_mask].copy()

            # Align columns with existing table (add missing cols as NULL,
            # ignore extra cols in the upload that aren't in the table).
            for c in existing_cols:
                if c not in df.columns:
                    df[c] = None
            df = df[[c for c in existing_cols if c in df.columns]]

        rows_appended = len(df)
        if rows_appended > 0:
            df.to_sql(DATA_TABLE, conn, if_exists="append", index=False)

        # Log the upload
        conn.execute(f"""
            INSERT INTO {UPLOAD_LOG_TBL}
                (filename, file_hash, upload_timestamp,
                 rows_in_file, rows_appended, rows_duplicate)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            filename,
            _file_hash(file_bytes) if file_bytes else None,
            datetime.now().isoformat(timespec="seconds"),
            rows_in_file,
            rows_appended,
            rows_duplicate,
        ))
        conn.commit()

    return {
        "rows_in_file"  : rows_in_file,
        "rows_appended" : rows_appended,
        "rows_duplicate": rows_duplicate,
    }


def load_all_stored_data() -> pd.DataFrame:
    """Return the entire accumulated dataset. Empty DF if nothing stored yet."""
    if not DB_PATH.exists():
        return pd.DataFrame()
    with _db_connect() as conn:
        if not _table_exists(conn, DATA_TABLE):
            return pd.DataFrame()
        return pd.read_sql(f"SELECT * FROM {DATA_TABLE}", conn)


def get_storage_summary() -> dict:
    """Quick stats for the UI banner."""
    summary = {
        "exists"     : False,
        "rows"       : 0,
        "uploads"    : 0,
        "files"      : [],
        "min_date"   : None,
        "max_date"   : None,
        "db_size_kb" : 0,
    }
    if not DB_PATH.exists():
        return summary
    summary["db_size_kb"] = round(DB_PATH.stat().st_size / 1024, 1)
    with _db_connect() as conn:
        if not _table_exists(conn, DATA_TABLE):
            return summary
        summary["exists"] = True
        summary["rows"] = int(conn.execute(
            f"SELECT COUNT(*) FROM {DATA_TABLE}"
        ).fetchone()[0])
        if _table_exists(conn, UPLOAD_LOG_TBL):
            summary["uploads"] = int(conn.execute(
                f"SELECT COUNT(*) FROM {UPLOAD_LOG_TBL}"
            ).fetchone()[0])
            summary["files"] = [r[0] for r in conn.execute(
                f"SELECT DISTINCT filename FROM {UPLOAD_LOG_TBL} "
                f"ORDER BY id DESC LIMIT 20"
            ).fetchall()]
        # Try to pull min/max calendar_day if present
        try:
            row = conn.execute(
                f"SELECT MIN(calendar_day), MAX(calendar_day) FROM {DATA_TABLE}"
            ).fetchone()
            summary["min_date"], summary["max_date"] = row
        except Exception:
            pass
    return summary


def get_upload_log() -> pd.DataFrame:
    """Return the upload history as a DataFrame (newest first)."""
    if not DB_PATH.exists():
        return pd.DataFrame()
    with _db_connect() as conn:
        if not _table_exists(conn, UPLOAD_LOG_TBL):
            return pd.DataFrame()
        return pd.read_sql(
            f"SELECT id, filename, upload_timestamp, rows_in_file, "
            f"rows_appended, rows_duplicate, file_hash "
            f"FROM {UPLOAD_LOG_TBL} ORDER BY id DESC",
            conn,
        )


def clear_storage() -> None:
    """Drop the data table and wipe the upload log."""
    if not DB_PATH.exists():
        return
    with _db_connect() as conn:
        conn.execute(f"DROP TABLE IF EXISTS {DATA_TABLE}")
        conn.execute(f"DELETE FROM {UPLOAD_LOG_TBL}")
        conn.commit()


def deduplicate_storage() -> int:
    """Remove duplicate rows using the DEDUP_KEYS. Returns rows removed."""
    df = load_all_stored_data()
    if df.empty:
        return 0
    keys = [k for k in DEDUP_KEYS if k in df.columns]
    if not keys:
        return 0
    before = len(df)
    df = df.drop_duplicates(subset=keys, keep="first")
    removed = before - len(df)
    if removed > 0:
        with _db_connect() as conn:
            df.to_sql(DATA_TABLE, conn, if_exists="replace", index=False)
            conn.commit()
    return removed


# Initialise the DB on import so tables exist before first use
init_storage()

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
        "_auto_loaded_from_storage": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Auto-load persistent storage on first app run ──────────────────
    # If there's already data in msr_data.db, load it silently so the user
    # opens directly onto the dashboard instead of the empty landing page.
    if (not st.session_state._auto_loaded_from_storage
            and not st.session_state.data_loaded):
        try:
            _sum = get_storage_summary()
            if _sum["exists"] and _sum["rows"] > 0:
                _full = load_all_stored_data()
                _analyse = _full.drop(
                    columns=[c for c in ["_source_file", "_upload_ts"]
                             if c in _full.columns],
                    errors="ignore",
                )
                st.session_state.raw_df              = _analyse
                st.session_state.data_loaded         = True
                st.session_state.data_source         = "Persistent Storage"
                st.session_state.uploaded_files_info = [f"DB ({_sum['rows']:,} rows)"]
                st.session_state.page                = "dashboard"
        except Exception:
            # If something goes wrong, just fall back to the landing page
            pass
        st.session_state._auto_loaded_from_storage = True
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

    # ── Last Day logic (IST) ────────────────────────────────────────────
    # "Last day" = most recent calendar_day in the data that is on/before
    # today in IST. Using IST ensures the cut-off matches what admins in
    # India see on the wall-clock, regardless of where the server runs.
    last_day_ts: Optional[pd.Timestamp] = None
    last_day_mask = pd.Series(False, index=df.index)
    if "shopping_date" in df.columns and df["shopping_date"].notna().any():
        today = today_ist()
        valid_dates = df["shopping_date"].where(df["shopping_date"] <= today)
        if valid_dates.notna().any():
            last_day_ts = valid_dates.max().normalize()
            last_day_mask = (df["shopping_date"].dt.normalize() == last_day_ts)

    # Core counts
    total_cust = df.groupby(group_cols)["mobile_number"].nunique().rename("Total NOC")

    # NEW: Last Day NOC (unique customers on the last day, per store)
    if last_day_mask.any():
        last_day_noc = (df[last_day_mask]
                        .groupby(group_cols)["mobile_number"].nunique()
                        .rename("Last Day NOC"))
    else:
        last_day_noc = pd.Series(dtype=int, name="Last Day NOC")

    # NEW: Last Day Member Enrollment — customers on the last day whose
    # msr_month (dd-mm-yyyy) equals that day's calendar_day.
    # The existing `is_day_enrollment` flag already encodes exactly this.
    if last_day_mask.any() and "is_day_enrollment" in df.columns:
        last_day_enroll = (df[last_day_mask & df["is_day_enrollment"]]
                           .groupby(group_cols)["mobile_number"].nunique()
                           .rename("Last Day Member Enrollment"))
    else:
        last_day_enroll = pd.Series(dtype=int, name="Last Day Member Enrollment")

    # NEW: Last Day Non Member Shopped — unique non-MSR customers on the
    # last day. Required for the Detailed View tab.
    if last_day_mask.any():
        last_day_non_member = (
            df[last_day_mask & ~df["is_msr"]]
              .groupby(group_cols)["mobile_number"].nunique()
              .rename("Last Day Non Member Shopped")
        )
    else:
        last_day_non_member = pd.Series(dtype=int, name="Last Day Non Member Shopped")

    mtd        = df[mtd_mask].groupby(group_cols)["mobile_number"].nunique().rename("MTD Enrollment")
    msr_cnt    = df[df["is_msr"]].groupby(group_cols)["mobile_number"].nunique().rename("Unique MSR Members")
    non_msr    = df[~df["is_msr"]].groupby(group_cols)["mobile_number"].nunique().rename("Unique Non-MSR Members")

    # NEW Bills logic — count NON-MSR bills only (MSR member bills excluded)
    non_msr_df = df[~df["is_msr"]].copy()
    gt_df = non_msr_df[non_msr_df["grs_sales"] >  2000]
    lt_df = non_msr_df[non_msr_df["grs_sales"] <= 2000]
    nob_gt = _count_bills(gt_df, group_cols).rename("Bills >2K")
    nob_lt = _count_bills(lt_df, group_cols).rename("Bills ≤2K")

    metrics = (pd.concat([total_cust, last_day_noc, last_day_enroll,
                          last_day_non_member,
                          mtd, msr_cnt, non_msr, nob_gt, nob_lt], axis=1)
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
             ["Total NOC", "Last Day NOC", "Last Day Member Enrollment",
              "Last Day Non Member Shopped",
              "MTD Enrollment","Unique MSR Members","Unique Non-MSR Members",
              "Conversion %","Bills >2K","Bills ≤2K"])
    cols = [c for c in order if c in metrics.columns]
    result = metrics[cols].sort_values("Total NOC", ascending=False)

    # Stash the detected last-day so the dashboard can show it in a caption
    result.attrs["last_day"] = last_day_ts
    return result


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


@st.cache_data(show_spinner=False)
def calculate_detailed_view(df: pd.DataFrame,
                             metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Build the 'Detailed View' table that mirrors the new-format CSV.

    Columns produced (in order):
      Store Code · Store Name · Store Director Name · ASM Name ·
      TTL MTD Customer · Last Day Non Member Shopped ·
      Last Day member Enrollment · Last Day Enrollment % ·
      MTD Non Member Shopped · MTD member Enrollment · MTD member Enrollment %

    Enrollment % formulas:
      Last Day Enrollment %  = Last Day Member Enrollment / Last Day Non Member Shopped × 100
      MTD member Enrollment % = MTD Enrollment / MTD Non Member Shopped × 100
    """
    if df.empty or metrics_df is None or metrics_df.empty:
        return pd.DataFrame(columns=[
            "Store Code", "Store Name", "Store Director Name", "ASM Name",
            "TTL MTD Customer", "Last Day Non Member Shopped",
            "Last Day member Enrollment", "Last Day Enrollment %",
            "MTD Non Member Shopped", "MTD member Enrollment",
            "MTD member Enrollment %",
        ])

    m = metrics_df.copy()

    # Defensive: ensure every column we need exists, default to 0
    for col in ["Total NOC", "Last Day NOC", "Last Day Member Enrollment",
                "Last Day Non Member Shopped", "MTD Enrollment",
                "Unique Non-MSR Members"]:
        if col not in m.columns:
            m[col] = 0

    # Last Day Enrollment % = Last Day Member Enrollment / Last Day Non Member Shopped × 100
    last_day_nonmem = m["Last Day Non Member Shopped"].astype(float)
    m["Last Day Enrollment %"] = np.where(
        last_day_nonmem > 0,
        (m["Last Day Member Enrollment"].astype(float) / last_day_nonmem * 100).round(2),
        0.0,
    )

    # MTD Enrollment % = MTD Enrollment / MTD Non Member Shopped × 100
    mtd_nonmem = m["Unique Non-MSR Members"].astype(float)
    m["MTD member Enrollment %"] = np.where(
        mtd_nonmem > 0,
        (m["MTD Enrollment"].astype(float) / mtd_nonmem * 100).round(2),
        0.0,
    )

    # Pull the Store Director name from the lookup
    if "Store Code" in m.columns:
        m["Store Director Name"] = m["Store Code"].apply(lookup_store_director)
    else:
        m["Store Director Name"] = "-"

    # Final shape — match the new-format CSV exactly
    detailed = pd.DataFrame({
        "Store Code"                : m["Store Code"]                if "Store Code" in m.columns else "",
        "Store Name"                : m["Store Name"]                if "Store Name" in m.columns else "",
        "Store Director Name"       : m["Store Director Name"],
        "ASM Name"                  : m["ASM Name"]                  if "ASM Name"   in m.columns else "",
        "Last Day Non Member Shopped": m["Last Day Non Member Shopped"].astype(int),
        "Last Day member Enrollment": m["Last Day Member Enrollment"].astype(int),
        "Last Day Enrollment %"     : m["Last Day Enrollment %"],
        "TTL MTD Customer"          : m["Total NOC"].astype(int),
        "MTD Non Member Shopped"    : m["Unique Non-MSR Members"].astype(int),
        "MTD member Enrollment"     : m["MTD Enrollment"].astype(int),
        "MTD member Enrollment %"   : m["MTD member Enrollment %"],
    })

    return detailed.sort_values("TTL MTD Customer", ascending=False).reset_index(drop=True)


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
    """Generate a clean white-background PDF table from a DataFrame.

    Design rules (from product owner):
      • Pure white background, black fonts, borders only — no shading, no
        zebra rows, no dark theme colours.
      • Body & header font size = 18 pt.
      • ALL columns fit horizontally on ONE page; rows simply continue on
        the next page when they run out of room.
      • Headers wrap onto multiple lines so long labels (e.g.
        'Last Day Non Member Shopped') no longer overlap each other.

    To make every column fit at 18 pt the page size is chosen automatically
    from the column count: A3 → A2 → A1 → A0 (all landscape). This avoids
    the squashed/overlapping output of the previous implementation.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A0, A1, A2, A3, A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.units import cm, mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.platypus import (Paragraph, SimpleDocTemplate,
                                        Spacer, Table, TableStyle)
    except ImportError:
        raise ImportError(
            "reportlab is required for PDF export. "
            "Install: pip install reportlab"
        )

    # ── Choose a page big enough to fit every column at 18pt ─────────────
    # Heuristic: at 18pt, an average numeric cell needs ~2cm wide; a wrapped
    # header needs ~3cm minimum. We size up the paper as columns grow.
    n_cols = max(1, len(df.columns))
    if   n_cols <= 6:   page = landscape(A3)   # ~42 × 30 cm
    elif n_cols <= 9:   page = landscape(A2)   # ~59 × 42 cm
    elif n_cols <= 13:  page = landscape(A1)   # ~84 × 59 cm
    else:               page = landscape(A0)   # ~119 × 84 cm

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=page,
        leftMargin=1.2*cm, rightMargin=1.2*cm,
        topMargin=1.2*cm, bottomMargin=1.2*cm,
    )

    styles = getSampleStyleSheet()

    # ── Title & subtitle styles (dark text, no colour fills) ─────────────
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        textColor=colors.black,
        fontName="Helvetica-Bold",
        fontSize=22,
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "SubStyle",
        parent=styles["Normal"],
        textColor=colors.black,
        fontName="Helvetica",
        fontSize=11,
        spaceAfter=10,
    )

    # ── Table-cell paragraph styles (font size 18, black, centred) ───────
    # IMPORTANT: no `wordWrap='CJK'` — that breaks words mid-character (e.g.
    # turning "Shopped" into "Shop\nped"). The default reportlab wrapping
    # breaks only at whitespace, which is exactly what the user asked for.
    # We make sure every column is wide enough for its longest single word
    # so that no word ever overflows.
    header_para_style = ParagraphStyle(
        "HeaderPara",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,            # generous line-height so wrapped text breathes
        textColor=colors.black,
        alignment=TA_CENTER,
        splitLongWords=False,  # never break a word in the middle
    )
    cell_para_style = ParagraphStyle(
        "CellPara",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=18,
        leading=22,
        textColor=colors.black,
        alignment=TA_CENTER,
        splitLongWords=False,
    )

    # ── Header / body content ────────────────────────────────────────────
    elements = [
        Paragraph(f"Spencer's Retail — {title}", title_style),
        Paragraph(
            f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}  |  "
            f"Rows: {len(df):,}",
            sub_style,
        ),
        Spacer(1, 0.25*cm),
    ]

    # Wrap every cell value in a Paragraph so reportlab can wrap text on
    # whitespace — this is what stops headers from overlapping.
    headers = [Paragraph(str(c), header_para_style) for c in df.columns]
    data = [headers]
    for _, row in df.iterrows():
        data.append([Paragraph(str(v) if pd.notna(v) else "", cell_para_style)
                     for v in row])

    # ── Compute column widths so no single word ever needs to wrap ───────
    # Strategy:
    #   1. For each column, measure (in points) the actual width of:
    #        (a) the longest single WORD in the header,
    #        (b) the widest cell value in the body.
    #      Use whichever is larger as the column's MIN width — this is the
    #      width below which a word would have to be hyphenated/broken.
    #   2. Distribute the remaining page width proportionally to body
    #      content length, so columns with long values get more breathing
    #      room without ever shrinking below their min width.
    H_PAD = 14                          # left + right cell padding
    page_w_pt = page[0] - 2.4*cm        # available width after page margins

    # Sample at most ~80 rows to estimate body widths (faster, accurate enough)
    sample = df.head(80)

    min_widths = []
    body_lens  = []
    for c in df.columns:
        col_str = str(c)
        # (a) widest single word in header (incl. unbreakable tokens like "MTD")
        words = col_str.split() or [col_str]
        max_word_pt = max(
            pdfmetrics.stringWidth(w, "Helvetica-Bold", 18) for w in words
        )
        # (b) widest body value
        try:
            body_strs = sample[c].astype(str).tolist() if c in sample.columns else [""]
        except Exception:
            body_strs = [""]
        if not body_strs:
            body_strs = [""]
        max_body_pt = max(
            pdfmetrics.stringWidth(s, "Helvetica", 18) for s in body_strs
        ) if body_strs else 0

        min_w = max(max_word_pt, max_body_pt) + H_PAD
        min_widths.append(min_w)

        # proportional weight = average body length (chars), floor of 4
        try:
            avg_chars = sample[c].astype(str).map(len).mean() if c in sample.columns else 4
            avg_chars = float(avg_chars) if pd.notna(avg_chars) else 4.0
        except Exception:
            avg_chars = 4.0
        body_lens.append(max(4.0, avg_chars))

    total_min = sum(min_widths)
    if total_min >= page_w_pt:
        # Min widths already fill (or overflow) the page — just use them.
        # The page-size heuristic above should have given us enough room,
        # but this branch keeps things safe for unusually wide content.
        col_widths = min_widths
    else:
        # Distribute the remaining width proportional to body length
        slack = page_w_pt - total_min
        weight_total = sum(body_lens)
        col_widths = [
            mw + slack * (bl / weight_total)
            for mw, bl in zip(min_widths, body_lens)
        ]

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Pure white background everywhere
        ("BACKGROUND",     (0, 0), (-1, -1), colors.white),
        ("TEXTCOLOR",      (0, 0), (-1, -1), colors.black),
        # Alignment — header row vertically centred so multi-line headers
        # sit nicely no matter how tall the row gets.
        ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        # Borders only — full grid in solid black, slightly heavier under header
        ("GRID",           (0, 0), (-1, -1), 0.7, colors.black),
        ("LINEBELOW",      (0, 0), (-1,  0), 1.6, colors.black),
        # Extra-generous padding on the header row so multi-line headers
        # have room to breathe — the row will auto-grow to fit.
        ("TOPPADDING",     (0, 0), (-1,  0), 12),
        ("BOTTOMPADDING",  (0, 0), (-1,  0), 12),
        # Body rows — normal padding
        ("TOPPADDING",     (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING",  (0, 1), (-1, -1), 8),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
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
    ist_stamp = now_ist().strftime("%d %b %Y · %H:%M IST")
    badges = []
    if st.session_state.data_loaded:
        src = st.session_state.data_source or "Data"
        badges.append(f'<div class="badge">● Live · {src}</div>')
    badges.append(f'<div class="badge">🕒 {ist_stamp}</div>')
    if auth.is_logged_in():
        badges.append(f'<div class="badge">👤 {auth.current_user()}</div>')
    badges_html = "".join(badges)
    st.markdown(f"""
    <div class="hero">
        <div>
            <h1>🛒 MySpencers Rewards Dashboard</h1>
            <div class="tag">{subtitle}</div>
        </div>
        <div style="display:flex;gap:.4rem;flex-wrap:wrap;justify-content:flex-end;">
            {badges_html}
        </div>
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
            f"""<div style="background:#fde8ec;border:1px solid #C8102E;color:#9e0c24;
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
        return "background-color:#e7f5e9; color:#1e6b27; font-weight:700"
    elif v >= 8:
        return "background-color:#fff4d9; color:#8a5a00; font-weight:700"
    else:
        return "background-color:#fde8ec; color:#9e0c24; font-weight:700"

def style_metrics(df: pd.DataFrame):
    s = df.style
    conv_col = next((c for c in df.columns if "Conversion" in c or "conversion" in c
                     or "Enrollment %" in c), None)
    if conv_col:
        s = s.map(color_conversion, subset=[conv_col])
    # overall light styling for the styler
    s = s.set_table_styles([
        {"selector": "th", "props": [("background-color", "#C8102E"),
                                      ("color", "#ffffff"),
                                      ("font-weight", "700"),
                                      ("border-color", "#9e0c24")]},
        {"selector": "td", "props": [("background-color", "#ffffff"),
                                      ("color", "#1a1a1a"),
                                      ("border-color", "#e6e6e6")]},
    ])
    return s

# ────────────────────────────────────────────────────────────────────────────
# Landing page — Upload + Manage Storage (ADMIN ONLY)
# ────────────────────────────────────────────────────────────────────────────
def landing_page():
    render_hero("Connect a data source to begin")
    st.write("")

    # Safety net — this page should never render for non-admins; main() guards it
    if not auth.is_logged_in():
        st.error("🔒 You must be signed in as an admin to access this page.")
        return

    tab_upload, tab_sample, tab_storage = st.tabs([
        "📁 Upload Files",
        "🧪 Sample Data",
        "💾 Manage Storage",
    ])

    # ── File Upload ────────────────────────────────────────────────────────
    with tab_upload:
        # Live summary of what's already in persistent storage
        summary = get_storage_summary()

        if summary["exists"] and summary["rows"] > 0:
            date_range = ""
            if summary["min_date"] and summary["max_date"]:
                date_range = (f"<br>📅 Date range in storage: "
                              f"<b>{summary['min_date']}</b> → "
                              f"<b>{summary['max_date']}</b>")
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#C8102E 0%,#9e0c24 100%);
                        border:1px solid rgba(255,255,255,.12);
                        border-radius:14px;padding:1.1rem 1.3rem;margin-bottom:1rem;
                        color:#fff;">
                <div style="font-size:.95rem;font-weight:700;color:#ffffff;margin-bottom:.3rem;">
                    💾 Persistent Storage Active
                </div>
                <div style="font-size:.88rem;color:#fff5f5;line-height:1.6;">
                    <b>{summary['rows']:,}</b> rows already stored ·
                    <b>{summary['uploads']}</b> upload(s) in history ·
                    DB size: <b>{summary['db_size_kb']} KB</b>
                    {date_range}
                    <br>Any new file you upload will be <b>automatically appended</b>.
                    Duplicate rows (same bill + mobile + date + store) are skipped.
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:var(--bg-elev);border:1px solid var(--border);
                        border-radius:14px;padding:1.1rem 1.3rem;margin-bottom:1rem;">
                <div style="font-size:.95rem;font-weight:700;color:#C8102E;margin-bottom:.3rem;">
                    💾 Persistent Storage · Empty
                </div>
                <div style="font-size:.88rem;color:#4a4a4a;">
                    No data stored yet. Your first upload will create the table and
                    seed it. Future uploads will append automatically.
                </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div style="background:var(--bg-card);border:1px solid var(--border);
                    border-radius:14px;padding:1.4rem;margin-bottom:1rem;">
            <h3 style="color:#C8102E;margin:0 0 .5rem 0;">📁 Upload CSV / Excel</h3>
            <p style="color:#4a4a4a;margin:0;font-size:.9rem;">
                Upload one or <b>multiple files</b> — they are appended to persistent
                storage and the dashboard re-runs on the <b>full accumulated dataset</b>.
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

        col_a, col_b = st.columns([2, 1])
        with col_a:
            append_btn = st.button(
                "🚀 Append & Analyse (full history)",
                use_container_width=True,
                disabled=not uploaded,
                key="btn_load_files",
                help="New rows are appended to msr_data.db, then the dashboard "
                     "loads the FULL accumulated dataset for analysis.",
            )
        with col_b:
            use_stored_btn = st.button(
                "📂 Use Stored Data Only",
                use_container_width=True,
                disabled=not (summary["exists"] and summary["rows"] > 0),
                key="btn_use_stored",
                help="Skip uploading — just load everything already in storage.",
            )

        if append_btn and uploaded:
            total_in = total_appended = total_dupe = 0
            info = []
            for f in uploaded:
                try:
                    file_bytes = f.getvalue()
                    with st.spinner(f"Parsing & appending {f.name}…"):
                        raw = load_single(file_bytes, f.name)
                        result = append_upload_to_db(raw, f.name, file_bytes)
                    total_in       += result["rows_in_file"]
                    total_appended += result["rows_appended"]
                    total_dupe     += result["rows_duplicate"]
                    info.append(f.name)
                    st.info(
                        f"📄 **{f.name}** → {result['rows_in_file']:,} rows read · "
                        f"**{result['rows_appended']:,} appended** · "
                        f"{result['rows_duplicate']:,} duplicates skipped"
                    )
                except Exception as e:
                    st.error(f"Could not load {f.name}: {e}")

            # Load the FULL accumulated dataset (old + newly appended)
            full_df = load_all_stored_data()
            if full_df.empty:
                st.error("Storage is empty after append — something went wrong.")
            else:
                # Drop internal tracking columns before handing to the analyser
                analyse_df = full_df.drop(
                    columns=[c for c in ["_source_file", "_upload_ts"]
                             if c in full_df.columns],
                    errors="ignore",
                )
                st.session_state.raw_df              = analyse_df
                st.session_state.data_loaded         = True
                st.session_state.data_source         = f"Storage · {len(info)} new file(s)"
                st.session_state.uploaded_files_info = info
                st.session_state.page                = "dashboard"
                # Cached results are now stale — invalidate
                st.cache_data.clear()
                st.success(
                    f"✅ Appended {total_appended:,} new rows "
                    f"({total_dupe:,} duplicates skipped). "
                    f"Dashboard will analyse **{len(analyse_df):,} total rows** from storage."
                )
                st.rerun()

        if use_stored_btn:
            full_df = load_all_stored_data()
            if full_df.empty:
                st.error("Storage is empty.")
            else:
                analyse_df = full_df.drop(
                    columns=[c for c in ["_source_file", "_upload_ts"]
                             if c in full_df.columns],
                    errors="ignore",
                )
                st.session_state.raw_df              = analyse_df
                st.session_state.data_loaded         = True
                st.session_state.data_source         = "Persistent Storage"
                st.session_state.uploaded_files_info = [f"DB ({summary['rows']:,} rows)"]
                st.session_state.page                = "dashboard"
                st.cache_data.clear()
                st.rerun()

    # ── Sample ─────────────────────────────────────────────────────────────
    with tab_sample:
        st.markdown("""
        <div style="background:var(--bg-card);border:1px solid var(--border);
                    border-radius:14px;padding:1.4rem;margin-bottom:1rem;">
            <h3 style="color:#C8102E;margin:0 0 .5rem 0;">🧪 Explore with sample data</h3>
            <p style="color:#4a4a4a;margin:0;font-size:.9rem;">
                Generates 3,000 synthetic transactions across 8 stores so you can play with the dashboard.
            </p>
        </div>""", unsafe_allow_html=True)
        if st.button("🧪 Load Sample Data", use_container_width=True, key="btn_sample"):
            st.session_state.raw_df = _sample_data()
            st.session_state.data_loaded = True
            st.session_state.data_source = "Sample data"
            st.session_state.page = "dashboard"
            st.rerun()

    # ── Manage Storage ─────────────────────────────────────────────────────
    with tab_storage:
        st.markdown("""
        <div style="background:var(--bg-card);border:1px solid var(--border);
                    border-radius:14px;padding:1.4rem;margin-bottom:1rem;">
            <h3 style="color:#C8102E;margin:0 0 .5rem 0;">💾 Persistent Data Storage</h3>
            <p style="color:#4a4a4a;margin:0;font-size:.9rem;">
                All uploads are stored locally in <code>msr_data.db</code> (SQLite).
                Review what's in there, inspect the upload log, deduplicate, or
                reset the table.
            </p>
        </div>""", unsafe_allow_html=True)

        summary = get_storage_summary()

        # ── Summary cards ──────────────────────────────────────────────
        s1, s2, s3, s4 = st.columns(4, gap="medium")
        with s1: kpi("Total Rows Stored",
                     f"{summary['rows']:,}",
                     "Across all uploads", "blue")
        with s2: kpi("Uploads Recorded",
                     f"{summary['uploads']:,}",
                     "Files ingested to date", "gold")
        with s3: kpi("Earliest Date",
                     str(summary["min_date"] or "—"),
                     "calendar_day MIN", "green")
        with s4: kpi("Latest Date",
                     str(summary["max_date"] or "—"),
                     "calendar_day MAX", "red")

        st.markdown("")

        # ── Upload history ─────────────────────────────────────────────
        section("Upload History", "📜")
        log_df = get_upload_log()
        if log_df.empty:
            st.info("No uploads yet. Head to **📁 Upload Files** to get started.")
        else:
            # Hide the md5 column from display but keep it in the raw table
            display_log = log_df.drop(columns=["file_hash"], errors="ignore").rename(columns={
                "id"              : "#",
                "filename"        : "File",
                "upload_timestamp": "Uploaded At",
                "rows_in_file"    : "Rows Read",
                "rows_appended"   : "Rows Appended",
                "rows_duplicate"  : "Duplicates Skipped",
            })
            st.dataframe(display_log, use_container_width=True, height=320)
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            st.download_button(
                "⬇️ Download Upload Log (CSV)",
                to_csv_bytes(display_log),
                f"upload_log_{ts}.csv", "text/csv",
            )

        st.markdown("---")

        # ── Actions ────────────────────────────────────────────────────
        section("Actions", "🛠️")
        a1, a2, a3 = st.columns(3, gap="medium")

        with a1:
            if st.button("📂 Load Full Storage into Dashboard",
                         use_container_width=True,
                         disabled=not (summary["exists"] and summary["rows"] > 0),
                         key="btn_storage_load"):
                full_df = load_all_stored_data()
                analyse_df = full_df.drop(
                    columns=[c for c in ["_source_file", "_upload_ts"]
                             if c in full_df.columns],
                    errors="ignore",
                )
                st.session_state.raw_df              = analyse_df
                st.session_state.data_loaded         = True
                st.session_state.data_source         = "Persistent Storage"
                st.session_state.uploaded_files_info = [f"DB ({len(analyse_df):,} rows)"]
                st.session_state.page                = "dashboard"
                st.cache_data.clear()
                st.rerun()

        with a2:
            if st.button("🧹 Deduplicate Stored Data",
                         use_container_width=True,
                         disabled=not (summary["exists"] and summary["rows"] > 0),
                         key="btn_storage_dedup",
                         help="Removes rows with the same bill_no + mobile_number + "
                              "calendar_day + store_code combination."):
                removed = deduplicate_storage()
                st.cache_data.clear()
                if removed > 0:
                    st.success(f"Removed {removed:,} duplicate rows.")
                else:
                    st.info("No duplicates found.")
                st.rerun()

        with a3:
            # Two-click confirmation for the destructive action
            if "confirm_clear" not in st.session_state:
                st.session_state.confirm_clear = False
            if not st.session_state.confirm_clear:
                if st.button("🗑️ Clear All Stored Data",
                             use_container_width=True,
                             disabled=not summary["exists"],
                             key="btn_storage_clear_1"):
                    st.session_state.confirm_clear = True
                    st.rerun()
            else:
                st.warning("This will delete **everything** in msr_data.db. "
                           "Confirm to proceed.")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("✅ Yes, delete", use_container_width=True,
                                 key="btn_storage_clear_confirm"):
                        clear_storage()
                        st.session_state.raw_df      = None
                        st.session_state.data_loaded = False
                        st.session_state.confirm_clear = False
                        st.cache_data.clear()
                        st.success("Storage cleared.")
                        st.rerun()
                with cc2:
                    if st.button("❌ Cancel", use_container_width=True,
                                 key="btn_storage_clear_cancel"):
                        st.session_state.confirm_clear = False
                        st.rerun()

        # ── Preview ────────────────────────────────────────────────────
        if summary["exists"] and summary["rows"] > 0:
            with st.expander("👀 Preview first 100 rows in storage", expanded=False):
                preview = load_all_stored_data().head(100)
                st.dataframe(preview, use_container_width=True, height=420)

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

    # Upload / admin-only button
    if auth.is_logged_in():
        if st.sidebar.button("🔄 Change / Add Files", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()
    else:
        st.sidebar.caption("👁️ Viewer mode · Sign in as admin below to upload data.")

    if st.session_state.uploaded_files_info:
        st.sidebar.caption("📦 Loaded: " + " | ".join(st.session_state.uploaded_files_info))

    # Persistent-storage status
    _sum = get_storage_summary()
    if _sum["exists"] and _sum["rows"] > 0:
        st.sidebar.markdown(
            f"""<div style="background:var(--bg-elev);border:1px solid var(--border);
                            border-radius:8px;padding:.6rem .75rem;margin:.4rem 0;
                            font-size:.78rem;color:#4a4a4a;">
                 💾 <b style="color:#C8102E;">Storage:</b>
                 {_sum['rows']:,} rows · {_sum['uploads']} upload(s)
                 <br><span style="color:#7a7a7a;">
                 {_sum['min_date'] or '—'} → {_sum['max_date'] or '—'}
                 </span>
               </div>""",
            unsafe_allow_html=True,
        )

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
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="Inter,Helvetica,Arial", color="#1a1a1a", size=12),
        title_font=dict(size=14, color="#C8102E"),
        hoverlabel=dict(bgcolor="#ffffff", font_color="#1a1a1a",
                        bordercolor="#C8102E"),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center",
                    bgcolor="rgba(0,0,0,0)", font=dict(color="#1a1a1a")),
    )
    fig.update_xaxes(showgrid=False, linecolor="#d0d0d0",
                     tickfont=dict(color="#4a4a4a"),
                     title_font=dict(color="#4a4a4a"))
    fig.update_yaxes(gridcolor="#ececec", linecolor="#d0d0d0",
                     tickfont=dict(color="#4a4a4a"),
                     title_font=dict(color="#4a4a4a"))
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
                          textfont_color="#1a1a1a")
        fig.update_layout(coloraxis_showscale=False,
                          yaxis_title=None, xaxis_title=None)
        st.plotly_chart(_layout(fig, 430), use_container_width=True)
    with c2:
        msr_t = int(metrics_df["Unique MSR Members"].sum())
        non_t = int(metrics_df["Unique Non-MSR Members"].sum())
        fig = go.Figure(data=[go.Pie(
            labels=["MSR Members","Non-MSR"],
            values=[msr_t, non_t], hole=0.6,
            marker=dict(colors=[PALETTE["red"], PALETTE["grey"]],
                        line=dict(color="#ffffff", width=2)),
            textinfo="label+percent",
            textfont=dict(color="#ffffff"),
        )])
        fig.update_layout(title="MSR vs Non-MSR Split",
                          annotations=[dict(text=f"<b>{msr_t:,}</b><br>MSR",
                                            x=0.5, y=0.5, showarrow=False,
                                            font=dict(size=14, color="#C8102E"))])
        st.plotly_chart(_layout(fig, 430), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        long = top.melt(id_vars=["label"],
                        value_vars=["Unique MSR Members","Unique Non-MSR Members"],
                        var_name="Segment", value_name="Count")
        fig = px.bar(long, x="label", y="Count", color="Segment", barmode="group",
                     title="MSR vs Non-MSR by Store (Top 10)",
                     color_discrete_map={"Unique MSR Members": PALETTE["red"],
                                         "Unique Non-MSR Members": PALETTE["grey"]})
        fig.update_layout(xaxis_title=None, yaxis_title=None, xaxis_tickangle=-30)
        st.plotly_chart(_layout(fig), use_container_width=True)
    with c4:
        long2 = top.melt(id_vars=["label"], value_vars=["Bills >2K","Bills ≤2K"],
                         var_name="Slab", value_name="Count")
        fig = px.bar(long2, x="label", y="Count", color="Slab", barmode="stack",
                     title="Bills >2K vs ≤2K (Non-MSR, Top 10)",
                     color_discrete_map={"Bills >2K": "#C8102E",
                                         "Bills ≤2K": "#1a1a1a"})
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
            line=dict(color=PALETTE["red"], width=3),
            marker=dict(size=11, color="#1a1a1a",
                        line=dict(width=2, color="#ffffff")),
            fill="tozeroy", fillcolor="rgba(200,16,46,.10)",
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


def render_detailed_view_table(dv_df: pd.DataFrame):
    """Render the new-format Detailed View table with light styling and a
    matching white-background PDF download button."""
    if dv_df is None or dv_df.empty:
        st.info("No detailed-view data for current filters.")
        return

    display = dv_df.copy()
    # Pretty-print percentage columns
    for col in ["Last Day Enrollment %", "MTD member Enrollment %"]:
        if col in display.columns:
            display[col] = display[col].apply(lambda v: f"{v:.2f}%")

    styled = style_metrics(display)
    st.dataframe(styled, use_container_width=True, height=540)

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    dl1, dl2, dl3 = st.columns(3)
    with dl1:
        st.download_button(
            "⬇️ Download CSV – Detailed View",
            to_csv_bytes(display),
            f"detailed_view_{ts}.csv", "text/csv",
            use_container_width=True, key=f"csv_detailed_{ts}",
        )
    with dl2:
        try:
            st.download_button(
                "⬇️ Download Excel – Detailed View",
                to_excel_bytes(display, "DetailedView"),
                f"detailed_view_{ts}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True, key=f"xlsx_detailed_{ts}",
            )
        except Exception as e:
            st.caption(f"Excel unavailable: {e}")
    with dl3:
        try:
            pdf_b = to_pdf_bytes(display, "Detailed View")
            st.download_button(
                "⬇️ Download PDF – Detailed View", pdf_b,
                f"detailed_view_{ts}.pdf", "application/pdf",
                use_container_width=True, key=f"pdf_detailed_{ts}",
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

    # ── Compute everything once, BEFORE laying out tabs ─────────────────────
    # The Detailed View is the default landing surface, so it must always
    # have access to filters and metrics — even when the other two tabs are
    # hidden. We therefore lift these computations out of `tab_summary`.
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

    # ── Tab visibility toggle (Summary + Drill-Down hidden by default) ──────
    if "show_advanced_tabs" not in st.session_state:
        st.session_state.show_advanced_tabs = False
    show_advanced = st.session_state.show_advanced_tabs

    btn_col1, btn_col2 = st.columns([3, 1])
    with btn_col2:
        if show_advanced:
            if st.button("🙈 Hide Summary & Drill-Down",
                         use_container_width=True, key="toggle_adv_tabs_off"):
                st.session_state.show_advanced_tabs = False
                st.rerun()
        else:
            if st.button("👁️ Show Summary & Drill-Down",
                         use_container_width=True, key="toggle_adv_tabs_on",
                         type="primary"):
                st.session_state.show_advanced_tabs = True
                st.rerun()

    # ── Render Detailed View body ───────────────────────────────────────────
    def _render_detailed_view_body():
        section("Detailed View – Store Director × Member Performance", "📋")
        st.markdown("""
        This view follows the **new reporting format** with one row per store.
        Columns: Store Director Name (auto-populated), ASM Name, MTD totals
        for customers, members and non-members, plus same-day enrollment
        rates.
        """)

        detailed_df = calculate_detailed_view(filtered, metrics)

        # Optional store filter, mirroring the drill-down tab UX
        if not detailed_df.empty and "Store Name" in detailed_df.columns:
            stores_dv = sorted(detailed_df["Store Name"].dropna().unique().tolist())
            sel_dv = st.multiselect("Filter by Store (Detailed View only)",
                                    ["All"] + stores_dv, default=["All"],
                                    key="dv_store_filter")
            if sel_dv and "All" not in sel_dv:
                detailed_df = detailed_df[detailed_df["Store Name"].isin(sel_dv)]

        st.caption(f"Showing **{len(detailed_df):,}** stores")
        render_detailed_view_table(detailed_df)

    # ── Render Summary body ─────────────────────────────────────────────────
    def _render_summary_body():
        section("Executive Summary", "📌")
        render_kpis(metrics, filtered, mtd_label)

        section("Visual Analytics", "📈")
        render_charts(metrics, filtered)

        section("Store-level Metrics Table", "🏬")
        last_day_attr = metrics.attrs.get("last_day") if hasattr(metrics, "attrs") else None
        last_day_str  = pd.Timestamp(last_day_attr).strftime("%d-%m-%Y") if pd.notna(last_day_attr) else "—"
        st.caption(
            f"Showing **{len(metrics):,}** stores · "
            f"**{len(filtered):,}** transactions · "
            f"**{filtered['mobile_number'].nunique():,}** unique customers · "
            f"MTD Month: **{mtd_label}** · "
            f"Last Day (IST): **{last_day_str}**"
        )
        render_table(metrics)

    # ── Render Drill-Down body ──────────────────────────────────────────────
    def _render_drilldown_body():
        section("Day-wise × Store-wise Drill-Down", "🔍")
        st.markdown("""
        This table shows **day-wise** and **store-wise** breakdown of:
        Total NOC, Enrollment (MTD), Unique MSR/Non-MSR members, Conversion %,
        and Bills >₹2K / ≤₹2K (non-MSR bills only).
        """)

        dd_df_display = dd_df

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

    # ── Layout: tabs only when advanced view is on, otherwise plain page ────
    if show_advanced:
        tab_summary, tab_drill, tab_detailed = st.tabs([
            "📊 Summary Dashboard",
            "🔍 Drill-Down (Day × Store)",
            "📋 Detailed View",
        ])
        with tab_summary:
            _render_summary_body()
        with tab_drill:
            _render_drilldown_body()
        with tab_detailed:
            _render_detailed_view_body()
    else:
        _render_detailed_view_body()

# ────────────────────────────────────────────────────────────────────────────
# Viewer-only "no data yet" page
# ────────────────────────────────────────────────────────────────────────────
def viewer_no_data_page():
    """Shown to unauthenticated visitors when storage is empty."""
    render_hero("Live dashboard · waiting for admin to upload data")
    st.markdown("""
    <div style="background:var(--bg-card);border:1px solid var(--border);
                border-radius:14px;padding:2rem;margin-top:1rem;text-align:center;
                box-shadow:0 1px 3px rgba(0,0,0,.04);">
        <h2 style="color:#C8102E;margin:0 0 .6rem 0;">📭 No data available yet</h2>
        <p style="color:#4a4a4a;font-size:.95rem;margin:0;">
            An admin has not uploaded any data to this dashboard yet.<br>
            Please check back later, or contact your administrator.
        </p>
        <p style="color:#7a7a7a;font-size:.82rem;margin-top:1rem;">
            Admins: sign in from the sidebar to upload your first file.
        </p>
    </div>
    """, unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────────────────
# Router
# ────────────────────────────────────────────────────────────────────────────
def main():
    # 🔐 Render auth panel in the sidebar on every rerun. Returns True if
    # the viewer is signed in as an admin.
    is_admin = auth.render_auth_sidebar()

    # Non-admins are never allowed on the landing (upload / manage) page.
    # If they somehow land there (e.g. stale session), bounce them to the
    # dashboard or the viewer-waiting screen.
    if not is_admin and st.session_state.page == "landing":
        st.session_state.page = "dashboard"

    # Route
    if st.session_state.page == "landing":
        # Landing is admin-only (guaranteed by the check above).
        landing_page()
    else:
        if st.session_state.data_loaded:
            dashboard_page()
        else:
            # No data stored yet.
            if is_admin:
                # Send the admin straight to the upload page.
                st.session_state.page = "landing"
                st.rerun()
            else:
                viewer_no_data_page()


if __name__ == "__main__":
    main()
