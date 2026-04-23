"""
MySpencers Rewards (MSR) Dashboard
==================================
A premium retail analytics dashboard for MSR membership and customer transaction
performance at store level.

Run locally:
    pip install -r requirements.txt
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

# ---------------------------------------------------------------------------
# Page config & theme
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MSR Dashboard | Spencer's Retail",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Premium "McKinsey / BCG" inspired CSS --------------------------------------
CUSTOM_CSS = """
<style>
    /* Base */
    html, body, [class*="css"]  {
        font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif !important;
        color: #1a2332;
    }
    .main .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }
    /* Hero header */
    .hero {
        background: linear-gradient(135deg, #0B2545 0%, #13315C 50%, #1C4B82 100%);
        color: #fff;
        padding: 1.4rem 1.8rem;
        border-radius: 14px;
        margin-bottom: 1.4rem;
        box-shadow: 0 10px 30px rgba(11, 37, 69, 0.18);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .hero h1 {
        margin: 0;
        font-size: 1.7rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .hero .tag {
        font-size: 0.9rem;
        opacity: 0.85;
        margin-top: 0.25rem;
    }
    .hero .badge {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.25);
        padding: 0.4rem 0.85rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    /* KPI cards */
    .kpi-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 1.1rem 1.2rem;
        box-shadow: 0 2px 8px rgba(12, 28, 55, 0.06), 0 1px 2px rgba(12,28,55,0.04);
        border: 1px solid #eef1f6;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
        height: 100%;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 22px rgba(12, 28, 55, 0.10);
    }
    .kpi-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 1.1px;
        color: #5b6b82;
        font-weight: 600;
        margin-bottom: 0.4rem;
    }
    .kpi-value {
        font-size: 1.9rem;
        font-weight: 800;
        color: #0B2545;
        line-height: 1.1;
    }
    .kpi-sub {
        font-size: 0.78rem;
        color: #7a8ba3;
        margin-top: 0.35rem;
    }
    .kpi-accent-blue  { border-top: 4px solid #1C6DD0; }
    .kpi-accent-gold  { border-top: 4px solid #D4A017; }
    .kpi-accent-green { border-top: 4px solid #2A9D8F; }
    .kpi-accent-red   { border-top: 4px solid #E76F51; }
    /* Section headers */
    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #0B2545;
        margin: 1.6rem 0 0.8rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid #eef1f6;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .section-title .dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: linear-gradient(135deg, #D4A017, #f5c646);
    }
    /* Landing page cards */
    .source-card {
        background: #ffffff;
        border: 1px solid #e6ebf2;
        border-radius: 14px;
        padding: 1.4rem;
        height: 100%;
        transition: all 0.2s ease;
    }
    .source-card:hover {
        border-color: #1C6DD0;
        box-shadow: 0 6px 18px rgba(28, 109, 208, 0.12);
    }
    .source-card .icon {
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    .source-card h3 {
        margin: 0.2rem 0 0.4rem 0;
        color: #0B2545;
        font-size: 1.1rem;
    }
    .source-card p {
        color: #5b6b82;
        font-size: 0.88rem;
        margin: 0;
    }
    /* Dataframe container tweaks */
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #eef1f6;
    }
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f7f9fc 0%, #eef2f8 100%);
        border-right: 1px solid #e1e7f0;
    }
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #0B2545 !important;
    }
    /* Primary buttons */
    .stButton>button {
        background: linear-gradient(135deg, #1C6DD0 0%, #0B2545 100%);
        color: #fff;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(28, 109, 208, 0.25);
    }
    /* Download buttons */
    .stDownloadButton>button {
        background: #ffffff;
        color: #0B2545;
        border: 1.5px solid #1C6DD0;
        border-radius: 8px;
        font-weight: 600;
        width: 100%;
    }
    .stDownloadButton>button:hover {
        background: #1C6DD0;
        color: #fff;
    }
    /* Hide default Streamlit chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 3rem 1rem;
        color: #7a8ba3;
    }
    .empty-state .big {
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# Plotly chart palette -------------------------------------------------------
PALETTE = {
    "navy": "#0B2545",
    "blue": "#1C6DD0",
    "gold": "#D4A017",
    "teal": "#2A9D8F",
    "red":  "#E76F51",
    "grey": "#8A9BB4",
}
SEQ_BLUE  = ["#DCE7F5", "#AAC4E8", "#6E99D1", "#3C73B8", "#1C4B82", "#0B2545"]
SEQ_GOLD  = ["#FDF2D1", "#F9DF8A", "#ECC24C", "#D4A017", "#A87C0A", "#6E5008"]
DIVERGING = ["#E76F51", "#F4A261", "#E9C46A", "#8ECBC2", "#2A9D8F", "#0B2545"]


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

def _init_state() -> None:
    defaults = {
        "raw_df": None,
        "data_loaded": False,
        "data_source": None,
        "page": "landing",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

REQUIRED_COLS = [
    "store_code", "store_name", "mobile_number", "bill_no",
    "grs_sales", "msr_number", "msr_month", "noc_tagging",
    "msr_tagging", "asm_name",
]
# Any of these columns satisfies "shopping date"
DATE_COLS = ["calendar_day", "month_name"]


@st.cache_data(show_spinner=False)
def load_csv(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Load a CSV or Excel file from raw bytes."""
    buf = io.BytesIO(file_bytes)
    lower = filename.lower()
    if lower.endswith((".xlsx", ".xls", ".xlsm")):
        return pd.read_excel(buf)
    # Try CSV with a couple of common separators
    for sep in [",", ";", "\t", "|"]:
        try:
            buf.seek(0)
            df = pd.read_csv(buf, sep=sep)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    buf.seek(0)
    return pd.read_csv(buf)


def load_sql_server(server: str, database: str, user: str, password: str,
                    table_or_query: str, trusted: bool = False) -> pd.DataFrame:
    """Load data from a local MS SQL Server using pyodbc / sqlalchemy."""
    try:
        from sqlalchemy import create_engine
        from urllib.parse import quote_plus
    except ImportError as e:
        raise RuntimeError(
            "SQLAlchemy is required for SQL Server import. "
            "Install with: pip install sqlalchemy pyodbc"
        ) from e

    if trusted:
        params = quote_plus(
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};DATABASE={database};Trusted_Connection=yes;"
        )
    else:
        params = quote_plus(
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};DATABASE={database};UID={user};PWD={password};"
        )
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
    q = table_or_query.strip()
    if not q.lower().startswith("select"):
        q = f"SELECT * FROM {q}"
    return pd.read_sql(q, engine)


def load_cloud_sql(dialect: str, host: str, port: int, database: str,
                   user: str, password: str, table_or_query: str) -> pd.DataFrame:
    """Load data from an AWS-hosted Cloud SQL (MySQL / PostgreSQL / MSSQL)."""
    try:
        from sqlalchemy import create_engine
    except ImportError as e:
        raise RuntimeError(
            "SQLAlchemy is required. Install with: pip install sqlalchemy"
        ) from e

    driver_map = {
        "PostgreSQL": "postgresql+psycopg2",
        "MySQL":      "mysql+pymysql",
        "SQL Server": "mssql+pyodbc",
    }
    prefix = driver_map.get(dialect, "postgresql+psycopg2")
    url = f"{prefix}://{user}:{password}@{host}:{port}/{database}"
    engine = create_engine(url)
    q = table_or_query.strip()
    if not q.lower().startswith("select"):
        q = f"SELECT * FROM {q}"
    return pd.read_sql(q, engine)


# ---------------------------------------------------------------------------
# Data processing
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def process_data(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean, normalise and enrich the raw dataframe."""
    df = raw.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # Validate required columns
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}. "
            f"Available: {list(df.columns)}"
        )

    # Trim strings
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip()

    # Parse dates robustly
    for c in DATE_COLS + ["msr_month"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    # Drop Untagged NOC rows
    before = len(df)
    df = df[df["noc_tagging"].str.lower() != "untagged"].copy()
    df.attrs["dropped_untagged"] = before - len(df)

    # Resolve shopping date
    if "calendar_day" in df.columns and df["calendar_day"].notna().any():
        df["shopping_date"] = df["calendar_day"]
    elif "month_name" in df.columns:
        df["shopping_date"] = df["month_name"]
    else:
        df["shopping_date"] = pd.NaT

    # Shopping month label (mmm-yy) + period for sorting
    df["shopping_month"] = df["shopping_date"].dt.strftime("%b-%y")
    df["shopping_period"] = df["shopping_date"].dt.to_period("M")

    # Enrollment month (from msr_month)
    df["enroll_month"] = df["msr_month"].dt.strftime("%b-%y")
    df["enroll_period"] = df["msr_month"].dt.to_period("M")

    # MSR flag: treat rows as MSR members if the tag says so or there's a valid
    # msr_number that is not the same as the mobile placeholder.
    tag = df.get("msr_tagging", pd.Series(index=df.index, dtype=str)).astype(str).str.upper()
    df["is_msr"] = tag.str.contains("MSR_MEMBER") | tag.eq("MSR")
    # Fall back: non-null, non-zero msr_number also counts as enrolled
    if "msr_number" in df.columns:
        msr_valid = pd.to_numeric(df["msr_number"], errors="coerce").fillna(0) > 0
        df["is_msr"] = df["is_msr"] | msr_valid

    # Numeric coercions
    for c in ["grs_sales", "nob_ach", "billed_qty", "bill_no"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    return df


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply sidebar filter selections to the working dataframe."""
    out = df.copy()

    for col, sel in filters.get("multi", {}).items():
        if sel and col in out.columns:
            out = out[out[col].isin(sel)]

    # Date range on shopping_date
    date_from = filters.get("date_from")
    date_to   = filters.get("date_to")
    if date_from is not None and date_to is not None and "shopping_date" in out.columns:
        mask = (out["shopping_date"] >= pd.Timestamp(date_from)) & \
               (out["shopping_date"] <= pd.Timestamp(date_to))
        out = out[mask]

    # Month filters
    enroll_months = filters.get("enroll_months") or []
    if enroll_months:
        out = out[out["enroll_month"].isin(enroll_months)]

    shop_months = filters.get("shopping_months") or []
    if shop_months:
        out = out[out["shopping_month"].isin(shop_months)]

    # Free-text search
    q = (filters.get("search") or "").strip()
    if q:
        fields = []
        for c in ["store_code", "msr_number", "mobile_number"]:
            if c in out.columns:
                fields.append(out[c].astype(str).str.contains(q, case=False, na=False))
        if fields:
            combined = np.logical_or.reduce(fields)
            out = out[combined]

    return out


# ---------------------------------------------------------------------------
# Metric calculations
# ---------------------------------------------------------------------------

def _current_month_period(df: pd.DataFrame) -> Optional[pd.Period]:
    """Choose the 'current month' as the latest shopping period in the data."""
    if "shopping_period" not in df.columns:
        return None
    per = df["shopping_period"].dropna()
    if per.empty:
        return None
    return per.max()


@st.cache_data(show_spinner=False)
def calculate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Store-level aggregation of KPIs."""
    if df.empty:
        return pd.DataFrame()

    group_cols = ["store_code", "store_name", "asm_name"]
    group_cols = [c for c in group_cols if c in df.columns]
    cur_month = _current_month_period(df)

    # 1. Total unique customers per store
    total_cust = df.groupby(group_cols)["mobile_number"].nunique().rename("Total Customers")

    # 2. MTD MSR Registration: unique customers enrolled in the current month,
    #    shopping in that store
    if cur_month is not None and "enroll_period" in df.columns:
        mtd_df = df[df["enroll_period"] == cur_month]
        mtd = mtd_df.groupby(group_cols)["mobile_number"].nunique().rename("MTD MSR Registration")
    else:
        mtd = pd.Series(0, index=total_cust.index, name="MTD MSR Registration")

    # 3. MSR Members unique count
    msr = df[df["is_msr"]].groupby(group_cols)["mobile_number"].nunique().rename("MSR Members")

    # 4. Non-MSR Members unique count
    non_msr = df[~df["is_msr"]].groupby(group_cols)["mobile_number"].nunique().rename("Non MSR Members")

    # 6/7. Customers by monthly cumulative spend slab
    if "shopping_period" in df.columns:
        cust_spend = (
            df.groupby(group_cols + ["mobile_number", "shopping_period"])["grs_sales"]
              .sum()
              .reset_index()
        )
    else:
        cust_spend = df.groupby(group_cols + ["mobile_number"])["grs_sales"].sum().reset_index()

    nob_gt = (
        cust_spend[cust_spend["grs_sales"] > 2000]
        .groupby(group_cols)["mobile_number"].nunique()
        .rename("Sum of NOB >2K")
    )
    nob_lt = (
        cust_spend[cust_spend["grs_sales"] <= 2000]
        .groupby(group_cols)["mobile_number"].nunique()
        .rename("Sum of NOB <2K")
    )

    # 8. Unique customers with a SINGLE bill over 2K
    bill_counts = df.groupby(group_cols + ["mobile_number"]).agg(
        bill_count=("bill_no", "nunique"),
        max_spend=("grs_sales", "max"),
    ).reset_index()
    single_big = (
        bill_counts[(bill_counts["bill_count"] == 1) & (bill_counts["max_spend"] > 2000)]
        .groupby(group_cols)["mobile_number"].nunique()
        .rename("Unique Customers (Single Bill >2K)")
    )

    # Combine
    metrics = pd.concat(
        [total_cust, mtd, msr, non_msr, nob_gt, nob_lt, single_big], axis=1
    ).fillna(0).astype(int, errors="ignore").reset_index()

    # Conversion % = MTD MSR Registration / Total Customers
    metrics["Conversion %"] = np.where(
        metrics["Total Customers"] > 0,
        (metrics["MTD MSR Registration"] / metrics["Total Customers"]) * 100.0,
        0.0,
    ).round(2)

    # Order columns
    cols = [c for c in group_cols] + [
        "Total Customers", "MTD MSR Registration", "MSR Members",
        "Non MSR Members", "Conversion %", "Sum of NOB >2K",
        "Sum of NOB <2K", "Unique Customers (Single Bill >2K)",
    ]
    cols = [c for c in cols if c in metrics.columns]
    metrics = metrics[cols].sort_values("Total Customers", ascending=False)

    # Pretty column names for display
    rename = {"store_code": "Store Code", "store_name": "Store Name", "asm_name": "ASM Name"}
    metrics = metrics.rename(columns=rename)
    return metrics


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "MSR Metrics") -> bytes:
    buf = io.BytesIO()
    engine = "xlsxwriter"
    try:
        import xlsxwriter  # noqa: F401
    except ImportError:
        engine = "openpyxl"
    with pd.ExcelWriter(buf, engine=engine) as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        # Auto column width
        ws = writer.sheets[sheet_name]
        if engine == "xlsxwriter":
            for i, col in enumerate(df.columns):
                width = max(12, min(30, int(df[col].astype(str).map(len).max() or 10) + 2))
                ws.set_column(i, i, width)
    buf.seek(0)
    return buf.getvalue()


def to_pdf_bytes(df: pd.DataFrame, title: str = "MSR Dashboard Report") -> bytes:
    """Render the metrics table to a landscape PDF using reportlab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        )
    except ImportError:
        raise RuntimeError(
            "reportlab is required for PDF export. "
            "Install with: pip install reportlab"
        )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=28, rightMargin=28, topMargin=30, bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "t", parent=styles["Heading1"], fontSize=16,
        textColor=colors.HexColor("#0B2545"),
    )
    sub_style = ParagraphStyle(
        "s", parent=styles["Normal"], fontSize=9,
        textColor=colors.HexColor("#5b6b82"),
    )
    story = [
        Paragraph(title, title_style),
        Paragraph(
            f"Generated on {datetime.now().strftime('%d %b %Y, %H:%M')} "
            f"&nbsp;·&nbsp; Stores: {len(df)}",
            sub_style,
        ),
        Spacer(1, 10),
    ]

    data = [list(df.columns)] + df.astype(str).values.tolist()
    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B2545")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 7.5),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.whitesmoke, colors.HexColor("#F2F6FC")]),
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.HexColor("#c5cedb")),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
    ]))
    story.append(tbl)
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------

def render_hero(subtitle: str = "Customer & MSR Membership Performance"):
    right_badge = ""
    if st.session_state.data_loaded:
        src = st.session_state.data_source or "Data"
        right_badge = f'<div class="badge">● Live · {src}</div>'
    st.markdown(
        f"""
        <div class="hero">
            <div>
                <h1>🛒 MySpencers Rewards Dashboard</h1>
                <div class="tag">{subtitle}</div>
            </div>
            {right_badge}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(label: str, value: str, sub: str = "", accent: str = "blue"):
    st.markdown(
        f"""
        <div class="kpi-card kpi-accent-{accent}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section(title: str, icon: str = "📊"):
    st.markdown(
        f'<div class="section-title"><span class="dot"></span>{icon} {title}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------

def landing_page():
    render_hero("Connect a data source to begin")

    st.write("")
    cols = st.columns(3, gap="large")
    for col, icon, title, desc in [
        (cols[0], "📁", "Upload CSV/Excel", "Drop a file from your machine."),
        (cols[1], "🗄️",  "MS SQL Server",    "Local or on-prem SQL Server."),
        (cols[2], "☁️",  "AWS Cloud SQL",    "RDS PostgreSQL, MySQL, or MSSQL."),
    ]:
        with col:
            st.markdown(
                f"""<div class="source-card">
                    <div class="icon">{icon}</div>
                    <h3>{title}</h3>
                    <p>{desc}</p>
                </div>""",
                unsafe_allow_html=True,
            )

    st.write("")
    tab1, tab2, tab3 = st.tabs(["📁 Upload File", "🗄️ MS SQL Server", "☁️ AWS Cloud SQL"])

    # --- CSV/Excel upload -------------------------------------------------
    with tab1:
        st.markdown("#### Upload a CSV or Excel file")
        up = st.file_uploader(
            "Supported: .csv, .xlsx, .xls, .xlsm",
            type=["csv", "xlsx", "xls", "xlsm"],
            label_visibility="collapsed",
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            if up is not None and st.button("Load file", key="load_csv", use_container_width=True):
                try:
                    with st.spinner("Parsing file..."):
                        raw = load_csv(up.getvalue(), up.name)
                    st.session_state.raw_df = raw
                    st.session_state.data_loaded = True
                    st.session_state.data_source = f"Upload · {up.name}"
                    st.session_state.page = "dashboard"
                    st.success(f"Loaded {len(raw):,} rows · {raw.shape[1]} columns")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not load file: {e}")
        with c2:
            if st.button("🧪 Try with sample data", use_container_width=True):
                st.session_state.raw_df = _sample_data()
                st.session_state.data_loaded = True
                st.session_state.data_source = "Sample data"
                st.session_state.page = "dashboard"
                st.rerun()

    # --- SQL Server -------------------------------------------------------
    with tab2:
        st.markdown("#### Connect to a local MS SQL Server")
        c1, c2 = st.columns(2)
        with c1:
            server   = st.text_input("Server Name", placeholder="localhost\\SQLEXPRESS")
            database = st.text_input("Database Name")
            trusted  = st.checkbox("Use Windows Authentication (Trusted)", value=False)
        with c2:
            user     = st.text_input("Username", disabled=trusted)
            password = st.text_input("Password", type="password", disabled=trusted)
        tbl = st.text_input(
            "Table or Query",
            value="transactions",
            help="Table name, or a full SELECT query.",
        )
        if st.button("Connect & Load", key="load_mssql"):
            try:
                with st.spinner("Connecting to SQL Server..."):
                    raw = load_sql_server(server, database, user, password, tbl, trusted)
                st.session_state.raw_df = raw
                st.session_state.data_loaded = True
                st.session_state.data_source = f"MSSQL · {database}"
                st.session_state.page = "dashboard"
                st.success(f"Loaded {len(raw):,} rows")
                st.rerun()
            except Exception as e:
                st.error(f"Connection failed: {e}")
                st.info(
                    "Tip: make sure the ODBC Driver 17 for SQL Server is installed, "
                    "and `pyodbc` is available in your Python environment."
                )

    # --- AWS Cloud SQL ----------------------------------------------------
    with tab3:
        st.markdown("#### Connect to AWS Cloud SQL (RDS)")
        c1, c2 = st.columns(2)
        with c1:
            host     = st.text_input("Host", placeholder="my-db.abc123.us-east-1.rds.amazonaws.com")
            database = st.text_input("Database", key="aws_db")
            dialect  = st.selectbox("Dialect", ["PostgreSQL", "MySQL", "SQL Server"])
        with c2:
            user     = st.text_input("Username", key="aws_user")
            password = st.text_input("Password", type="password", key="aws_pw")
            port     = st.number_input(
                "Port", min_value=1, max_value=65535,
                value={"PostgreSQL": 5432, "MySQL": 3306, "SQL Server": 1433}[dialect],
            )
        tbl = st.text_input("Table or Query", value="transactions", key="aws_tbl")
        if st.button("Connect & Load", key="load_cloud"):
            try:
                with st.spinner(f"Connecting to {dialect}..."):
                    raw = load_cloud_sql(dialect, host, int(port), database, user, password, tbl)
                st.session_state.raw_df = raw
                st.session_state.data_loaded = True
                st.session_state.data_source = f"{dialect} · {database}"
                st.session_state.page = "dashboard"
                st.success(f"Loaded {len(raw):,} rows")
                st.rerun()
            except Exception as e:
                st.error(f"Connection failed: {e}")


# ---------------------------------------------------------------------------
# Sample data (fallback for demo)
# ---------------------------------------------------------------------------

def _sample_data(n: int = 4000) -> pd.DataFrame:
    """Synthetic but realistic dataset mirroring the user's schema."""
    rng = np.random.default_rng(42)
    stores = [
        ("S070", "Gariahat",      "East",  "Kolkata", "Sagar SenGupta"),
        ("S071", "Park Street",   "East",  "Kolkata", "Sagar SenGupta"),
        ("S120", "Koramangala",   "South", "Bengaluru", "Anitha Rao"),
        ("S121", "Indiranagar",   "South", "Bengaluru", "Anitha Rao"),
        ("S210", "Bandra West",   "West",  "Mumbai",    "Rahul Mehta"),
        ("S211", "Powai",         "West",  "Mumbai",    "Rahul Mehta"),
        ("S310", "CP Delhi",      "North", "Delhi",     "Preeti Arora"),
        ("S311", "Gurgaon Cyber", "North", "Delhi",     "Preeti Arora"),
    ]
    rows = []
    for _ in range(n):
        s = stores[rng.integers(0, len(stores))]
        sold = pd.Timestamp("2026-01-01") + pd.Timedelta(days=int(rng.integers(0, 120)))
        mob = int(7000000000 + rng.integers(0, 99999999))
        is_msr = rng.random() < 0.55
        msr_num = mob if is_msr else 0
        # 80% of MSR members have enrolled in the same month as a purchase
        enroll_offset = rng.integers(-5, 1) if is_msr else 0
        enroll = sold - pd.Timedelta(days=int(abs(enroll_offset) * 30)) if is_msr else pd.NaT
        sales = int(rng.integers(150, 6000))
        rows.append({
            "calendar_day":  sold,
            "store_code":    s[0],
            "store_name":    s[1],
            "region_name":   s[2],
            "cluster_name":  s[3],
            "mobile_number": mob,
            "bill_no":       int(2000000000 + rng.integers(0, 99999999)),
            "nob_ach":       1,
            "billed_qty":    int(rng.integers(1, 8)),
            "grs_sales":     sales,
            "bill_type":     "Non_Liq" if rng.random() < 0.85 else "Liq",
            "bill_slab":     ">_2K" if sales > 2000 else "<_2K",
            "msr_number":    msr_num,
            "msr_month":     enroll,
            "noc_tagging":   "Tagged" if rng.random() < 0.9 else "Untagged",
            "msr_tagging":   "MSR_MEMBER" if is_msr else "NON_MSR",
            "month_name":    sold.replace(day=1),
            "asm_name":      s[4],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Sidebar (filters + exports)
# ---------------------------------------------------------------------------

def render_sidebar(df: pd.DataFrame, metrics_df: pd.DataFrame) -> dict:
    st.sidebar.markdown("## ⚙️ Controls")

    if st.sidebar.button("🔄 Change Data Source", use_container_width=True):
        st.session_state.page = "landing"
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔎 Search")
    search = st.sidebar.text_input(
        "Store Code · MSR · Mobile",
        placeholder="e.g. S070 or 96745",
        label_visibility="collapsed",
    )

    st.sidebar.markdown("### 🎛️ Filters")

    multi_filters = {}
    for col, label in [
        ("store_name",   "Store Name"),
        ("region_name",  "Region Name"),
        ("cluster_name", "Cluster Name"),
        ("asm_name",     "ASM Name"),
    ]:
        if col in df.columns:
            options = sorted([str(x) for x in df[col].dropna().unique()])
            if options:
                sel = st.sidebar.multiselect(label, options, default=[])
                multi_filters[col] = sel

    st.sidebar.markdown("### 📅 Dates")
    date_from = date_to = None
    if "shopping_date" in df.columns and df["shopping_date"].notna().any():
        min_d = df["shopping_date"].min().date()
        max_d = df["shopping_date"].max().date()
        dr = st.sidebar.date_input(
            "Shopping Date range",
            value=(min_d, max_d),
            min_value=min_d, max_value=max_d,
        )
        if isinstance(dr, tuple) and len(dr) == 2:
            date_from, date_to = dr

    shop_opts = sorted(
        df["shopping_month"].dropna().unique().tolist(),
        key=lambda s: pd.to_datetime(s, format="%b-%y", errors="coerce"),
    ) if "shopping_month" in df.columns else []
    shopping_months = st.sidebar.multiselect("Shopping Month (mmm-yy)", shop_opts, default=[])

    enroll_opts = sorted(
        df["enroll_month"].dropna().unique().tolist(),
        key=lambda s: pd.to_datetime(s, format="%b-%y", errors="coerce"),
    ) if "enroll_month" in df.columns else []
    enroll_months = st.sidebar.multiselect("Enroll Month (from msr_month)", enroll_opts, default=[])

    # Exports
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📤 Export")
    if not metrics_df.empty:
        st.sidebar.download_button(
            "⬇️ CSV",
            data=to_csv_bytes(metrics_df),
            file_name=f"msr_metrics_{datetime.now():%Y%m%d_%H%M}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        try:
            st.sidebar.download_button(
                "⬇️ Excel",
                data=to_excel_bytes(metrics_df),
                file_name=f"msr_metrics_{datetime.now():%Y%m%d_%H%M}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.sidebar.caption(f"Excel export unavailable: {e}")
        try:
            st.sidebar.download_button(
                "⬇️ PDF",
                data=to_pdf_bytes(metrics_df),
                file_name=f"msr_metrics_{datetime.now():%Y%m%d_%H%M}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except RuntimeError as e:
            st.sidebar.caption(str(e))
    else:
        st.sidebar.info("Load data to enable exports.")

    return {
        "multi": multi_filters,
        "date_from": date_from,
        "date_to": date_to,
        "shopping_months": shopping_months,
        "enroll_months": enroll_months,
        "search": search,
    }


# ---------------------------------------------------------------------------
# KPI row, charts, table
# ---------------------------------------------------------------------------

def render_kpis(metrics_df: pd.DataFrame, filtered_df: pd.DataFrame):
    total_cust      = int(metrics_df["Total Customers"].sum()) if not metrics_df.empty else 0
    msr_members     = int(metrics_df["MSR Members"].sum())     if not metrics_df.empty else 0
    conv            = (msr_members / total_cust * 100) if total_cust > 0 else 0
    gt_2k           = int(metrics_df["Sum of NOB >2K"].sum())  if not metrics_df.empty else 0
    mtd_regs        = int(metrics_df["MTD MSR Registration"].sum()) if not metrics_df.empty else 0
    n_stores        = int(metrics_df.shape[0])
    cur_month = _current_month_period(filtered_df)
    cur_label = cur_month.strftime("%b-%y") if cur_month is not None else "—"

    c = st.columns(4, gap="medium")
    with c[0]:
        render_kpi_card("Total Customers", f"{total_cust:,}",
                        f"Across {n_stores} stores", "blue")
    with c[1]:
        render_kpi_card("MSR Members", f"{msr_members:,}",
                        f"MTD Reg: {mtd_regs:,} ({cur_label})", "gold")
    with c[2]:
        render_kpi_card("Conversion %", f"{conv:.1f}%",
                        "MSR / Total Customers", "green")
    with c[3]:
        render_kpi_card(">2K Customers", f"{gt_2k:,}",
                        "Monthly cumulative spend", "red")


def _plot_layout(fig, height=380, legend_bottom=True):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(family="Inter, Helvetica, Arial", color="#1a2332"),
        title_font=dict(size=14, color="#0B2545"),
        hoverlabel=dict(bgcolor="#0B2545", font_color="#fff"),
    )
    if legend_bottom:
        fig.update_layout(legend=dict(
            orientation="h", y=-0.18, x=0.5, xanchor="center",
            bgcolor="rgba(0,0,0,0)",
        ))
    fig.update_xaxes(showgrid=False, linecolor="#e1e7f0")
    fig.update_yaxes(gridcolor="#eef1f6", linecolor="#e1e7f0")
    return fig


def render_charts(metrics_df: pd.DataFrame, filtered_df: pd.DataFrame):
    if metrics_df.empty:
        return

    # Top 10 stores by customers
    top_stores = metrics_df.head(10).copy()
    top_stores["label"] = top_stores["Store Name"] + " (" + top_stores["Store Code"] + ")"

    c1, c2 = st.columns((1.3, 1))
    with c1:
        fig = px.bar(
            top_stores.sort_values("Total Customers"),
            x="Total Customers", y="label", orientation="h",
            title="Top 10 Stores by Total Customers",
            color="Total Customers",
            color_continuous_scale=SEQ_BLUE,
            text="Total Customers",
        )
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(coloraxis_showscale=False, yaxis_title=None, xaxis_title=None)
        st.plotly_chart(_plot_layout(fig, height=430, legend_bottom=False),
                        use_container_width=True)

    with c2:
        msr_total     = int(metrics_df["MSR Members"].sum())
        non_msr_total = int(metrics_df["Non MSR Members"].sum())
        fig = go.Figure(data=[go.Pie(
            labels=["MSR Members", "Non-MSR"],
            values=[msr_total, non_msr_total],
            hole=0.6,
            marker=dict(colors=[PALETTE["gold"], PALETTE["grey"]],
                        line=dict(color="#fff", width=2)),
            textinfo="label+percent",
        )])
        fig.update_layout(title="MSR vs Non-MSR Split",
                          annotations=[dict(
                              text=f"<b>{msr_total:,}</b><br>MSR",
                              x=0.5, y=0.5, showarrow=False,
                              font=dict(size=15, color="#0B2545"))])
        st.plotly_chart(_plot_layout(fig, height=430), use_container_width=True)

    # MSR vs Non-MSR per store + >2K / <2K stacked
    c3, c4 = st.columns(2)
    with c3:
        long = top_stores.melt(
            id_vars=["label"], value_vars=["MSR Members", "Non MSR Members"],
            var_name="Segment", value_name="Customers",
        )
        fig = px.bar(
            long, x="label", y="Customers", color="Segment", barmode="group",
            title="MSR vs Non-MSR by Store (Top 10)",
            color_discrete_map={"MSR Members": PALETTE["gold"],
                                "Non MSR Members": PALETTE["grey"]},
        )
        fig.update_layout(xaxis_title=None, yaxis_title=None, xaxis_tickangle=-30)
        st.plotly_chart(_plot_layout(fig), use_container_width=True)

    with c4:
        long2 = top_stores.melt(
            id_vars=["label"], value_vars=["Sum of NOB >2K", "Sum of NOB <2K"],
            var_name="Slab", value_name="Customers",
        )
        fig = px.bar(
            long2, x="label", y="Customers", color="Slab", barmode="stack",
            title=">2K vs <2K Customers by Store (Top 10)",
            color_discrete_map={"Sum of NOB >2K": PALETTE["blue"],
                                "Sum of NOB <2K": PALETTE["teal"]},
        )
        fig.update_layout(xaxis_title=None, yaxis_title=None, xaxis_tickangle=-30)
        st.plotly_chart(_plot_layout(fig), use_container_width=True)

    # Monthly conversion trend
    if "shopping_month" in filtered_df.columns and filtered_df["shopping_month"].notna().any():
        month_df = (
            filtered_df
            .assign(_is_msr=filtered_df["is_msr"].astype(int))
            .groupby(["shopping_period", "shopping_month"])
            .agg(total=("mobile_number", "nunique"),
                 msr=("mobile_number",
                      lambda s: filtered_df.loc[s.index]
                                           .loc[filtered_df.loc[s.index, "is_msr"],
                                                "mobile_number"].nunique()))
            .reset_index()
            .sort_values("shopping_period")
        )
        month_df["Conversion %"] = np.where(
            month_df["total"] > 0,
            month_df["msr"] / month_df["total"] * 100, 0
        ).round(2)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=month_df["shopping_month"], y=month_df["Conversion %"],
            mode="lines+markers", name="Conversion %",
            line=dict(color=PALETTE["blue"], width=3),
            marker=dict(size=10, color=PALETTE["gold"],
                        line=dict(width=2, color="#fff")),
            fill="tozeroy", fillcolor="rgba(28, 109, 208, 0.10)",
        ))
        fig.update_layout(title="Monthly Conversion Trend",
                          yaxis_title="Conversion %", xaxis_title=None)
        st.plotly_chart(_plot_layout(fig, legend_bottom=False),
                        use_container_width=True)

    # Heatmap: Region vs Conversion % (only if region column present)
    if "region_name" in filtered_df.columns and \
       filtered_df["region_name"].notna().any() and \
       "shopping_month" in filtered_df.columns:

        heat = (
            filtered_df.groupby(["region_name", "shopping_period", "shopping_month"])
            .agg(total=("mobile_number", "nunique"),
                 msr=("mobile_number",
                      lambda s: filtered_df.loc[s.index]
                                           .loc[filtered_df.loc[s.index, "is_msr"],
                                                "mobile_number"].nunique()))
            .reset_index()
        )
        heat["Conversion %"] = np.where(
            heat["total"] > 0, heat["msr"] / heat["total"] * 100, 0
        ).round(1)
        if not heat.empty:
            order = heat.sort_values("shopping_period")["shopping_month"].drop_duplicates().tolist()
            pivot = heat.pivot_table(
                index="region_name", columns="shopping_month",
                values="Conversion %", aggfunc="mean",
            ).reindex(columns=order)
            fig = px.imshow(
                pivot, text_auto=".1f", aspect="auto",
                color_continuous_scale=SEQ_GOLD,
                title="Conversion % Heatmap · Region × Shopping Month",
            )
            fig.update_layout(xaxis_title=None, yaxis_title=None)
            st.plotly_chart(_plot_layout(fig, height=max(280, 80 + 40 * len(pivot))),
                            use_container_width=True)


def render_table(metrics_df: pd.DataFrame):
    if metrics_df.empty:
        st.markdown(
            '<div class="empty-state"><div class="big">📭</div>'
            "<div>No records match the current filters.</div></div>",
            unsafe_allow_html=True,
        )
        return

    display = metrics_df.copy()
    # Format numeric columns
    int_cols = [
        "Total Customers", "MTD MSR Registration", "MSR Members",
        "Non MSR Members", "Sum of NOB >2K", "Sum of NOB <2K",
        "Unique Customers (Single Bill >2K)",
    ]
    styler = display.style.format(
        {c: "{:,}" for c in int_cols if c in display.columns}
        | {"Conversion %": "{:.2f}%"}
    )
    # Colour highlight conversion
    if "Conversion %" in display.columns:
        styler = styler.background_gradient(
            subset=["Conversion %"], cmap="RdYlGn", vmin=0, vmax=100,
        )
    if "Total Customers" in display.columns:
        styler = styler.bar(
            subset=["Total Customers"], color="#DCE7F5", align="left",
        )
    styler = styler.set_properties(**{"text-align": "center", "font-size": "13px"})
    styler = styler.set_table_styles([
        {"selector": "th",
         "props": [("background-color", "#0B2545"), ("color", "white"),
                   ("font-weight", "600"), ("text-align", "center")]}
    ])
    st.dataframe(styler, use_container_width=True, height=500)


# ---------------------------------------------------------------------------
# Dashboard page
# ---------------------------------------------------------------------------

def dashboard_page():
    raw = st.session_state.raw_df
    if raw is None or raw.empty:
        st.warning("No data loaded. Returning to the data source page.")
        st.session_state.page = "landing"
        st.rerun()
        return

    try:
        df = process_data(raw)
    except Exception as e:
        st.error(f"Data processing failed: {e}")
        if st.button("← Back to data source"):
            st.session_state.page = "landing"
            st.rerun()
        return

    render_hero("Store-level customer & MSR performance")

    if df.attrs.get("dropped_untagged", 0):
        st.caption(
            f"ℹ️ Removed {df.attrs['dropped_untagged']:,} rows tagged as "
            "'Untagged' in NOC Tagging."
        )

    # Build filter UI first (needs the full df for options)
    metrics_all = calculate_metrics(df)
    filters = render_sidebar(df, metrics_all)

    # Apply filters
    filtered = apply_filters(df, filters)
    metrics  = calculate_metrics(filtered)

    if filtered.empty:
        st.markdown(
            '<div class="empty-state"><div class="big">🔍</div>'
            "<div>No rows match the current filter set. "
            "Try broadening your selection.</div></div>",
            unsafe_allow_html=True,
        )
        return

    # KPIs
    render_section("Executive Summary", "📌")
    render_kpis(metrics, filtered)

    # Charts
    render_section("Visual Analytics", "📈")
    render_charts(metrics, filtered)

    # Table
    render_section("Store-level Metrics", "🏬")
    st.caption(
        f"Showing **{len(metrics):,}** stores · "
        f"**{len(filtered):,}** filtered transactions · "
        f"**{filtered['mobile_number'].nunique():,}** unique customers."
    )
    render_table(metrics)


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

def main():
    if st.session_state.page == "landing" or not st.session_state.data_loaded:
        landing_page()
    else:
        dashboard_page()


if __name__ == "__main__":
    main()
