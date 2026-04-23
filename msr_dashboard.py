"""
MySpencers Rewards (MSR) Dashboard — Enhanced
==============================================
Features:
  - Multi-file upload & consolidation
  - Date normalisation (dd-mm-yyyy) on ingestion
  - MTD enrollment from msr_month (mmm-yy)
  - Reporting month from month_name (mmm-yy) with dropdown
  - MSR member = non-null / non-zero msr_number; otherwise Non-MSR
  - Conversion % colour-coded
  - New "Drill-Down" tab: day-wise & store-wise detailed table
  - Export CSV / Excel with headers

Run:
    pip install streamlit pandas plotly openpyxl xlsxwriter
    streamlit run msr_dashboard.py
"""

from __future__ import annotations

import io
from datetime import datetime, date
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

CUSTOM_CSS = """
<style>
    html, body, [class*="css"] {
        font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif !important;
        color: #1a2332;
    }
    .main .block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1440px; }
    .hero {
        background: linear-gradient(135deg, #0B2545 0%, #13315C 50%, #1C4B82 100%);
        color: #fff; padding: 1.4rem 1.8rem; border-radius: 14px;
        margin-bottom: 1.2rem; box-shadow: 0 10px 30px rgba(11,37,69,0.18);
        display: flex; align-items: center; justify-content: space-between;
    }
    .hero h1 { margin:0; font-size:1.65rem; font-weight:700; letter-spacing:-0.5px; }
    .hero .tag { font-size:0.88rem; opacity:0.85; margin-top:0.2rem; }
    .hero .badge {
        background: rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.25);
        padding: 0.35rem 0.8rem; border-radius:999px; font-size:0.78rem; font-weight:500;
    }
    .kpi-card {
        background:#fff; border-radius:14px; padding:1.1rem 1.2rem;
        box-shadow: 0 2px 8px rgba(12,28,55,0.06); border:1px solid #eef1f6;
        transition: transform .18s ease, box-shadow .18s ease; height:100%;
    }
    .kpi-card:hover { transform: translateY(-2px); box-shadow: 0 8px 22px rgba(12,28,55,.10); }
    .kpi-label { font-size:.78rem; text-transform:uppercase; letter-spacing:1.1px; color:#5b6b82; font-weight:600; margin-bottom:.4rem; }
    .kpi-value { font-size:1.9rem; font-weight:800; color:#0B2545; line-height:1.1; }
    .kpi-sub { font-size:.78rem; color:#7a8ba3; margin-top:.35rem; }
    .kpi-accent-blue  { border-top:4px solid #1C6DD0; }
    .kpi-accent-gold  { border-top:4px solid #D4A017; }
    .kpi-accent-green { border-top:4px solid #2A9D8F; }
    .kpi-accent-red   { border-top:4px solid #E76F51; }
    .section-title {
        font-size:1.1rem; font-weight:700; color:#0B2545;
        margin:1.5rem 0 0.7rem 0; padding-bottom:.4rem;
        border-bottom:2px solid #eef1f6; display:flex; align-items:center; gap:.5rem;
    }
    .section-title .dot { width:8px; height:8px; border-radius:50%; background:linear-gradient(135deg,#D4A017,#f5c646); }
    [data-testid="stDataFrame"] { border-radius:10px; overflow:hidden; border:1px solid #eef1f6; }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);
        border-right:1px solid #e1e7f0;
    }
    .stButton>button {
        background: linear-gradient(135deg,#1C6DD0 0%,#0B2545 100%);
        color:#fff; border:none; border-radius:8px; padding:.5rem 1rem;
        font-weight:600; transition:all .2s ease;
    }
    .stButton>button:hover { transform:translateY(-1px); box-shadow:0 6px 16px rgba(28,109,208,.25); }
    .stDownloadButton>button {
        background:#fff; color:#0B2545; border:1.5px solid #1C6DD0;
        border-radius:8px; font-weight:600; width:100%;
    }
    .stDownloadButton>button:hover { background:#1C6DD0; color:#fff; }
    #MainMenu,footer,header { visibility:hidden; }
    .conv-high   { background:#d4edda !important; color:#155724 !important; font-weight:700; }
    .conv-medium { background:#fff3cd !important; color:#856404 !important; font-weight:700; }
    .conv-low    { background:#f8d7da !important; color:#721c24 !important; font-weight:700; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

PALETTE   = {"navy":"#0B2545","blue":"#1C6DD0","gold":"#D4A017","teal":"#2A9D8F","red":"#E76F51","grey":"#8A9BB4"}
SEQ_BLUE  = ["#DCE7F5","#AAC4E8","#6E99D1","#3C73B8","#1C4B82","#0B2545"]
SEQ_GOLD  = ["#FDF2D1","#F9DF8A","#ECC24C","#D4A017","#A87C0A","#6E5008"]

REQUIRED_COLS = [
    "store_code","store_name","mobile_number","bill_no",
    "grs_sales","msr_number","msr_month","noc_tagging","msr_tagging","asm_name",
]
DATE_COLS = ["calendar_day","month_name"]

# ────────────────────────────────────────────────────────────────────────────
# Session state
# ────────────────────────────────────────────────────────────────────────────
def _init_state():
    for k,v in {"raw_df":None,"data_loaded":False,"data_source":None,"page":"landing","uploaded_files_info":[]}.items():
        if k not in st.session_state:
            st.session_state[k] = v
_init_state()

# ────────────────────────────────────────────────────────────────────────────
# Date helpers
# ────────────────────────────────────────────────────────────────────────────
def _parse_flexible_date(series: pd.Series) -> pd.Series:
    """Try many date formats; return a datetime64 Series."""
    for fmt in ["%d-%m-%Y","%d/%m/%Y","%Y-%m-%d","%m-%d-%Y","%d-%b-%Y",
                "%d %b %Y","%b-%y","%b %y","%Y/%m/%d"]:
        try:
            parsed = pd.to_datetime(series, format=fmt, errors="coerce")
            if parsed.notna().sum() > len(series) * 0.5:
                return parsed
        except Exception:
            continue
    return pd.to_datetime(series, errors="coerce", dayfirst=True)

def _to_dd_mm_yyyy(series: pd.Series) -> pd.Series:
    """Convert a datetime series to dd-mm-yyyy strings."""
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

    # Validate
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

    # ── PARSE & NORMALISE DATES to dd-mm-yyyy ──────────────────────────────

    # calendar_day
    if "calendar_day" in df.columns:
        df["calendar_day_dt"] = _parse_flexible_date(df["calendar_day"].astype(str))
        df["calendar_day"]    = _to_dd_mm_yyyy(df["calendar_day_dt"])

    # month_name  (e.g. "Apr-26" → parse → store as datetime AND mmm-yy label)
    if "month_name" in df.columns:
        df["month_name_dt"]  = _parse_flexible_date(df["month_name"].astype(str))
        df["reporting_month"] = df["month_name_dt"].dt.strftime("%b-%y")

    # msr_month  (e.g. "Nov-25" or a full date)
    if "msr_month" in df.columns:
        df["msr_month_dt"]  = _parse_flexible_date(df["msr_month"].astype(str))
        df["enroll_month"]  = df["msr_month_dt"].dt.strftime("%b-%y")
        df["enroll_period"] = df["msr_month_dt"].dt.to_period("M")

    # Shopping date & period (prefer calendar_day_dt)
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

    # ── MSR FLAG ──────────────────────────────────────────────────────────
    # A customer is MSR if msr_number is NOT null/zero (regardless of text tag)
    msr_num_valid = pd.to_numeric(df["msr_number"], errors="coerce").fillna(0) > 0
    df["is_msr"] = msr_num_valid

    # Numeric coercions
    for c in ["grs_sales","nob_ach","billed_qty","bill_no"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    return df

# ────────────────────────────────────────────────────────────────────────────
# Metrics
# ────────────────────────────────────────────────────────────────────────────
def _latest_period(df):
    per = df["shopping_period"].dropna() if "shopping_period" in df.columns else pd.Series(dtype="object")
    return per.max() if not per.empty else None

@st.cache_data(show_spinner=False)
def calculate_metrics(df: pd.DataFrame, mtd_month_label: Optional[str] = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    group_cols = [c for c in ["store_code","store_name","asm_name"] if c in df.columns]

    # Determine MTD month
    if mtd_month_label:
        mtd_mask = df["enroll_month"] == mtd_month_label if "enroll_month" in df.columns else pd.Series(False, index=df.index)
    else:
        cur = _latest_period(df)
        mtd_mask = (df["enroll_period"] == cur) if (cur is not None and "enroll_period" in df.columns) else pd.Series(False, index=df.index)

    total_cust = df.groupby(group_cols)["mobile_number"].nunique().rename("Total NOC")
    mtd        = df[mtd_mask].groupby(group_cols)["mobile_number"].nunique().rename("MTD Enrollment")
    msr_cnt    = df[df["is_msr"]].groupby(group_cols)["mobile_number"].nunique().rename("Unique MSR Members")
    non_msr    = df[~df["is_msr"]].groupby(group_cols)["mobile_number"].nunique().rename("Unique Non-MSR Members")

    # >2K / <2K per customer cumulative spend
    spend_grp  = df.groupby(group_cols + ["mobile_number"])["grs_sales"].sum().reset_index()
    nob_gt = spend_grp[spend_grp["grs_sales"] > 2000].groupby(group_cols)["mobile_number"].nunique().rename("Bills >2K")
    nob_lt = spend_grp[spend_grp["grs_sales"] <= 2000].groupby(group_cols)["mobile_number"].nunique().rename("Bills ≤2K")

    metrics = pd.concat([total_cust, mtd, msr_cnt, non_msr, nob_gt, nob_lt], axis=1).fillna(0).astype(int, errors="ignore").reset_index()

    metrics["Conversion %"] = np.where(
        metrics["Total NOC"] > 0,
        (metrics["MTD Enrollment"] / metrics["Total NOC"] * 100).round(2), 0.0
    )

    rename = {"store_code":"Store Code","store_name":"Store Name","asm_name":"ASM Name"}
    metrics = metrics.rename(columns=rename)
    cols = [c for c in (list(rename.values()) + ["Total NOC","MTD Enrollment","Unique MSR Members","Unique Non-MSR Members","Conversion %","Bills >2K","Bills ≤2K"]) if c in metrics.columns]
    return metrics[cols].sort_values("Total NOC", ascending=False)


@st.cache_data(show_spinner=False)
def calculate_drilldown(df: pd.DataFrame, mtd_month_label: Optional[str] = None) -> pd.DataFrame:
    """Day-wise × store-wise breakdown."""
    if df.empty or "shopping_date" not in df.columns:
        return pd.DataFrame()

    # Format day as dd-mm-yyyy
    df = df.copy()
    df["Day"] = df["shopping_date"].dt.strftime("%d-%m-%Y")

    group = ["Day","store_code","store_name"]
    group = [c for c in group if c in df.columns]

    if mtd_month_label:
        mtd_mask = df["enroll_month"] == mtd_month_label if "enroll_month" in df.columns else pd.Series(False, index=df.index)
    else:
        cur = _latest_period(df)
        mtd_mask = (df["enroll_period"] == cur) if (cur is not None and "enroll_period" in df.columns) else pd.Series(False, index=df.index)

    total_noc  = df.groupby(group)["mobile_number"].nunique().rename("Total NOC")
    enrollment = df[mtd_mask].groupby(group)["mobile_number"].nunique().rename("Enrollment")
    msr_cnt    = df[df["is_msr"]].groupby(group)["mobile_number"].nunique().rename("Unique MSR Members")
    non_msr    = df[~df["is_msr"]].groupby(group)["mobile_number"].nunique().rename("Unique Non-MSR Members")

    spend_grp  = df.groupby(group + ["mobile_number"])["grs_sales"].sum().reset_index()
    nob_gt = spend_grp[spend_grp["grs_sales"] > 2000].groupby(group)["mobile_number"].nunique().rename("Bills >2K")
    nob_lt = spend_grp[spend_grp["grs_sales"] <= 2000].groupby(group)["mobile_number"].nunique().rename("Bills ≤2K")

    dd = pd.concat([total_noc, enrollment, msr_cnt, non_msr, nob_gt, nob_lt], axis=1).fillna(0).astype(int, errors="ignore").reset_index()
    dd["Conversion %"] = np.where(dd["Total NOC"] > 0, (dd["Enrollment"] / dd["Total NOC"] * 100).round(2), 0.0)

    rename = {"store_code":"Store Code","store_name":"Store Name"}
    dd = dd.rename(columns=rename)
    col_order = ["Day","Store Code","Store Name","Total NOC","Enrollment","Unique MSR Members","Unique Non-MSR Members","Conversion %","Bills >2K","Bills ≤2K"]
    col_order = [c for c in col_order if c in dd.columns]
    # Sort by Day desc then Store Code
    dd = dd[col_order].sort_values(["Day","Store Code"], ascending=[False,True])
    return dd

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
    return df.to_csv(index=False).encode("utf-8-sig")  # BOM for Excel compat

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
    st.markdown(f'<div class="section-title"><span class="dot"></span>{icon} {title}</div>', unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────────────────
# Conversion % colouring
# ────────────────────────────────────────────────────────────────────────────
def color_conversion(val):
    try:
        v = float(str(val).replace("%",""))
    except Exception:
        return ""
    if v >= 15:
        return "background-color:#d4edda; color:#155724; font-weight:700"
    elif v >= 8:
        return "background-color:#fff3cd; color:#856404; font-weight:700"
    else:
        return "background-color:#f8d7da; color:#721c24; font-weight:700"

def style_metrics(df: pd.DataFrame):
    """Return a Styler with conversion % coloured."""
    s = df.style
    if "Conversion %" in df.columns:
        s = s.applymap(color_conversion, subset=["Conversion %"])
    return s

# ────────────────────────────────────────────────────────────────────────────
# Landing page
# ────────────────────────────────────────────────────────────────────────────
def landing_page():
    render_hero("Connect a data source to begin")
    st.write("")

    st.markdown("""
    <div style="background:#fff;border:1px solid #e6ebf2;border-radius:14px;padding:1.4rem;margin-bottom:1rem;">
        <h3 style="color:#0B2545;margin:0 0 .5rem 0;">📁 Upload CSV / Excel</h3>
        <p style="color:#5b6b82;margin:0;font-size:.9rem;">
            Upload one or <b>multiple files</b> — they will be consolidated automatically before analysis.
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

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚀 Load & Analyse", use_container_width=True, disabled=not uploaded):
            dfs, info = [], []
            for f in uploaded:
                try:
                    with st.spinner(f"Parsing {f.name}…"):
                        raw = load_single(f.getvalue(), f.name)
                    dfs.append(raw)
                    info.append(f.name)
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
    with c2:
        if st.button("🧪 Try with sample data", use_container_width=True):
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
        enroll  = sold - pd.Timedelta(days=int(rng.integers(0,60)*30//30)) if is_msr else pd.NaT
        sales   = int(rng.integers(150,6000))
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
        st.sidebar.caption("Loaded: " + " | ".join(st.session_state.uploaded_files_info))

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔎 Search")
    search = st.sidebar.text_input("Store Code / MSR / Mobile", placeholder="e.g. S070", label_visibility="collapsed")

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
                       key=lambda s: pd.to_datetime(s, format="%b-%y", errors="coerce")) if "shopping_month" in df.columns else []
    shopping_months = st.sidebar.multiselect("Shopping Month", shop_opts, default=[])

    enroll_opts = sorted(df["enroll_month"].dropna().unique().tolist(),
                         key=lambda s: pd.to_datetime(s, format="%b-%y", errors="coerce")) if "enroll_month" in df.columns else []
    enroll_months = st.sidebar.multiselect("Enroll Month (MTD)", enroll_opts, default=[])

    # Reporting Month filter (from month_name)
    report_opts = sorted(df["reporting_month"].dropna().unique().tolist(),
                         key=lambda s: pd.to_datetime(s, format="%b-%y", errors="coerce")) if "reporting_month" in df.columns else []
    reporting_month = st.sidebar.selectbox("Reporting Month", ["All"] + report_opts)

    # Exports
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📤 Export Summary")
    if not metrics_df.empty:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        st.sidebar.download_button("⬇️ CSV – Summary",  to_csv_bytes(metrics_df),
            f"msr_summary_{ts}.csv", "text/csv", use_container_width=True)
        try:
            st.sidebar.download_button("⬇️ Excel – Summary", to_excel_bytes(metrics_df, "Summary"),
                f"msr_summary_{ts}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)
        except Exception as e:
            st.sidebar.caption(f"Excel: {e}")

    st.sidebar.markdown("### 📤 Export Drill-Down")
    if not dd_df.empty:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        st.sidebar.download_button("⬇️ CSV – Drill-Down",  to_csv_bytes(dd_df),
            f"msr_drilldown_{ts}.csv", "text/csv", use_container_width=True)
        try:
            st.sidebar.download_button("⬇️ Excel – Drill-Down", to_excel_bytes(dd_df, "DrillDown"),
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
    with c[0]: kpi("Total Unique NOC", f"{total:,}", f"Across {n_stores} stores", "blue")
    with c[1]: kpi("Unique MSR Members", f"{msr_mem:,}", f"MTD Enrollment: {mtd_reg:,} ({mtd_label})", "gold")
    with c[2]: kpi("Conversion %", f"{conv:.1f}%", "MTD Enrollment / Total NOC", "green")
    with c[3]: kpi("Bills >₹2K", f"{gt2k:,}", "Cumulative monthly spend", "red")

# ────────────────────────────────────────────────────────────────────────────
# Charts
# ────────────────────────────────────────────────────────────────────────────
def _layout(fig, h=380):
    fig.update_layout(
        height=h, margin=dict(l=10,r=10,t=40,b=10),
        plot_bgcolor="#fff", paper_bgcolor="#fff",
        font=dict(family="Inter,Helvetica,Arial", color="#1a2332"),
        title_font=dict(size=13, color="#0B2545"),
        hoverlabel=dict(bgcolor="#0B2545", font_color="#fff"),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(showgrid=False, linecolor="#e1e7f0")
    fig.update_yaxes(gridcolor="#eef1f6", linecolor="#e1e7f0")
    return fig

def render_charts(metrics_df, filtered_df):
    if metrics_df.empty: return
    top = metrics_df.head(10).copy()
    top["label"] = top["Store Name"] + " (" + top["Store Code"] + ")"

    c1, c2 = st.columns((1.4,1))
    with c1:
        fig = px.bar(top.sort_values("Total NOC"), x="Total NOC", y="label", orientation="h",
                     title="Top 10 Stores – Total NOC", color="Total NOC",
                     color_continuous_scale=SEQ_BLUE, text="Total NOC")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(coloraxis_showscale=False, yaxis_title=None, xaxis_title=None)
        st.plotly_chart(_layout(fig, 430), use_container_width=True)
    with c2:
        msr_t = int(metrics_df["Unique MSR Members"].sum())
        non_t = int(metrics_df["Unique Non-MSR Members"].sum())
        fig = go.Figure(data=[go.Pie(
            labels=["MSR Members","Non-MSR"],
            values=[msr_t, non_t], hole=0.6,
            marker=dict(colors=[PALETTE["gold"],PALETTE["grey"]], line=dict(color="#fff",width=2)),
            textinfo="label+percent",
        )])
        fig.update_layout(title="MSR vs Non-MSR Split",
                          annotations=[dict(text=f"<b>{msr_t:,}</b><br>MSR", x=0.5,y=0.5,showarrow=False,
                                            font=dict(size=14,color="#0B2545"))])
        st.plotly_chart(_layout(fig, 430), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        long = top.melt(id_vars=["label"], value_vars=["Unique MSR Members","Unique Non-MSR Members"],
                        var_name="Segment", value_name="Count")
        fig = px.bar(long, x="label", y="Count", color="Segment", barmode="group",
                     title="MSR vs Non-MSR by Store (Top 10)",
                     color_discrete_map={"Unique MSR Members":PALETTE["gold"],"Unique Non-MSR Members":PALETTE["grey"]})
        fig.update_layout(xaxis_title=None, yaxis_title=None, xaxis_tickangle=-30)
        st.plotly_chart(_layout(fig), use_container_width=True)
    with c4:
        long2 = top.melt(id_vars=["label"], value_vars=["Bills >2K","Bills ≤2K"],
                         var_name="Slab", value_name="Count")
        fig = px.bar(long2, x="label", y="Count", color="Slab", barmode="stack",
                     title="Bills >2K vs ≤2K (Top 10)",
                     color_discrete_map={"Bills >2K":PALETTE["blue"],"Bills ≤2K":PALETTE["teal"]})
        fig.update_layout(xaxis_title=None, yaxis_title=None, xaxis_tickangle=-30)
        st.plotly_chart(_layout(fig), use_container_width=True)

    # Monthly conversion trend
    if "shopping_month" in filtered_df.columns and filtered_df["shopping_month"].notna().any():
        trend = (
            filtered_df.groupby(["shopping_period","shopping_month"])
            .apply(lambda g: pd.Series({
                "Total": g["mobile_number"].nunique(),
                "MSR"  : g.loc[g["is_msr"],"mobile_number"].nunique(),
            })).reset_index().sort_values("shopping_period")
        )
        trend["Conversion %"] = np.where(trend["Total"]>0, trend["MSR"]/trend["Total"]*100, 0).round(2)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend["shopping_month"], y=trend["Conversion %"],
            mode="lines+markers", name="Conversion %",
            line=dict(color=PALETTE["blue"],width=3),
            marker=dict(size=10,color=PALETTE["gold"],line=dict(width=2,color="#fff")),
            fill="tozeroy", fillcolor="rgba(28,109,208,.10)",
        ))
        fig.update_layout(title="Monthly Conversion Trend", yaxis_title="Conversion %", xaxis_title=None)
        st.plotly_chart(_layout(fig, legend_bottom=False) if False else _layout(fig), use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# Table display
# ────────────────────────────────────────────────────────────────────────────
def render_table(metrics_df, label="Store-level"):
    if metrics_df.empty:
        st.info("No records match the current filters.")
        return
    display = metrics_df.copy()
    # Format Conversion %
    if "Conversion %" in display.columns:
        display["Conversion %"] = display["Conversion %"].apply(lambda v: f"{v:.2f}%")

    styled = style_metrics(display)
    st.dataframe(styled, use_container_width=True, height=480)

def render_drilldown_table(dd_df):
    if dd_df.empty:
        st.info("No drill-down data for current filters.")
        return
    display = dd_df.copy()
    if "Conversion %" in display.columns:
        display["Conversion %"] = display["Conversion %"].apply(lambda v: f"{v:.2f}%")
    styled = style_metrics(display)
    st.dataframe(styled, use_container_width=True, height=540)

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

    # ── Tabs ──────────────────────────────────────────────────────────────
    tab_summary, tab_drill = st.tabs(["📊 Summary Dashboard", "🔍 Drill-Down (Day × Store)"])

    with tab_summary:
        # We need filters — compute a preliminary metrics for sidebar
        metrics_all = calculate_metrics(df)
        dd_all      = calculate_drilldown(df)
        filters     = render_sidebar(df, metrics_all, dd_all)

        filtered = apply_filters(df, filters)
        if filtered.empty:
            st.warning("No rows match the current filters.")
            return

        # Determine MTD label
        rep_month = filters.get("reporting_month","All")
        if rep_month and rep_month != "All":
            # Use selected reporting month to drive MTD
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
        Total NOC, Enrollment, Unique MSR/Non-MSR members, Conversion %, Bills >2K & ≤2K.
        """)

        # Re-use filters from sidebar (already applied above)
        try:
            filtered_drill = filtered
            dd_df_display  = dd_df
        except NameError:
            filtered_drill = df
            dd_df_display  = calculate_drilldown(df)

        # Quick filter: store selector inside the tab
        stores_available = sorted(dd_df_display["Store Code"].dropna().unique().tolist()) if not dd_df_display.empty and "Store Code" in dd_df_display.columns else []
        sel_stores = st.multiselect("Filter by Store (Drill-Down only)", ["All"] + stores_available, default=["All"])
        if sel_stores and "All" not in sel_stores and not dd_df_display.empty:
            dd_df_display = dd_df_display[dd_df_display["Store Code"].isin(sel_stores)]

        st.caption(f"Showing **{len(dd_df_display):,}** rows")
        render_drilldown_table(dd_df_display)

        # In-tab export buttons
        c1, c2 = st.columns(2)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        with c1:
            st.download_button("⬇️ Export CSV", to_csv_bytes(dd_df_display),
                               f"drilldown_{ts}.csv", "text/csv", use_container_width=True)
        with c2:
            try:
                st.download_button("⬇️ Export Excel", to_excel_bytes(dd_df_display, "DrillDown"),
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
