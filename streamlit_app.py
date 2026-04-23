import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import anthropic

# ══════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Spencer's Rewards — Intelligence Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════════════
#  CUSTOM CSS
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap');

/* Global */
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.main { background: #0a0e1a; }

/* Hide default streamlit elements */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display:none;}

/* KPI Card */
.kpi-card {
    background: #131929;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 16px 14px;
    position: relative;
    overflow: hidden;
    margin-bottom: 0;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 12px 12px 0 0;
}
.kpi-card.amber::before { background: #f5a623; }
.kpi-card.red::before   { background: #e85d37; }
.kpi-card.blue::before  { background: #4fc3f7; }
.kpi-card.green::before { background: #66bb6a; }
.kpi-card.purple::before{ background: #ab47bc; }
.kpi-label {
    font-size: 10px; font-weight: 600;
    letter-spacing: .9px; text-transform: uppercase;
    color: #7a8398; margin-bottom: 7px;
}
.kpi-value {
    font-family: 'Syne', sans-serif;
    font-weight: 800; font-size: 24px;
    line-height: 1; margin-bottom: 4px; color: #e8eaf0;
}
.kpi-sub { font-size: 11px; color: #7a8398; }

/* Insight card */
.insight-card {
    background: #131929;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    gap: 11px;
    align-items: flex-start;
    margin-bottom: 8px;
}
.insight-icon {
    width: 38px; height: 38px;
    border-radius: 9px;
    display: flex; align-items: center;
    justify-content: center;
    font-size: 18px; flex-shrink: 0;
}
.insight-title { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 12px; color: #e8eaf0; margin-bottom: 3px; }
.insight-body  { font-size: 11px; color: #7a8398; line-height: 1.5; }
.insight-body strong { color: #f5a623; }

/* Section label */
.section-label {
    font-family: 'Syne', sans-serif;
    font-weight: 700; font-size: 11px;
    letter-spacing: 1.4px; text-transform: uppercase;
    color: #7a8398; margin-bottom: 11px;
    padding-bottom: 7px;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    display: flex; align-items: center; gap: 8px;
}

/* Tag */
.tag { display: inline-block; padding: 2px 8px; border-radius: 50px; font-size: 10px; font-weight: 600; }
.tag-green  { background: rgba(76,175,80,.12);  color: #4caf50; }
.tag-red    { background: rgba(239,83,80,.12);  color: #ef5350; }
.tag-blue   { background: rgba(79,195,247,.12); color: #4fc3f7; }
.tag-amber  { background: rgba(245,166,35,.12); color: #f5a623; }
.tag-muted  { background: rgba(255,255,255,.06);color: #7a8398; }

/* Leaderboard */
.lb-item {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 0;
    border-bottom: 1px solid rgba(255,255,255,.04);
    color: #e8eaf0;
}
.lb-rank { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 15px; color: #7a8398; min-width: 24px; }
.lb-rank.top { color: #f5a623; }
.lb-name { font-weight: 600; font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lb-meta { font-size: 10px; color: #7a8398; }
.lb-value { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 12px; min-width: 60px; text-align: right; }

/* Chat */
.chat-msg { padding: 10px 14px; border-radius: 12px; margin-bottom: 8px; font-size: 13px; line-height: 1.6; }
.chat-user { background: rgba(245,166,35,.12); border: 1px solid rgba(245,166,35,.2); color: #e8eaf0; margin-left: 20%; }
.chat-assistant { background: #131929; border: 1px solid rgba(255,255,255,.07); color: #e8eaf0; margin-right: 20%; }

/* Sidebar styling */
[data-testid="stSidebar"] {
    background: #0f1525;
    border-right: 1px solid rgba(255,255,255,0.07);
}

/* Header */
.dash-header {
    background: #131929;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    padding: 12px 20px;
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 20px;
}
.brand-text {
    font-family: 'Syne', sans-serif;
    font-weight: 800; font-size: 15px;
    letter-spacing: 2px; color: #f5a623;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════
MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
PALETTE = ['#f5a623','#4fc3f7','#66bb6a','#e85d37','#ab47bc','#26c6da',
           '#ff7043','#ffca28','#8bc34a','#5c6bc0','#ec407a','#29b6f6',
           '#9ccc65','#ffa726','#7e57c2']

PLOTLY_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='DM Sans', color='#7a8398'),
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(font=dict(color='#7a8398'), bgcolor='rgba(0,0,0,0)'),
    xaxis=dict(gridcolor='rgba(255,255,255,.05)', tickfont=dict(color='#7a8398')),
    yaxis=dict(gridcolor='rgba(255,255,255,.05)', tickfont=dict(color='#7a8398')),
)

def fmt_inr(n):
    if pd.isna(n) or n is None: return "—"
    n = float(n); sg = "-" if n < 0 else ""; a = abs(n)
    if a >= 1e7:  return f"{sg}₹{a/1e7:.1f}Cr"
    if a >= 1e5:  return f"{sg}₹{a/1e5:.1f}L"
    if a >= 1e3:  return f"{sg}₹{a/1e3:.1f}K"
    return f"{sg}₹{a:.0f}"

def fmt_num(n):
    if pd.isna(n) or n is None: return "—"
    n = float(n); sg = "-" if n < 0 else ""; a = abs(n)
    if a >= 1e7:  return f"{sg}{a/1e7:.1f}Cr"
    if a >= 1e5:  return f"{sg}{a/1e5:.1f}L"
    if a >= 1e3:  return f"{sg}{a/1e3:.1f}K"
    return f"{sg}{a:.1f}"

def month_to_num(s):
    if not s or not isinstance(s, str): return 0
    p = s.split('-')
    if len(p) != 2: return 0
    try:
        mi = MONTH_NAMES.index(p[0])
    except ValueError:
        return 0
    yr = int(p[1]); yr = 2000 + yr if yr < 100 else yr
    return yr * 12 + mi

def sub_months(s, n):
    k = month_to_num(s)
    if not k: return ''
    total = k - n; y, m = divmod(total, 12)
    return f"{MONTH_NAMES[m]}-{str(y)[-2:]}"

def detect_reporting_month(df):
    if 'enroll_month' not in df.columns: return ''
    nums = df['enroll_month'].map(month_to_num)
    idx = nums.idxmax()
    return df.loc[idx, 'enroll_month'] if idx is not None else ''

def kpi_card(label, value, sub, color="amber"):
    return f"""
    <div class="kpi-card {color}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>"""

def insight_card(icon, bg, title, body):
    return f"""
    <div class="insight-card">
        <div class="insight-icon" style="background:{bg}">{icon}</div>
        <div>
            <div class="insight-title">{title}</div>
            <div class="insight-body">{body}</div>
        </div>
    </div>"""

def bar_chart(df_series, x_col, y_col, title, color=None, horizontal=False,
              y_fmt=None, color_list=None):
    if df_series.empty:
        return go.Figure(layout=dict(**PLOTLY_LAYOUT, title=title))
    clr = color_list if color_list is not None else (color or PALETTE[0])
    if horizontal:
        fig = go.Figure(go.Bar(
            y=df_series[x_col], x=df_series[y_col],
            marker_color=clr, orientation='h',
            marker=dict(line=dict(width=0)),
        ))
        fig.update_layout(**PLOTLY_LAYOUT, title=dict(text=title, font=dict(color='#e8eaf0', size=13, family='Syne')),
                          yaxis=dict(autorange='reversed', **PLOTLY_LAYOUT['yaxis']))
    else:
        fig = go.Figure(go.Bar(
            x=df_series[x_col], y=df_series[y_col],
            marker_color=clr,
            marker=dict(line=dict(width=0)),
        ))
        fig.update_layout(**PLOTLY_LAYOUT, title=dict(text=title, font=dict(color='#e8eaf0', size=13, family='Syne')))
    if y_fmt == 'inr':
        axis = fig.layout.xaxis if horizontal else fig.layout.yaxis
        axis.tickprefix = '₹'
    return fig

def donut_chart(labels, values, title, colors=None):
    clrs = colors or PALETTE[:len(labels)]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.6, marker=dict(colors=clrs, line=dict(width=0)),
        textfont=dict(color='#7a8398', size=11),
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title=dict(text=title, font=dict(color='#e8eaf0', size=13, family='Syne')),
                      showlegend=True)
    return fig

def leaderboard_html(items, name_fn, value_fn, meta_fn, bad=False):
    html = ""
    for i, it in enumerate(items):
        rank_cls = "top" if i < 3 and not bad else ""
        html += f"""
        <div class="lb-item">
            <div class="lb-rank {rank_cls}">{i+1}</div>
            <div style="flex:1;min-width:0">
                <div class="lb-name">{name_fn(it)}</div>
                <div class="lb-meta">{meta_fn(it)}</div>
            </div>
            <div class="lb-value">{value_fn(it)}</div>
        </div>"""
    return html

# ══════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════
if 'df' not in st.session_state:
    st.session_state.df = None
if 'reporting_month' not in st.session_state:
    st.session_state.reporting_month = ''
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'api_key' not in st.session_state:
    st.session_state.api_key = ''

# ══════════════════════════════════════════════════════════════
#  UPLOAD SCREEN
# ══════════════════════════════════════════════════════════════
if st.session_state.df is None:
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px 20px;">
        <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:14px;
                    letter-spacing:4px;text-transform:uppercase;color:#f5a623;margin-bottom:40px;">
            ● SPENCER'S REWARDS
        </div>
        <h1 style="font-family:'Syne',sans-serif;font-weight:800;font-size:48px;
                   line-height:1.1;letter-spacing:-1.5px;color:#e8eaf0;margin-bottom:12px;">
            Rewards <span style="color:#f5a623;">Intelligence</span><br>Dashboard
        </h1>
        <p style="color:#7a8398;font-size:16px;max-width:480px;margin:0 auto 40px;">
            Upload your Spencer's My Rewards CSV export to generate instant analytics,
            charts, and AI-powered insights.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        uploaded = st.file_uploader(
            "Drop your CSV file here", type=['csv'],
            label_visibility="collapsed"
        )

        months = [f"{m}-{str(y)[-2:]}" for y in [25,26] for m in MONTH_NAMES]
        rm_sel = st.selectbox("📅 Reporting Month (auto-detected if left as Auto)",
                              ["Auto"] + months, index=0)

        if uploaded:
            with st.spinner("Processing data…"):
                df = pd.read_csv(uploaded, low_memory=False)
                df = df[df['store_code'].notna()] if 'store_code' in df.columns else df

                # Numeric coercion
                num_cols = ['current_bill_value','cashback_earned_current_month',
                            'redemed_amount_current_month','incremental_sales',
                            'current_nob','past_six_months_average_nob',
                            'past_six_months_average_ams','current_asp',
                            'current_ams_slab']
                for c in num_cols:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

                rm = rm_sel if rm_sel != "Auto" else detect_reporting_month(df)
                st.session_state.df = df
                st.session_state.reporting_month = rm
                st.session_state.chat_history = []
            st.rerun()
    st.stop()

# ══════════════════════════════════════════════════════════════
#  SIDEBAR NAVIGATION & FILTERS
# ══════════════════════════════════════════════════════════════
df_all = st.session_state.df
rm = st.session_state.reporting_month

with st.sidebar:
    st.markdown(f"""
    <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:14px;
                letter-spacing:2px;color:#f5a623;padding:14px 4px 6px;">
        ● SPENCER'S
    </div>
    <div style="font-size:11px;color:#7a8398;padding:0 4px 14px;
                border-bottom:1px solid rgba(255,255,255,0.07);">
        {len(df_all):,} records · 📅 {rm}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top:12px;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;color:#7a8398;padding:4px;'>Analytics</div>", unsafe_allow_html=True)
    tab = st.radio("", [
        "📊 Overview",
        "🔄 Return Rate",
        "👥 Customers",
        "🏪 Stores",
        "💳 Cashback & Sales",
        "🗺️ Geography",
        "📉 Lost Sales",
        "🔍 Data Explorer",
    ], label_visibility="collapsed")

    st.markdown("<div style='margin-top:12px;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;color:#7a8398;padding:4px;'>Intelligence</div>", unsafe_allow_html=True)
    if st.button("🤖 AI Analyst", use_container_width=True):
        tab = "🤖 AI Analyst"
        st.session_state['active_tab'] = "🤖 AI Analyst"

    # Store tab in session so AI button works
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = tab
    if tab != "📊 Overview" or st.session_state.active_tab == "🤖 AI Analyst":
        st.session_state.active_tab = tab

    st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:16px 0 10px;'>", unsafe_allow_html=True)

    # ── Filters ──
    st.markdown("<div style='font-size:10px;letter-spacing:1px;text-transform:uppercase;color:#7a8398;margin-bottom:6px;'>Filters</div>", unsafe_allow_html=True)

    def uniq(col):
        if col not in df_all.columns: return []
        return sorted(df_all[col].dropna().unique().tolist())

    search = st.text_input("🔍 Search customer / store", placeholder="Type to search…")
    f_region  = st.selectbox("Region",   ["All"] + uniq('region_name'))
    f_city    = st.selectbox("City",     ["All"] + uniq('city_name'))
    f_cluster = st.selectbox("Cluster",  ["All"] + uniq('cluster_name'))
    f_store   = st.selectbox("Store",    ["All"] + uniq('store_name'))
    f_format  = st.selectbox("Format",   ["All"] + uniq('format_type'))
    f_shopper = st.selectbox("Shopper",  ["All"] + uniq('shopper_behaviour'))
    f_ctype   = st.selectbox("Cust Type",["All"] + uniq('customer_type'))
    f_month   = st.selectbox("Month",    ["All"] + uniq('enroll_month'))

    if st.button("✕ Clear Filters", use_container_width=True):
        st.rerun()

    st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:10px 0;'>", unsafe_allow_html=True)
    if st.button("↩ New Upload", use_container_width=True):
        st.session_state.df = None
        st.session_state.chat_history = []
        st.rerun()

    st.markdown("<div style='font-size:10px;color:#7a8398;text-align:center;opacity:.6;margin-top:auto;padding:8px;'>Spencer's Intelligence v3</div>", unsafe_allow_html=True)

# ── Apply filters ──
df = df_all.copy()
def safe_filter(df, col, val):
    if val != "All" and col in df.columns:
        df = df[df[col] == val]
    return df

df = safe_filter(df, 'region_name', f_region)
df = safe_filter(df, 'city_name', f_city)
df = safe_filter(df, 'cluster_name', f_cluster)
df = safe_filter(df, 'store_name', f_store)
df = safe_filter(df, 'format_type', f_format)
df = safe_filter(df, 'shopper_behaviour', f_shopper)
df = safe_filter(df, 'customer_type', f_ctype)
df = safe_filter(df, 'enroll_month', f_month)
if search:
    mask = pd.Series([False] * len(df), index=df.index)
    for col in ['customer_name','store_name','city_name','cluster_name']:
        if col in df.columns:
            mask |= df[col].astype(str).str.lower().str.contains(search.lower(), na=False)
    df = df[mask]

# Use active tab
active = st.session_state.get('active_tab', tab)

# ══════════════════════════════════════════════════════════════
#  TAB: OVERVIEW
# ══════════════════════════════════════════════════════════════
if active == "📊 Overview":
    st.markdown("<div class='section-label'>Key Performance Indicators</div>", unsafe_allow_html=True)

    rev   = df['current_bill_value'].sum() if 'current_bill_value' in df.columns else 0
    sh    = df[df['shopper_behaviour'] == 'Shopped'] if 'shopper_behaviour' in df.columns else df
    conv  = len(sh) / len(df) * 100 if len(df) else 0
    ab    = df[df['current_bill_value'] > 0]['current_bill_value'].mean() if 'current_bill_value' in df.columns else 0
    cb    = df['cashback_earned_current_month'].sum() if 'cashback_earned_current_month' in df.columns else 0
    red   = df['redemed_amount_current_month'].sum() if 'redemed_amount_current_month' in df.columns else 0
    stores = df['store_code'].nunique() if 'store_code' in df.columns else 0
    rr    = (red / cb * 100) if cb > 0 else 0

    cols = st.columns(4)
    kpis = [
        ("Total Revenue",     fmt_inr(rev),        "Current month billing",      "amber"),
        ("Total Customers",   f"{len(df):,}",       "In filtered view",           "blue"),
        ("Customer Shopped",  f"{conv:.1f}%",       f"{len(sh):,} shopped",       "green"),
        ("Avg AMS Value",     fmt_inr(ab),          "Per transacting customer",   "amber"),
        ("Cashback Earned",   fmt_inr(cb),          "Total this month",           "red"),
        ("Cashback Redeemed", fmt_inr(red),         f"{rr:.1f}% utilization",     "purple"),
        ("Active Stores",     str(stores),          "Unique store codes",         "blue"),
        ("Not Shopped",       f"{len(df)-len(sh):,}","",                          "red"),
    ]
    for i, (l, v, s, c) in enumerate(kpis):
        with cols[i % 4]:
            st.markdown(kpi_card(l, v, s, c), unsafe_allow_html=True)
            st.write("")

    # Insights
    st.markdown("<div class='section-label' style='margin-top:16px;'>Insights</div>", unsafe_allow_html=True)

    def top_by(col_group, col_val):
        if col_group not in df.columns or col_val not in df.columns: return None, None
        g = df.groupby(col_group)[col_val].sum().sort_values(ascending=False)
        return (g.index[0], g.iloc[0]) if len(g) else (None, None)

    t_reg, t_reg_v  = top_by('region_name', 'current_bill_value')
    t_city, t_city_v = top_by('city_name', 'current_bill_value')
    t_store, t_store_v = top_by('store_name', 'current_bill_value')

    ic1, ic2, ic3, ic4, ic5 = st.columns(5)
    insights = [
        ("📍","rgba(245,166,35,.15)","Top Revenue Region", f"<strong>{t_reg or '–'}</strong> leads with {fmt_inr(t_reg_v)} in billing."),
        ("🏙️","rgba(79,195,247,.15)","Best City",          f"<strong>{t_city or '–'}</strong> — {fmt_inr(t_city_v)} revenue."),
        ("💰","rgba(171,71,188,.15)","Cashback Utilization",f"Redemption <strong>{rr:.1f}%</strong>. {'Push activation campaigns.' if rr < 30 else 'Healthy utilization.'}"),
        ("🏪","rgba(232,93,55,.15)", "Top Store",           f"<strong>{str(t_store or '–')[:20]}</strong> — {fmt_inr(t_store_v)}."),
        ("📊","rgba(38,198,218,.15)","Coverage",            f"<strong>{df['region_name'].nunique() if 'region_name' in df.columns else 0} regions</strong>, {df['city_name'].nunique() if 'city_name' in df.columns else 0} cities, {stores} stores."),
    ]
    for ic, (icon, bg, title, body) in zip([ic1,ic2,ic3,ic4,ic5], insights):
        with ic:
            st.markdown(insight_card(icon, bg, title, body), unsafe_allow_html=True)

    # Charts row 1
    st.markdown("<div class='section-label' style='margin-top:16px;'>Charts</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

    with c1:
        if 'shopper_behaviour' in df.columns:
            beh = df['shopper_behaviour'].value_counts()
            fig = donut_chart(beh.index.tolist(), beh.values.tolist(), "Shopper Behaviour",
                              ['#66bb6a','#e85d37'])
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        if 'customer_type' in df.columns:
            cu = df['customer_type'].value_counts()
            fig = donut_chart(cu.index.tolist(), cu.values.tolist(), "Customer Type",
                              ['#f5a623','#4fc3f7'])
            st.plotly_chart(fig, use_container_width=True)

    with c3:
        if 'format_type' in df.columns:
            fm = df['format_type'].value_counts()
            fig = go.Figure(go.Pie(
                labels=fm.index.tolist(), values=fm.values.tolist(),
                marker=dict(colors=PALETTE[:len(fm)], line=dict(width=0)),
                textfont=dict(color='#7a8398', size=11),
            ))
            fig.update_layout(**PLOTLY_LAYOUT, title=dict(text="Store Format Mix", font=dict(color='#e8eaf0', size=13, family='Syne')))
            st.plotly_chart(fig, use_container_width=True)

    # Enrollment trend
    if 'enroll_month' in df.columns:
        et = df['enroll_month'].value_counts().reset_index()
        et.columns = ['month','count']
        et['sort_key'] = et['month'].map(month_to_num)
        et = et.sort_values('sort_key')
        fig = go.Figure(go.Scatter(
            x=et['month'], y=et['count'],
            mode='lines+markers',
            line=dict(color='#f5a623', width=2),
            fill='tozeroy', fillcolor='rgba(245,166,35,.08)',
            marker=dict(color='#f5a623', size=5),
        ))
        fig.update_layout(**PLOTLY_LAYOUT, title=dict(text="Enrollment Trend by Month", font=dict(color='#e8eaf0', size=13, family='Syne')))
        st.plotly_chart(fig, use_container_width=True)

    # Bill slab
    if 'bill_slab' in df.columns:
        bs = df['bill_slab'].value_counts().reset_index()
        bs.columns = ['slab','count']
        fig = bar_chart(bs, 'slab', 'count', "Bill Value Slab Distribution", color=PALETTE[0])
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════
#  TAB: RETURN RATE
# ══════════════════════════════════════════════════════════════
elif active == "🔄 Return Rate":
    rm_num = month_to_num(rm)
    window_start = rm_num - 9 if rm_num > 0 else 0
    window_end   = rm_num - 1 if rm_num > 0 else float('inf')

    if rm_num > 0 and 'enroll_month' in df.columns:
        elig = df[df['enroll_month'].map(month_to_num).between(window_start, window_end)]
        note = f"Return Rate window: customers enrolled {sub_months(rm,9)} to {sub_months(rm,1)} (9-month window before {rm})"
    else:
        elig = df[df['customer_type'] == 'Existing Customer'] if 'customer_type' in df.columns else df
        note = "Using Existing Customers (no reporting month set)"

    st.info(note)

    ret  = elig[elig['shopper_behaviour'] == 'Shopped'] if 'shopper_behaviour' in elig.columns else elig
    rr_ov = len(ret) / len(elig) * 100 if len(elig) else 0

    # RR by store
    def rr_by_group(data, key):
        if key not in data.columns or 'shopper_behaviour' not in data.columns:
            return pd.DataFrame(columns=['group','total','returned','rate'])
        g = data.groupby(key).agg(
            total=(key, 'count'),
            returned=('shopper_behaviour', lambda x: (x == 'Shopped').sum())
        ).reset_index()
        g.columns = ['group','total','returned']
        g['rate'] = g.apply(lambda r: r['returned']/r['total']*100 if r['total'] > 0 else 0, axis=1)
        return g.sort_values('rate', ascending=False)

    rr_stores = rr_by_group(elig, 'store_name')
    rr_stores_filt = rr_stores[rr_stores['total'] >= 3]
    avg_rrs = rr_stores_filt['rate'].mean() if len(rr_stores_filt) else 0

    st.markdown("<div class='section-label'>Key Performance Indicators</div>", unsafe_allow_html=True)
    cols = st.columns(3)
    kpis = [
        ("Eligible Customers", f"{len(elig):,}", "Enrolled in 9-month window", "amber"),
        ("Returned (Shopped)",  f"{len(ret):,}",  "Active this month",          "green"),
        ("Overall Return Rate", f"{rr_ov:.1f}%",  "Eligible who came back",     "green" if rr_ov >= 40 else "red"),
        ("Not Returned",        f"{len(elig)-len(ret):,}", "At-risk / lapsed",  "red"),
        ("Avg Store Return Rate",f"{avg_rrs:.1f}%","Mean across stores",         "purple"),
        ("Stores Tracked",      f"{len(rr_stores_filt)}", "Min 3 eligible customers", "blue"),
    ]
    for i, (l, v, s, c) in enumerate(kpis):
        with cols[i % 3]:
            st.markdown(kpi_card(l, v, s, c), unsafe_allow_html=True)
            st.write("")

    # Charts
    st.markdown("<div class='section-label' style='margin-top:16px;'>Return Rate by Dimension</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        rr_reg = rr_by_group(elig, 'region_name')
        if not rr_reg.empty:
            clrs = ['rgba(76,175,80,.8)' if r >= 50 else 'rgba(239,83,80,.8)' for r in rr_reg['rate']]
            fig = go.Figure(go.Bar(x=rr_reg['group'], y=rr_reg['rate'],
                                   marker_color=clrs, marker=dict(line=dict(width=0))))
            fig.update_layout(**PLOTLY_LAYOUT,
                              title=dict(text="Return Rate by Region", font=dict(color='#e8eaf0',size=13,family='Syne')),
                              yaxis=dict(**PLOTLY_LAYOUT['yaxis'], range=[0,100], ticksuffix='%'))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        rr_cl = rr_by_group(elig, 'cluster_name')
        if not rr_cl.empty:
            clrs = ['rgba(76,175,80,.8)' if r >= 50 else 'rgba(245,166,35,.8)' for r in rr_cl['rate']]
            fig = go.Figure(go.Bar(x=rr_cl['group'], y=rr_cl['rate'],
                                   marker_color=clrs, marker=dict(line=dict(width=0))))
            fig.update_layout(**PLOTLY_LAYOUT,
                              title=dict(text="Return Rate by Cluster", font=dict(color='#e8eaf0',size=13,family='Syne')),
                              yaxis=dict(**PLOTLY_LAYOUT['yaxis'], range=[0,100], ticksuffix='%'))
            st.plotly_chart(fig, use_container_width=True)

    # AMS Slab Transition
    if 'past_six_months_ams_slab' in df.columns and 'current_ams_slab' in df.columns:
        SLABS = ['0 to 500','501 to 1000','1001 to 1500','1501 to 2000','2001 to 2500',
                 '2501 to 3000','3001 to 3300','3301 to 4000','4001 to 5000',
                 '5001 to 7500','7501 to 10000','10001 to 12500','12501 to 15000','15000 & Above']
        pc = df['past_six_months_ams_slab'].value_counts()
        cc = df['current_ams_slab'].value_counts()
        labs = [s for s in SLABS if s in pc.index or s in cc.index]
        fig = go.Figure([
            go.Bar(name='Past 6M Avg Slab', x=labs, y=[pc.get(s,0) for s in labs],
                   marker_color='rgba(79,195,247,0.75)', marker=dict(line=dict(width=0))),
            go.Bar(name='Current Month Slab', x=labs, y=[cc.get(s,0) for s in labs],
                   marker_color='rgba(245,166,35,0.75)', marker=dict(line=dict(width=0))),
        ])
        fig.update_layout(**PLOTLY_LAYOUT, barmode='group',
                          title=dict(text="AMS Slab Transition", font=dict(color='#e8eaf0',size=13,family='Syne')))
        st.plotly_chart(fig, use_container_width=True)

    # Leaderboards
    st.markdown("<div class='section-label' style='margin-top:8px;'>Store Return Rate Leaderboards</div>", unsafe_allow_html=True)
    lb1, lb2 = st.columns(2)

    with lb1:
        st.markdown("**🏆 Top 10 Stores — Return Rate**")
        top10 = rr_stores_filt.nlargest(10, 'rate').to_dict('records')
        st.markdown(leaderboard_html(top10,
            name_fn=lambda r: r['group'][:24],
            value_fn=lambda r: f"{r['rate']:.1f}%",
            meta_fn=lambda r: f"{r['returned']}/{r['total']} customers",
        ), unsafe_allow_html=True)

    with lb2:
        st.markdown("**⚠️ Bottom 10 Stores — Return Rate**")
        bot10 = rr_stores_filt.nsmallest(10, 'rate').to_dict('records')
        st.markdown(leaderboard_html(bot10,
            name_fn=lambda r: r['group'][:24],
            value_fn=lambda r: f"{r['rate']:.1f}%",
            meta_fn=lambda r: f"{r['returned']}/{r['total']} customers",
            bad=True
        ), unsafe_allow_html=True)

    # Enrollment leaderboards
    st.markdown("<div class='section-label' style='margin-top:16px;'>Enrollment by Store</div>", unsafe_allow_html=True)
    lb3, lb4 = st.columns(2)
    enr = df.groupby('store_name').size().reset_index(name='cnt') if 'store_name' in df.columns else pd.DataFrame()

    with lb3:
        st.markdown("**🏆 Top 10 — Most Enrollments**")
        top10e = enr.nlargest(10,'cnt').to_dict('records') if not enr.empty else []
        st.markdown(leaderboard_html(top10e,
            name_fn=lambda r: r['store_name'][:24],
            value_fn=lambda r: f"{r['cnt']:,}",
            meta_fn=lambda r: "customers",
        ), unsafe_allow_html=True)

    with lb4:
        st.markdown("**⚠️ Bottom 10 — Fewest Enrollments**")
        bot10e = enr.nsmallest(10,'cnt').to_dict('records') if not enr.empty else []
        st.markdown(leaderboard_html(bot10e,
            name_fn=lambda r: r['store_name'][:24],
            value_fn=lambda r: f"{r['cnt']:,}",
            meta_fn=lambda r: "customers",
            bad=True
        ), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  TAB: CUSTOMERS
# ══════════════════════════════════════════════════════════════
elif active == "👥 Customers":
    sh = df[df['shopper_behaviour'] == 'Shopped'] if 'shopper_behaviour' in df.columns else df
    nw = df[df['customer_type'] == 'New Customer'] if 'customer_type' in df.columns else pd.DataFrame()
    ex = df[df['customer_type'] == 'Existing Customer'] if 'customer_type' in df.columns else pd.DataFrame()

    t_curr = sh['current_bill_value'].sum() if 'current_bill_value' in sh.columns else 0
    t_past = sh['past_six_months_average_ams'].sum() if 'past_six_months_average_ams' in sh.columns else 0
    t_inc  = t_curr - t_past
    t_curr_nob = sh['current_nob'].sum() if 'current_nob' in sh.columns else 0
    t_past_nob = sh['past_six_months_average_nob'].sum() if 'past_six_months_average_nob' in sh.columns else 0
    t_inc_nob  = t_curr_nob - t_past_nob
    a_nob = t_curr_nob / len(sh) if len(sh) else 0
    a_asp = sh['current_asp'].mean() if 'current_asp' in sh.columns else 0

    st.markdown("<div class='section-label'>Key Performance Indicators</div>", unsafe_allow_html=True)
    cols = st.columns(4)
    kpis = [
        ("Shopped Customers",  f"{len(sh):,}",     "Transacted this month",         "green"),
        ("Incremental Sales",  fmt_inr(t_inc),     "Current − 6M avg baseline",     "green" if t_inc >= 0 else "red"),
        ("Total Incr. NOB",    f"{t_inc_nob:.0f}", "Current NOB − Past Avg NOB",     "green" if t_inc_nob >= 0 else "red"),
        ("Avg NOB / Shopper",  f"{a_nob:.2f}",     "Bills per customer",             "amber"),
        ("Avg ASP",            fmt_inr(a_asp),     "Avg selling price",              "blue"),
        ("New Customers",      f"{len(nw):,}",     "First-time buyers",              "blue"),
        ("Existing Customers", f"{len(ex):,}",     "Repeat members",                 "purple"),
        ("Shopped Revenue",    fmt_inr(t_curr),    "Revenue from shoppers",          "amber"),
    ]
    for i, (l, v, s, c) in enumerate(kpis):
        with cols[i % 4]:
            st.markdown(kpi_card(l, v, s, c), unsafe_allow_html=True)
            st.write("")

    st.markdown("<div class='section-label' style='margin-top:16px;'>Incremental Sales Analysis</div>", unsafe_allow_html=True)

    def inc_bar(group_col, title):
        if group_col not in df.columns or 'incremental_sales' not in df.columns:
            return go.Figure()
        g = df.groupby(group_col)['incremental_sales'].sum().sort_values(ascending=False).reset_index()
        g.columns = ['group','inc']
        clrs = ['rgba(76,175,80,.8)' if v >= 0 else 'rgba(239,83,80,.8)' for v in g['inc']]
        fig = go.Figure(go.Bar(x=g['group'], y=g['inc'], marker_color=clrs, marker=dict(line=dict(width=0))))
        fig.update_layout(**PLOTLY_LAYOUT, title=dict(text=title, font=dict(color='#e8eaf0',size=13,family='Syne')),
                          yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickprefix='₹'))
        return fig

    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(inc_bar('region_name', "Incremental Sales by Region"), use_container_width=True)
    with c2: st.plotly_chart(inc_bar('cluster_name', "Incremental Sales by Cluster"), use_container_width=True)

    # Top 15 stores
    if 'store_name' in df.columns and 'incremental_sales' in df.columns:
        g = df.groupby('store_name')['incremental_sales'].sum().sort_values(ascending=False).head(15).reset_index()
        g.columns = ['store','inc']
        clrs = ['rgba(76,175,80,.75)' if v >= 0 else 'rgba(239,83,80,.75)' for v in g['inc']]
        fig = go.Figure(go.Bar(y=g['store'], x=g['inc'], orientation='h',
                               marker_color=clrs, marker=dict(line=dict(width=0))))
        fig.update_layout(**PLOTLY_LAYOUT,
                          title=dict(text="Top 15 Stores — Incremental Sales", font=dict(color='#e8eaf0',size=13,family='Syne')),
                          yaxis=dict(**PLOTLY_LAYOUT['yaxis'], autorange='reversed'),
                          xaxis=dict(**PLOTLY_LAYOUT['xaxis'], tickprefix='₹'))
        st.plotly_chart(fig, use_container_width=True)

    # Avg spend new vs existing
    c3, c4 = st.columns(2)
    with c3:
        avg_new = nw[nw['current_bill_value'] > 0]['current_bill_value'].mean() if len(nw) and 'current_bill_value' in nw.columns else 0
        avg_ex  = ex[ex['current_bill_value'] > 0]['current_bill_value'].mean() if len(ex) and 'current_bill_value' in ex.columns else 0
        fig = go.Figure(go.Bar(
            x=['New Customer','Existing Customer'], y=[avg_new, avg_ex],
            marker_color=['rgba(79,195,247,.8)','rgba(245,166,35,.8)'],
            marker=dict(line=dict(width=0))
        ))
        fig.update_layout(**PLOTLY_LAYOUT,
                          title=dict(text="Avg Bill Value: New vs Existing", font=dict(color='#e8eaf0',size=13,family='Syne')),
                          yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickprefix='₹'))
        st.plotly_chart(fig, use_container_width=True)

    with c4:
        if 'current_ams_slab' in df.columns:
            g = df['current_ams_slab'].value_counts().reset_index()
            g.columns = ['slab','count']
            fig = go.Figure(go.Bar(x=g['slab'], y=g['count'],
                                   marker_color=PALETTE[0]+'bb', marker=dict(line=dict(width=0))))
            fig.update_layout(**PLOTLY_LAYOUT,
                              title=dict(text="AMS Slab Distribution", font=dict(color='#e8eaf0',size=13,family='Syne')))
            st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════
#  TAB: STORES
# ══════════════════════════════════════════════════════════════
elif active == "🏪 Stores":
    stores_rev = df.groupby('store_name')['current_bill_value'].sum().sort_values(ascending=False) if 'store_name' in df.columns and 'current_bill_value' in df.columns else pd.Series()
    total_stores = df['store_code'].nunique() if 'store_code' in df.columns else 0
    top_st = (stores_rev.index[0], stores_rev.iloc[0]) if len(stores_rev) else (None, 0)
    avg_rev = stores_rev.mean() if len(stores_rev) else 0
    formats = df['format_type'].nunique() if 'format_type' in df.columns else 0

    st.markdown("<div class='section-label'>Key Performance Indicators</div>", unsafe_allow_html=True)
    cols = st.columns(4)
    kpis = [
        ("Total Stores",      str(total_stores),              "Unique store codes",      "blue"),
        ("Top Store",         str(top_st[0] or "–")[:16],    fmt_inr(top_st[1]),        "amber"),
        ("Avg Revenue/Store", fmt_inr(avg_rev),              "Mean bill value",          "green"),
        ("Total Formats",     str(formats),                  "Distinct store types",     "purple"),
    ]
    for i, (l, v, s, c) in enumerate(kpis):
        with cols[i]:
            st.markdown(kpi_card(l, v, s, c), unsafe_allow_html=True)
            st.write("")

    # Top 15 stores horizontal bar
    if len(stores_rev):
        top15 = stores_rev.head(15).reset_index()
        top15.columns = ['store','revenue']
        fig = go.Figure(go.Bar(
            y=top15['store'], x=top15['revenue'],
            marker_color=[PALETTE[i % len(PALETTE)] + 'cc' for i in range(len(top15))],
            orientation='h', marker=dict(line=dict(width=0))
        ))
        fig.update_layout(**PLOTLY_LAYOUT,
                          title=dict(text="Top 15 Stores by Revenue", font=dict(color='#e8eaf0',size=13,family='Syne')),
                          yaxis=dict(**PLOTLY_LAYOUT['yaxis'], autorange='reversed'),
                          xaxis=dict(**PLOTLY_LAYOUT['xaxis'], tickprefix='₹'), height=400)
        st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        if 'format_type' in df.columns:
            sf = df['format_type'].value_counts()
            fig = donut_chart(sf.index.tolist(), sf.values.tolist(), "Store Format Distribution")
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        if 'format_type' in df.columns and 'current_bill_value' in df.columns:
            bf = df.groupby('format_type')['current_bill_value'].mean().reset_index()
            bf.columns = ['format','avg_basket']
            fig = go.Figure(go.Bar(
                x=bf['format'], y=bf['avg_basket'],
                marker_color=[PALETTE[i % len(PALETTE)] + 'cc' for i in range(len(bf))],
                marker=dict(line=dict(width=0))
            ))
            fig.update_layout(**PLOTLY_LAYOUT,
                              title=dict(text="Avg Basket Value by Format", font=dict(color='#e8eaf0',size=13,family='Syne')),
                              yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickprefix='₹'))
            st.plotly_chart(fig, use_container_width=True)

    # Leaderboard
    st.markdown("<div class='section-label' style='margin-top:8px;'>Store Leaderboard (Top 20)</div>", unsafe_allow_html=True)
    if len(stores_rev):
        max_rev = stores_rev.iloc[0]
        items = list(zip(stores_rev.head(20).index, stores_rev.head(20).values))
        cust_cnt = df.groupby('store_name').size() if 'store_name' in df.columns else pd.Series()
        st.markdown(leaderboard_html(items,
            name_fn=lambda r: r[0],
            value_fn=lambda r: fmt_inr(r[1]),
            meta_fn=lambda r: f"{cust_cnt.get(r[0], 0):,} customers",
        ), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  TAB: CASHBACK & SALES
# ══════════════════════════════════════════════════════════════
elif active == "💳 Cashback & Sales":
    cb  = df['cashback_earned_current_month'].sum() if 'cashback_earned_current_month' in df.columns else 0
    red = df['redemed_amount_current_month'].sum() if 'redemed_amount_current_month' in df.columns else 0
    rr  = cb > 0 and red / cb * 100 or 0
    nr  = cb - red

    st.markdown("<div class='section-label'>Key Performance Indicators</div>", unsafe_allow_html=True)
    cols = st.columns(4)
    kpis = [
        ("Total Cashback Earned", fmt_inr(cb),        "This month",                "amber"),
        ("Total Redeemed",        fmt_inr(red),        f"{rr:.1f}% utilization",    "green"),
        ("Unredeemed Balance",    fmt_inr(nr),         "Yet to be used",            "red"),
        ("Redemption Rate",       f"{rr:.1f}%",       "Healthy" if rr >= 30 else "Needs activation", "green" if rr >= 30 else "red"),
    ]
    for i, (l, v, s, c) in enumerate(kpis):
        with cols[i]:
            st.markdown(kpi_card(l, v, s, c), unsafe_allow_html=True)
            st.write("")

    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Bar(
            x=['Earned','Redeemed','Unredeemed'], y=[cb, red, nr],
            marker_color=['rgba(245,166,35,.8)','rgba(76,175,80,.8)','rgba(239,83,80,.8)'],
            marker=dict(line=dict(width=0))
        ))
        fig.update_layout(**PLOTLY_LAYOUT,
                          title=dict(text="Cashback Overview", font=dict(color='#e8eaf0',size=13,family='Syne')),
                          yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickprefix='₹'))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        if 'format_type' in df.columns:
            cb_f  = df.groupby('format_type')['cashback_earned_current_month'].sum()
            red_f = df.groupby('format_type')['redemed_amount_current_month'].sum()
            formats = list(set(cb_f.index) | set(red_f.index))
            rr_f = [(f, (red_f.get(f,0) / cb_f.get(f,1) * 100) if cb_f.get(f,0) > 0 else 0) for f in formats]
            rr_f.sort(key=lambda x: x[1])
            fig = go.Figure(go.Bar(
                x=[r[0] for r in rr_f], y=[r[1] for r in rr_f],
                marker_color=['rgba(76,175,80,.8)' if r[1] >= 30 else 'rgba(239,83,80,.8)' for r in rr_f],
                marker=dict(line=dict(width=0))
            ))
            fig.update_layout(**PLOTLY_LAYOUT,
                              title=dict(text="Redemption Rate by Format", font=dict(color='#e8eaf0',size=13,family='Syne')),
                              yaxis=dict(**PLOTLY_LAYOUT['yaxis'], range=[0,100], ticksuffix='%'))
            st.plotly_chart(fig, use_container_width=True)

    # Top 10 cities cashback
    if 'city_name' in df.columns and 'cashback_earned_current_month' in df.columns:
        g = df.groupby('city_name')['cashback_earned_current_month'].sum().sort_values(ascending=False).head(10).reset_index()
        g.columns = ['city','cashback']
        fig = go.Figure(go.Bar(
            x=g['city'], y=g['cashback'],
            marker_color=[PALETTE[i % len(PALETTE)] + 'cc' for i in range(len(g))],
            marker=dict(line=dict(width=0))
        ))
        fig.update_layout(**PLOTLY_LAYOUT,
                          title=dict(text="Top 10 Cities — Cashback Earned", font=dict(color='#e8eaf0',size=13,family='Syne')),
                          yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickprefix='₹'))
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════
#  TAB: GEOGRAPHY
# ══════════════════════════════════════════════════════════════
elif active == "🗺️ Geography":
    regions  = df['region_name'].nunique()  if 'region_name'  in df.columns else 0
    cities   = df['city_name'].nunique()    if 'city_name'    in df.columns else 0
    clusters = df['cluster_name'].nunique() if 'cluster_name' in df.columns else 0
    stores   = df['store_code'].nunique()   if 'store_code'   in df.columns else 0

    st.markdown("<div class='section-label'>Geographic Coverage</div>", unsafe_allow_html=True)
    cols = st.columns(4)
    for col, (l, v, c) in zip(cols, [
        ("Regions", str(regions), "blue"), ("Cities", str(cities), "amber"),
        ("Clusters", str(clusters), "green"), ("Stores", str(stores), "purple")
    ]):
        with col:
            st.markdown(kpi_card(l, v, "Operational units", c), unsafe_allow_html=True)
            st.write("")

    c1, c2 = st.columns(2)
    with c1:
        if 'region_name' in df.columns and 'current_bill_value' in df.columns:
            g = df.groupby('region_name')['current_bill_value'].sum().sort_values(ascending=False).reset_index()
            g.columns = ['region','revenue']
            fig = go.Figure(go.Bar(x=g['region'], y=g['revenue'],
                                   marker_color=[PALETTE[i%len(PALETTE)]+'cc' for i in range(len(g))],
                                   marker=dict(line=dict(width=0))))
            fig.update_layout(**PLOTLY_LAYOUT,
                              title=dict(text="Revenue by Region", font=dict(color='#e8eaf0',size=13,family='Syne')),
                              yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickprefix='₹'))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        if 'region_name' in df.columns:
            g = df.groupby('region_name').size().sort_values(ascending=False).reset_index()
            g.columns = ['region','customers']
            fig = go.Figure(go.Bar(x=g['region'], y=g['customers'],
                                   marker_color=[PALETTE[i%len(PALETTE)]+'aa' for i in range(len(g))],
                                   marker=dict(line=dict(width=0))))
            fig.update_layout(**PLOTLY_LAYOUT,
                              title=dict(text="Customers by Region", font=dict(color='#e8eaf0',size=13,family='Syne')))
            st.plotly_chart(fig, use_container_width=True)

    # Top 15 cities by revenue (horizontal)
    if 'city_name' in df.columns and 'current_bill_value' in df.columns:
        g = df.groupby('city_name')['current_bill_value'].sum().sort_values(ascending=False).head(15).reset_index()
        g.columns = ['city','revenue']
        fig = go.Figure(go.Bar(
            y=g['city'], x=g['revenue'], orientation='h',
            marker_color=[PALETTE[i%len(PALETTE)]+'cc' for i in range(len(g))],
            marker=dict(line=dict(width=0))
        ))
        fig.update_layout(**PLOTLY_LAYOUT,
                          title=dict(text="Top 15 Cities by Revenue", font=dict(color='#e8eaf0',size=13,family='Syne')),
                          yaxis=dict(**PLOTLY_LAYOUT['yaxis'], autorange='reversed'),
                          xaxis=dict(**PLOTLY_LAYOUT['xaxis'], tickprefix='₹'), height=400)
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════
#  TAB: LOST SALES
# ══════════════════════════════════════════════════════════════
elif active == "📉 Lost Sales":
    ns = df[
        (df['shopper_behaviour'] == 'Not Shopped') &
        (df['past_six_months_average_ams'] > 0)
    ] if 'shopper_behaviour' in df.columns and 'past_six_months_average_ams' in df.columns else pd.DataFrame()

    t_lost = ns['past_six_months_average_ams'].sum() if len(ns) else 0
    t_lost_nob = ns['past_six_months_average_nob'].sum() if 'past_six_months_average_nob' in ns.columns and len(ns) else 0
    a_lost = t_lost / len(ns) if len(ns) else 0
    a_lost_nob = t_lost_nob / len(ns) if len(ns) else 0

    st.markdown("<div class='section-label'>Lost Sales KPIs</div>", unsafe_allow_html=True)
    cols = st.columns(3)
    kpis = [
        ("Lost Customers",      f"{len(ns):,}",        "Had past history, not shopped this month","red"),
        ("Total Lost Sales",    fmt_inr(t_lost),       "Σ Past 6M Avg AMS of lost customers",    "red"),
        ("Avg Lost / Customer", fmt_inr(a_lost),       "Per lost customer",                       "amber"),
        ("Total Lost NOB",      f"{t_lost_nob:.0f}",   "Σ Past 6M Avg NOB of lost customers",    "red"),
        ("Avg Lost NOB / Cust", f"{a_lost_nob:.2f}",   "Expected visits missed",                  "amber"),
        ("Win-back Potential",  fmt_inr(t_lost),       "If all returned this month",              "green"),
    ]
    for i, (l, v, s, c) in enumerate(kpis):
        with cols[i % 3]:
            st.markdown(kpi_card(l, v, s, c), unsafe_allow_html=True)
            st.write("")

    if len(ns) == 0:
        st.info("No lost sales data found (customers with 'Not Shopped' and past AMS > 0).")
    else:
        c1, c2 = st.columns(2)
        with c1:
            if 'region_name' in ns.columns:
                g = ns.groupby('region_name')['past_six_months_average_ams'].sum().sort_values(ascending=False).reset_index()
                g.columns = ['region','lost']
                fig = go.Figure(go.Bar(x=g['region'], y=g['lost'],
                                       marker_color='rgba(239,83,80,.75)', marker=dict(line=dict(width=0))))
                fig.update_layout(**PLOTLY_LAYOUT,
                                  title=dict(text="Lost Sales by Region", font=dict(color='#e8eaf0',size=13,family='Syne')),
                                  yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickprefix='₹'))
                st.plotly_chart(fig, use_container_width=True)

        with c2:
            if 'cluster_name' in ns.columns:
                g = ns.groupby('cluster_name')['past_six_months_average_ams'].sum().sort_values(ascending=False).head(12).reset_index()
                g.columns = ['cluster','lost']
                fig = go.Figure(go.Bar(x=g['cluster'], y=g['lost'],
                                       marker_color='rgba(245,166,35,.75)', marker=dict(line=dict(width=0))))
                fig.update_layout(**PLOTLY_LAYOUT,
                                  title=dict(text="Lost Sales by Cluster (Top 12)", font=dict(color='#e8eaf0',size=13,family='Syne')),
                                  yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickprefix='₹'))
                st.plotly_chart(fig, use_container_width=True)

        # Lost sales by store (horizontal)
        if 'store_name' in ns.columns:
            g = ns.groupby('store_name')['past_six_months_average_ams'].sum().sort_values(ascending=False).head(15).reset_index()
            g.columns = ['store','lost']
            fig = go.Figure(go.Bar(
                y=g['store'], x=g['lost'], orientation='h',
                marker_color='rgba(239,83,80,.7)', marker=dict(line=dict(width=0))
            ))
            fig.update_layout(**PLOTLY_LAYOUT,
                              title=dict(text="Top 15 Stores — Lost Sales", font=dict(color='#e8eaf0',size=13,family='Syne')),
                              yaxis=dict(**PLOTLY_LAYOUT['yaxis'], autorange='reversed'),
                              xaxis=dict(**PLOTLY_LAYOUT['xaxis'], tickprefix='₹'), height=400)
            st.plotly_chart(fig, use_container_width=True)

        # Lost NOB charts
        st.markdown("<div class='section-label' style='margin-top:8px;'>Lost NOB Analysis</div>", unsafe_allow_html=True)
        if 'past_six_months_average_nob' in ns.columns:
            c3, c4 = st.columns(2)
            with c3:
                if 'region_name' in ns.columns:
                    g = ns.groupby('region_name')['past_six_months_average_nob'].sum().sort_values(ascending=False).reset_index()
                    g.columns = ['region','nob']
                    fig = go.Figure(go.Bar(x=g['region'], y=g['nob'],
                                           marker_color='rgba(171,71,188,.75)', marker=dict(line=dict(width=0))))
                    fig.update_layout(**PLOTLY_LAYOUT, title=dict(text="Lost NOB by Region", font=dict(color='#e8eaf0',size=13,family='Syne')))
                    st.plotly_chart(fig, use_container_width=True)

            with c4:
                if 'cluster_name' in ns.columns:
                    g = ns.groupby('cluster_name')['past_six_months_average_nob'].sum().sort_values(ascending=False).head(12).reset_index()
                    g.columns = ['cluster','nob']
                    fig = go.Figure(go.Bar(x=g['cluster'], y=g['nob'],
                                           marker_color='rgba(79,195,247,.75)', marker=dict(line=dict(width=0))))
                    fig.update_layout(**PLOTLY_LAYOUT, title=dict(text="Lost NOB by Cluster", font=dict(color='#e8eaf0',size=13,family='Syne')))
                    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════
#  TAB: DATA EXPLORER
# ══════════════════════════════════════════════════════════════
elif active == "🔍 Data Explorer":
    COLS = ['store_name','customer_name','city_name','cluster_name','region_name',
            'format_type','shopper_behaviour','customer_type','enroll_month',
            'current_bill_value','cashback_earned_current_month',
            'redemed_amount_current_month','incremental_sales',
            'current_nob','past_six_months_average_nob']
    show_cols = [c for c in COLS if c in df.columns]

    st.markdown(f"<div class='section-label'>Data Explorer — {len(df):,} rows</div>", unsafe_allow_html=True)

    PAGE_SIZE = 50
    total_pages = max(1, (len(df) + PAGE_SIZE - 1) // PAGE_SIZE)

    if 'explorer_page' not in st.session_state:
        st.session_state.explorer_page = 1

    col_prev, col_info, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("◀ Prev") and st.session_state.explorer_page > 1:
            st.session_state.explorer_page -= 1
    with col_info:
        st.markdown(f"<div style='text-align:center;color:#7a8398;font-size:12px;padding-top:8px;'>Page {st.session_state.explorer_page} of {total_pages} ({len(df):,} rows)</div>", unsafe_allow_html=True)
    with col_next:
        if st.button("Next ▶") and st.session_state.explorer_page < total_pages:
            st.session_state.explorer_page += 1

    page_df = df[show_cols].iloc[
        (st.session_state.explorer_page - 1) * PAGE_SIZE :
        st.session_state.explorer_page * PAGE_SIZE
    ]
    st.dataframe(page_df, use_container_width=True, height=600)
    
    st.download_button(
        "⬇ Download Filtered CSV", 
        df[show_cols].to_csv(index=False).encode(),
        file_name="spencers_filtered.csv", mime="text/csv"
    )

# ══════════════════════════════════════════════════════════════
#  TAB: AI ANALYST
# ══════════════════════════════════════════════════════════════
elif active == "🤖 AI Analyst":
    st.markdown("<div class='section-label'>AI Analyst — Powered by Claude</div>", unsafe_allow_html=True)

    api_key = st.text_input("Anthropic API Key", type="password",
                            value=st.session_state.api_key,
                            placeholder="sk-ant-api03-…")
    if api_key:
        st.session_state.api_key = api_key

    # Build data context summary
    def build_data_context():
        sh = df[df['shopper_behaviour'] == 'Shopped'] if 'shopper_behaviour' in df.columns else df
        ns = df[
            (df['shopper_behaviour'] == 'Not Shopped') &
            (df['past_six_months_average_ams'] > 0)
        ] if 'shopper_behaviour' in df.columns and 'past_six_months_average_ams' in df.columns else pd.DataFrame()
        cb  = df['cashback_earned_current_month'].sum() if 'cashback_earned_current_month' in df.columns else 0
        red = df['redemed_amount_current_month'].sum()  if 'redemed_amount_current_month' in df.columns else 0
        rev = df['current_bill_value'].sum() if 'current_bill_value' in df.columns else 0

        top_stores = ""
        if 'store_name' in df.columns and 'current_bill_value' in df.columns:
            top = df.groupby('store_name')['current_bill_value'].sum().sort_values(ascending=False).head(5)
            top_stores = "\n".join([f"  {i+1}. {name}: {fmt_inr(val)}" for i, (name,val) in enumerate(top.items())])

        return f"""
Reporting Month: {rm}
Total Records: {len(df):,}
Total Revenue: {fmt_inr(rev)}
Shopped Customers: {len(sh):,} ({len(sh)/len(df)*100:.1f}% of total)
Not Shopped: {len(df)-len(sh):,}
Cashback Earned: {fmt_inr(cb)}
Cashback Redeemed: {fmt_inr(red)} ({red/cb*100:.1f}% rate)
Lost Customers (Not Shopped with past AMS): {len(ns):,}
Total Lost Sales (past avg AMS): {fmt_inr(ns['past_six_months_average_ams'].sum() if len(ns) else 0)}
Active Regions: {df['region_name'].nunique() if 'region_name' in df.columns else 0}
Active Cities: {df['city_name'].nunique() if 'city_name' in df.columns else 0}
Active Stores: {df['store_code'].nunique() if 'store_code' in df.columns else 0}
Top 5 Stores by Revenue:
{top_stores}
"""

    # Display chat history
    for msg in st.session_state.chat_history:
        cls = "chat-user" if msg['role'] == 'user' else "chat-assistant"
        st.markdown(f"<div class='chat-msg {cls}'>{msg['content']}</div>", unsafe_allow_html=True)

    # Suggested questions
    if not st.session_state.chat_history:
        st.markdown("<div style='color:#7a8398;font-size:12px;margin:12px 0 6px;'>Suggested questions:</div>", unsafe_allow_html=True)
        sugg = [
            "What is the overall return rate and which stores are underperforming?",
            "Which regions have the highest lost sales potential?",
            "How is cashback utilization trending and what actions should I take?",
            "Give me a top 3 priority action list based on this data.",
        ]
        for s in sugg:
            if st.button(s, key=f"sugg_{s}"):
                st.session_state.chat_history.append({'role':'user','content':s})
                st.rerun()

    # Input
    user_input = st.chat_input("Ask about your rewards data…")
    if user_input:
        st.session_state.chat_history.append({'role':'user','content':user_input})
        st.rerun()

    # Call API if last message is from user
    if st.session_state.chat_history and st.session_state.chat_history[-1]['role'] == 'user':
        if not st.session_state.api_key:
            st.warning("Please enter your Anthropic API key above to use the AI Analyst.")
        else:
            data_ctx = build_data_context()
            system_prompt = f"""You are an expert business analyst for Spencer's Retail, specializing in the 'My Rewards' loyalty program.

You have access to the following live data from the Spencer's My Rewards loyalty program dashboard:

{data_ctx}

Guidelines:
- Give specific, actionable, business-focused answers
- Reference actual numbers from the data provided
- Suggest concrete next steps when asked
- Use Indian retail context (₹, Lakh, Crore formats)
- Be concise but thorough
- When asked about trends or insights, highlight anomalies and opportunities
- For return rate, explain what the 9-month enrollment window means in business terms"""

            messages = [
                {"role": m['role'], "content": m['content']}
                for m in st.session_state.chat_history[-20:]
            ]

            with st.spinner("Claude is thinking…"):
                try:
                    client = anthropic.Anthropic(api_key=st.session_state.api_key)
                    response = client.messages.create(
                        model="claude-sonnet-4-5",
                        max_tokens=1024,
                        system=system_prompt,
                        messages=messages
                    )
                    reply = response.content[0].text
                    st.session_state.chat_history.append({'role':'assistant','content':reply})
                    st.rerun()
                except Exception as e:
                    st.error(f"API Error: {e}")

    if st.session_state.chat_history and st.button("🗑 Clear Chat"):
        st.session_state.chat_history = []
        st.rerun()

    st.markdown(f"""
    <div style='font-size:11px;color:#7a8398;margin-top:12px;padding:10px;
                background:rgba(79,195,247,.05);border:1px solid rgba(79,195,247,.15);
                border-radius:8px;'>
        📊 <strong style='color:#4fc3f7;'>{len(df):,} records loaded</strong> · 
        All dashboard features work without the API key · 
        AI Analyst requires an Anthropic API key
    </div>
    """, unsafe_allow_html=True)
