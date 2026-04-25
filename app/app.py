import os
import logging
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import boto3
from datetime import datetime, timedelta
import time
from config import *
from prompt_logging import render_prompt_logging_page
from i18n import t, init_locale, set_locale, get_locale, SUPPORTED_LOCALES

# Hide deploy button
os.environ['STREAMLIT_SERVER_ENABLE_STATIC_SERVING'] = 'false'

# Page configuration
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state="collapsed"
)

# Initialize theme and locale in session state
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'
init_locale()

# Theme colors
theme_colors = {
    'light': {
        'bg': '#ffffff',
        'secondary_bg': '#f8f9fa',
        'text': '#1f2937',
        'border': '#e5e7eb',
        'accent': '#1f77b4'
    },
    'dark': {
        'bg': '#0e1117',
        'secondary_bg': '#1e2530',
        'text': '#fafafa',
        'border': '#374151',
        'accent': '#4dabf7'
    }
}

current_theme = theme_colors[st.session_state.theme]

# Modern UI styling with theme support
modern_style = f"""
    <style>
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    [data-testid="stToolbar"] {{display: none;}}
    .stDeployButton {{display: none;}}
    [data-testid="stSidebar"] {{display: none;}}
    section[data-testid="stSidebar"] {{display: none;}}
    .stApp {{
        background-color: {current_theme['bg']};
        color: {current_theme['text']};
        font-size: 1.05rem;
    }}
    .main {{ padding: 1.5rem 2rem; }}
    [data-testid="stMetricValue"] {{
        font-size: 2.4rem; font-weight: 700; color: {current_theme['accent']};
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 1rem; font-weight: 500; color: {current_theme['text']}; opacity: 0.8;
    }}
    [data-testid="stMetricDelta"] {{
        font-size: 0.9rem;
    }}
    .block-container {{ padding-top: 1rem; padding-bottom: 2rem; max-width: 100%; }}
    .stButton button {{
        border-radius: 8px; font-weight: 500; padding: 0.4rem 0.8rem;
        transition: all 0.2s ease; border: 1px solid {current_theme['border']};
        background-color: {current_theme['secondary_bg']}; color: {current_theme['text']};
    }}
    .stButton button:hover {{
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-color: {current_theme['accent']};
    }}
    .dashboard-title {{
        font-weight: 700; font-size: 3rem; margin: 0; padding: 0;
        color: {current_theme['text']};
    }}
    .dashboard-subtitle {{
        font-size: 1.1rem; color: {current_theme['text']}; opacity: 0.5; margin-top: 4px;
    }}
    h2 {{ font-weight: 600; font-size: 1.6rem; margin-top: 1.5rem; margin-bottom: 0.8rem; color: {current_theme['text']}; }}
    h3 {{ font-weight: 600; font-size: 1.3rem; color: {current_theme['text']}; }}
    h4 {{ font-weight: 600; font-size: 1.15rem; color: {current_theme['text']}; }}
    p, li, span, label, .stMarkdown {{ color: {current_theme['text']}; }}
    strong {{ color: {current_theme['text']}; }}
    [data-testid="stMarkdownContainer"] {{ color: {current_theme['text']}; }}
    [data-testid="stMarkdownContainer"] p {{ color: {current_theme['text']}; }}
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stMarkdownContainer"] h4 {{ color: {current_theme['text']}; }}
    hr {{ margin: 1.5rem 0; border-color: {current_theme['border']}; opacity: 0.3; }}
    .streamlit-expanderHeader {{ background-color: {current_theme['secondary_bg']}; border-radius: 8px; font-weight: 500; }}
    [data-testid="stDataFrame"] {{ border-radius: 8px; overflow: hidden; }}
    div[data-testid="stPlotlyChart"] {{
        border-radius: 12px;
        overflow: hidden;
    }}
    </style>
"""
st.markdown(modern_style, unsafe_allow_html=True)

# --- Athena helpers ---

@st.cache_resource
def get_athena_client():
    return boto3.client('athena', region_name=AWS_REGION)

@st.cache_resource
def get_identity_store_client():
    return boto3.client('identitystore', region_name=AWS_REGION)

@st.cache_resource
def get_glue_client():
    return boto3.client('glue', region_name=AWS_REGION)

@st.cache_data(ttl=3600)
def resolve_table_name():
    """Auto-discover the table name from the Glue database.
    Falls back to GLUE_TABLE_NAME env var if set."""
    if GLUE_TABLE_NAME:
        return GLUE_TABLE_NAME
    try:
        client = get_glue_client()
        response = client.get_tables(DatabaseName=ATHENA_DATABASE, MaxResults=1)
        tables = response.get('TableList', [])
        if tables:
            return tables[0]['Name']
    except Exception:
        pass
    raise Exception(f"No tables found in Glue database '{ATHENA_DATABASE}'. "
                    "Run the Glue crawler first, or set GLUE_TABLE_NAME in .env.")

@st.cache_data(ttl=3600)
def get_username(userid):
    if not IDENTITY_STORE_ID:
        return userid
    # Strip IdentityStoreId prefix if present (e.g. "d-906xxx.uuid" → "uuid")
    lookup_id = userid
    if '.' in userid:
        lookup_id = userid.split('.', 1)[1]
    try:
        client = get_identity_store_client()
        response = client.describe_user(IdentityStoreId=IDENTITY_STORE_ID, UserId=lookup_id)
        return response.get('UserName') or response.get('DisplayName') or \
               response.get('Emails', [{}])[0].get('Value') or userid
    except Exception as e:
        logging.warning(f"Failed to resolve username for '{userid}' (lookup_id='{lookup_id}'): {e}")
        return userid

@st.cache_data(ttl=3600)
def get_usernames_batch(userids):
    """Batch-resolve userIds to friendly display names.

    When two different userIds resolve to the same username, disambiguate
    by appending the last 4 characters of the userId in parentheses.
    """
    from collections import Counter

    unique_ids = list(set(userids))

    # Step 1: resolve each userId to a raw username
    raw_map = {uid: get_username(uid) for uid in unique_ids}

    # Step 2: detect duplicate usernames
    name_counts = Counter(raw_map.values())

    # Step 3: append short ID suffix for duplicates
    display_map = {}
    for uid, name in raw_map.items():
        if name_counts[name] > 1 and name != uid:
            short_id = uid.split('.')[-1][-4:] if '.' in uid else uid[-4:]
            display_map[uid] = f"{name} ({short_id})"
        else:
            display_map[uid] = name

    return display_map

def execute_athena_query(query):
    client = get_athena_client()
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': ATHENA_DATABASE},
        ResultConfiguration={'OutputLocation': ATHENA_OUTPUT_BUCKET}
    )
    qid = response['QueryExecutionId']
    while True:
        result = client.get_query_execution(QueryExecutionId=qid)
        status = result['QueryExecution']['Status']['State']
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(1)  # nosemgrep
    if status == 'SUCCEEDED':
        return qid
    error_msg = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
    raise Exception(f"Query failed: {error_msg}")

@st.cache_data(ttl=300)
def fetch_data(query):
    client = get_athena_client()
    qid = execute_athena_query(query)
    result = client.get_query_results(QueryExecutionId=qid)
    columns = [col['Label'] for col in result['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    rows = []
    for row in result['ResultSet']['Rows'][1:]:
        rows.append([field.get('VarCharValue', '') for field in row['Data']])
    return pd.DataFrame(rows, columns=columns)

# --- Theme helpers ---

def get_plotly_template():
    return 'plotly_dark' if st.session_state.theme == 'dark' else 'plotly_white'

def get_chart_colors():
    if st.session_state.theme == 'dark':
        return {'paper_bgcolor': '#0e1117', 'plot_bgcolor': '#0e1117',
                'font_color': '#ffffff', 'title_color': '#ffffff'}
    return {'paper_bgcolor': '#ffffff', 'plot_bgcolor': '#ffffff',
            'font_color': '#1f2937', 'title_color': '#1f2937'}

# Modern color palette
CHART_COLORS = ['#4361ee', '#3a0ca3', '#7209b7', '#f72585', '#4cc9f0',
                '#4895ef', '#560bad', '#b5179e', '#f77f00', '#06d6a0']

def apply_chart_theme(fig):
    colors = get_chart_colors()
    fc, tc = colors['font_color'], colors['title_color']
    fig.update_layout(
        template=get_plotly_template(),
        paper_bgcolor=colors['paper_bgcolor'], plot_bgcolor=colors['plot_bgcolor'],
        font=dict(color=fc, size=12, family="Inter, system-ui, sans-serif"),
        title=dict(font=dict(color=tc, size=15, family="Inter, system-ui, sans-serif"), x=0.5, xanchor='center'),
        legend=dict(font=dict(color=fc, size=11), bgcolor='rgba(0,0,0,0)', borderwidth=0),
        margin=dict(l=40, r=40, t=50, b=40),
        hoverlabel=dict(bgcolor=colors['paper_bgcolor'], font_size=12, font_color=fc),
    )
    fig.update_xaxes(
        title_font=dict(color=fc, size=11), tickfont=dict(color=fc, size=10),
        gridcolor='rgba(128,128,128,0.1)', showline=True, linewidth=1, linecolor='rgba(128,128,128,0.2)'
    )
    fig.update_yaxes(
        title_font=dict(color=fc, size=11), tickfont=dict(color=fc, size=10),
        gridcolor='rgba(128,128,128,0.1)', showline=False
    )
    fig.update_annotations(font=dict(color=tc, size=13, family="Inter, system-ui, sans-serif"))
    return fig

def safe_float(val, default=0.0):
    try:
        return float(val) if val and str(val).strip() not in ('', 'None') else default
    except (ValueError, TypeError):
        return default

def safe_int(val, default=0):
    try:
        return int(float(val)) if val and str(val).strip() not in ('', 'None') else default
    except (ValueError, TypeError):
        return default


# --- Date / language filter helpers ---

def build_where_clause(table_name, start_date=None, end_date=None, language=None):
    """Build a WHERE clause for date range and programming language filters."""
    conditions = []
    if start_date:
        conditions.append(f"date >= '{start_date}'")
    if end_date:
        conditions.append(f"date <= '{end_date}'")
    if language and language != 'All':
        conditions.append(f"programming_language = '{language}'")
    return (" WHERE " + " AND ".join(conditions)) if conditions else ""


def compute_wau_mau(df_daily):
    """Given a daily DataFrame with 'date' and 'active_users' (or raw user-level data),
    compute weekly and monthly active user counts using rolling windows."""
    # df_daily is expected to have columns: date, userid (one row per user per day)
    df = df_daily.copy()
    df['date'] = pd.to_datetime(df['date'])

    # Weekly: ISO week
    df['week'] = df['date'].dt.isocalendar().year.astype(str) + '-W' + \
                 df['date'].dt.isocalendar().week.astype(str).str.zfill(2)
    wau = df.groupby('week')['userid'].nunique().reset_index()
    wau.columns = ['week', 'active_users']

    # Monthly
    df['month'] = df['date'].dt.to_period('M').astype(str)
    mau = df.groupby('month')['userid'].nunique().reset_index()
    mau.columns = ['month', 'active_users']

    # Daily
    dau = df.groupby('date')['userid'].nunique().reset_index()
    dau.columns = ['date', 'active_users']

    return dau, wau, mau


# --- Main app ---

def main():
    # Header
    header_col1, header_col2, header_col3, header_col4, header_col5 = st.columns([5, 2, 1, 1, 0.5])
    with header_col1:
        st.markdown(f'<p class="dashboard-title">{t("dashboard_title")}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="dashboard-subtitle">{t("dashboard_subtitle")}</p>', unsafe_allow_html=True)
    with header_col2:
        page = st.selectbox(t("navigate"), [t("nav_usage"), t("nav_prompt_log")],
                            key='nav_page', label_visibility='collapsed')
    with header_col3:
        refresh = st.button(t("refresh_data"))
    with header_col4:
        locale_names = list(SUPPORTED_LOCALES.values())
        locale_codes = list(SUPPORTED_LOCALES.keys())
        current_idx = locale_codes.index(get_locale()) if get_locale() in locale_codes else 0
        selected_lang = st.selectbox(
            t("language"), locale_names,
            index=current_idx,
            key='lang_select', label_visibility='collapsed'
        )
        new_locale = locale_codes[locale_names.index(selected_lang)]
        if new_locale != get_locale():
            set_locale(new_locale)
            st.rerun()
    with header_col5:
        theme_icon = "🌙" if st.session_state.theme == 'light' else "☀️"
        if st.button(theme_icon, help="Toggle theme"):
            st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
            st.rerun()

    st.markdown("")
    if refresh:
        st.cache_data.clear()

    # ── Route to selected page ──
    if page == t("nav_prompt_log"):
        render_prompt_logging_page(
            apply_chart_theme_fn=apply_chart_theme,
            chart_colors=CHART_COLORS,
            theme_colors=current_theme,
            get_username_fn=get_username,
        )
        return

    # ── Usage Dashboard (original content below) ──
    try:
        # Auto-discover table name from Glue database
        table_name = resolve_table_name()

        # ── Global Filters (date range + programming language) ──
        st.markdown(f"#### {t('filters')}")
        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([2, 2, 2, 2])

        # Fetch available date range
        df_date_range = fetch_data(f"SELECT MIN(date) as min_date, MAX(date) as max_date FROM {table_name}")
        data_min_date = pd.to_datetime(df_date_range['min_date'].iloc[0]).date()
        data_max_date = pd.to_datetime(df_date_range['max_date'].iloc[0]).date()

        with filter_col1:
            start_date = st.date_input(t("start_date"), value=data_min_date,
                                       min_value=data_min_date, max_value=data_max_date)
        with filter_col2:
            end_date = st.date_input(t("end_date"), value=data_max_date,
                                     min_value=data_min_date, max_value=data_max_date)

        # Fetch available programming languages (if column exists)
        try:
            df_langs = fetch_data(
                f"SELECT DISTINCT programming_language FROM {table_name} "
                f"WHERE programming_language IS NOT NULL AND programming_language != '' "
                f"ORDER BY programming_language"
            )
            languages = ['All'] + df_langs['programming_language'].tolist()
        except Exception:
            languages = ['All']

        with filter_col3:
            selected_language = st.selectbox(t("programming_language"), languages,
                                             help=t("filter_by_language_help"))
        with filter_col4:
            st.markdown("")  # spacer
            st.markdown("")
            st.markdown(t("data_range", min_date=data_min_date, max_date=data_max_date))

        where_clause = build_where_clause(table_name, start_date, end_date,
                                          selected_language if selected_language != 'All' else None)

        st.markdown("---")


        with st.expander(t("metric_definitions"), expanded=False):
            st.markdown(t("metric_definitions_body"))

        # ══════════════════════════════════════════════════════════════
        # SECTION 1: Subscription Overview (Official Dashboard Metrics)
        # ══════════════════════════════════════════════════════════════
        st.header(t("subscription_overview"))
        st.caption(t("subscription_overview_caption"))

        # Query subscription data: total / active / pending per tier
        # Active = users who have at least one record (they used Kiro)
        # We derive subscription status from activity data:
        #   - A userid with total_messages > 0 in the period is "Active"
        #   - A userid with total_messages = 0 (or only null) is "Pending"
        query_subscriptions = f"""
        SELECT
            subscription_tier,
            userid,
            SUM(TRY_CAST(total_messages AS INTEGER)) as total_messages
        FROM {table_name}
        {where_clause}
        GROUP BY subscription_tier, userid
        """
        df_subs = fetch_data(query_subscriptions)
        df_subs['total_messages'] = df_subs['total_messages'].apply(safe_int)

        # Derive status
        df_subs['status'] = df_subs['total_messages'].apply(
            lambda x: 'Active' if x > 0 else 'Pending'
        )

        # Aggregate per tier
        tier_total = df_subs.groupby('subscription_tier')['userid'].nunique().reset_index()
        tier_total.columns = ['subscription_tier', 'total']

        tier_active = df_subs[df_subs['status'] == 'Active'].groupby('subscription_tier')['userid'].nunique().reset_index()
        tier_active.columns = ['subscription_tier', 'active']

        tier_pending = df_subs[df_subs['status'] == 'Pending'].groupby('subscription_tier')['userid'].nunique().reset_index()
        tier_pending.columns = ['subscription_tier', 'pending']

        tier_summary = tier_total.merge(tier_active, on='subscription_tier', how='left') \
                                 .merge(tier_pending, on='subscription_tier', how='left')
        tier_summary['active'] = tier_summary['active'].fillna(0).astype(int)
        tier_summary['pending'] = tier_summary['pending'].fillna(0).astype(int)

        # Overall totals
        total_all = df_subs['userid'].nunique()
        active_all = df_subs[df_subs['status'] == 'Active']['userid'].nunique()
        pending_all = df_subs[df_subs['status'] == 'Pending']['userid'].nunique()

        # --- Total Subscriptions per Tier ---
        st.subheader(t("total_subs_per_tier"))
        st.caption(t("total_subs_per_tier_caption"))
        tier_cols = st.columns(len(tier_summary) + 1)
        with tier_cols[0]:
            st.metric(t("all_tiers"), total_all)
        for i, row in tier_summary.iterrows():
            with tier_cols[i + 1]:
                st.metric(row['subscription_tier'], row['total'])

        col_sub1, col_sub2 = st.columns(2)

        # --- Active Subscriptions per Tier ---
        with col_sub1:
            st.subheader(t("active_subs_per_tier"))
            st.caption(t("active_subs_caption"))
            active_cols = st.columns(len(tier_summary) + 1)
            with active_cols[0]:
                st.metric(t("all_active"), active_all,
                          delta=t("pct_of_total", pct=f"{active_all / max(total_all, 1) * 100:.0f}"))
            for i, row in tier_summary.iterrows():
                with active_cols[i + 1]:
                    st.metric(f"{row['subscription_tier']}", row['active'])

        # --- Pending Subscriptions per Tier ---
        with col_sub2:
            st.subheader(t("pending_subs_per_tier"))
            st.caption(t("pending_subs_caption"))
            pending_cols = st.columns(len(tier_summary) + 1)
            with pending_cols[0]:
                st.metric(t("all_pending"), pending_all,
                          delta=t("pct_of_total", pct=f"{pending_all / max(total_all, 1) * 100:.0f}"))
            for i, row in tier_summary.iterrows():
                with pending_cols[i + 1]:
                    st.metric(f"{row['subscription_tier']}", row['pending'])

        # Subscription tier pie chart
        col_pie1, col_pie2 = st.columns(2)
        with col_pie1:
            fig_sub_tier = px.pie(
                tier_summary, values='total', names='subscription_tier',
                title=t("subs_by_tier"), hole=0.45,
                color_discrete_sequence=CHART_COLORS
            )
            fig_sub_tier.update_traces(textinfo='label+percent+value', textposition='outside')
            apply_chart_theme(fig_sub_tier)
            st.plotly_chart(fig_sub_tier, use_container_width=True)

        with col_pie2:
            status_data = pd.DataFrame({
                'Status': ['Active', 'Pending'],
                'Count': [active_all, pending_all]
            })
            fig_sub_status = px.pie(
                status_data, values='Count', names='Status',
                title=t("active_vs_pending"), hole=0.45,
                color_discrete_sequence=['#06d6a0', '#f77f00']
            )
            fig_sub_status.update_traces(textinfo='label+percent+value', textposition='outside')
            apply_chart_theme(fig_sub_status)
            st.plotly_chart(fig_sub_status, use_container_width=True)

        st.markdown("---")


        # ══════════════════════════════════════════════════════════════
        # SECTION 2: Active Users — DAU / WAU / MAU (Official Dashboard)
        # ══════════════════════════════════════════════════════════════
        st.header(t("active_users_header"))
        st.caption(t("active_users_caption"))

        # Fetch raw user-level daily data for active user computation
        query_user_daily = f"""
        SELECT
            date,
            userid,
            client_type,
            subscription_tier
        FROM {table_name}
        {where_clause}
        """
        df_user_daily = fetch_data(query_user_daily)
        df_user_daily['date'] = pd.to_datetime(df_user_daily['date'])

        # Compute DAU, WAU, MAU
        dau, wau, mau = compute_wau_mau(df_user_daily)

        # Time granularity selector
        time_view = st.radio(t("time_granularity"), [t("daily_dau"), t("weekly_wau"), t("monthly_mau")],
                             horizontal=True, key='active_users_granularity')

        if time_view == t("daily_dau"):
            fig_au = px.line(dau, x='date', y='active_users',
                             title=t("dau_title"), markers=True,
                             labels={'active_users': t("active_users_label"), 'date': t("date_label")},
                             color_discrete_sequence=['#4361ee'])
            fig_au.update_traces(line=dict(width=2.5), marker=dict(size=5))
            apply_chart_theme(fig_au)
            st.plotly_chart(fig_au, use_container_width=True)
        elif time_view == t("weekly_wau"):
            fig_au = px.bar(wau, x='week', y='active_users',
                            title=t("wau_title"),
                            labels={'active_users': t("active_users_label"), 'week': t("week_label")},
                            color_discrete_sequence=['#3a0ca3'])
            fig_au.update_traces(marker_line_width=0)
            apply_chart_theme(fig_au)
            st.plotly_chart(fig_au, use_container_width=True)
        else:
            fig_au = px.bar(mau, x='month', y='active_users',
                            title=t("mau_title"),
                            labels={'active_users': t("active_users_label"), 'month': t("month_label")},
                            color_discrete_sequence=['#7209b7'])
            fig_au.update_traces(marker_line_width=0)
            apply_chart_theme(fig_au)
            st.plotly_chart(fig_au, use_container_width=True)

        # Breakdown by client type and subscription tier
        col_au1, col_au2 = st.columns(2)

        with col_au1:
            st.subheader(t("by_client_type"))
            df_user_daily['week'] = df_user_daily['date'].dt.isocalendar().year.astype(str) + '-W' + \
                                    df_user_daily['date'].dt.isocalendar().week.astype(str).str.zfill(2)
            df_user_daily['month'] = df_user_daily['date'].dt.to_period('M').astype(str)

            if time_view == t("daily_dau"):
                au_ct = df_user_daily.groupby(['date', 'client_type'])['userid'].nunique().reset_index()
                au_ct.columns = ['date', 'client_type', 'active_users']
                fig_au_ct = px.line(au_ct, x='date', y='active_users', color='client_type',
                                   title=t("active_users_by_client"), markers=True,
                                   color_discrete_sequence=CHART_COLORS)
            elif time_view == t("weekly_wau"):
                au_ct = df_user_daily.groupby(['week', 'client_type'])['userid'].nunique().reset_index()
                au_ct.columns = ['week', 'client_type', 'active_users']
                fig_au_ct = px.bar(au_ct, x='week', y='active_users', color='client_type',
                                  title=t("active_users_by_client"), barmode='group',
                                  color_discrete_sequence=CHART_COLORS)
            else:
                au_ct = df_user_daily.groupby(['month', 'client_type'])['userid'].nunique().reset_index()
                au_ct.columns = ['month', 'client_type', 'active_users']
                fig_au_ct = px.bar(au_ct, x='month', y='active_users', color='client_type',
                                  title=t("active_users_by_client"), barmode='group',
                                  color_discrete_sequence=CHART_COLORS)
            apply_chart_theme(fig_au_ct)
            st.plotly_chart(fig_au_ct, use_container_width=True)

        with col_au2:
            st.subheader(t("by_subscription_tier"))
            if time_view == t("daily_dau"):
                au_tier = df_user_daily.groupby(['date', 'subscription_tier'])['userid'].nunique().reset_index()
                au_tier.columns = ['date', 'subscription_tier', 'active_users']
                fig_au_tier = px.line(au_tier, x='date', y='active_users', color='subscription_tier',
                                     title=t("active_users_by_tier"), markers=True,
                                     color_discrete_sequence=CHART_COLORS[3:])
            elif time_view == t("weekly_wau"):
                au_tier = df_user_daily.groupby(['week', 'subscription_tier'])['userid'].nunique().reset_index()
                au_tier.columns = ['week', 'subscription_tier', 'active_users']
                fig_au_tier = px.bar(au_tier, x='week', y='active_users', color='subscription_tier',
                                    title=t("active_users_by_tier"), barmode='group',
                                    color_discrete_sequence=CHART_COLORS[3:])
            else:
                au_tier = df_user_daily.groupby(['month', 'subscription_tier'])['userid'].nunique().reset_index()
                au_tier.columns = ['month', 'subscription_tier', 'active_users']
                fig_au_tier = px.bar(au_tier, x='month', y='active_users', color='subscription_tier',
                                    title=t("active_users_by_tier"), barmode='group',
                                    color_discrete_sequence=CHART_COLORS[3:])
            apply_chart_theme(fig_au_tier)
            st.plotly_chart(fig_au_tier, use_container_width=True)

        st.markdown("---")


        # ══════════════════════════════════════════════════════════════
        # SECTION 3: Credits Consumed — DAU / WAU / MAU (Official Dashboard)
        # ══════════════════════════════════════════════════════════════
        st.header(t("credits_consumed_header"))
        st.caption(t("credits_consumed_caption"))

        # Fetch credits data at daily granularity
        query_credits_daily = f"""
        SELECT
            date,
            userid,
            client_type,
            subscription_tier,
            TRY_CAST(credits_used AS DOUBLE) as credits_used
        FROM {table_name}
        {where_clause}
        """
        df_credits_daily = fetch_data(query_credits_daily)
        df_credits_daily['date'] = pd.to_datetime(df_credits_daily['date'])
        df_credits_daily['credits_used'] = df_credits_daily['credits_used'].apply(safe_float)
        df_credits_daily['week'] = df_credits_daily['date'].dt.isocalendar().year.astype(str) + '-W' + \
                                   df_credits_daily['date'].dt.isocalendar().week.astype(str).str.zfill(2)
        df_credits_daily['month'] = df_credits_daily['date'].dt.to_period('M').astype(str)

        credits_view = st.radio(t("time_granularity"), [t("daily"), t("weekly"), t("monthly")],
                                horizontal=True, key='credits_granularity')

        if credits_view == t("daily"):
            cr_agg = df_credits_daily.groupby('date')['credits_used'].sum().reset_index()
            fig_cr = px.line(cr_agg, x='date', y='credits_used',
                             title=t("daily_credits_title"), markers=True,
                             labels={'credits_used': t("credits_label"), 'date': t("date_label")},
                             color_discrete_sequence=['#06d6a0'])
            fig_cr.update_traces(line=dict(width=2.5), marker=dict(size=5))
        elif credits_view == t("weekly"):
            cr_agg = df_credits_daily.groupby('week')['credits_used'].sum().reset_index()
            fig_cr = px.bar(cr_agg, x='week', y='credits_used',
                            title=t("weekly_credits_title"),
                            labels={'credits_used': t("credits_label"), 'week': t("week_label")},
                            color_discrete_sequence=['#06d6a0'])
            fig_cr.update_traces(marker_line_width=0)
        else:
            cr_agg = df_credits_daily.groupby('month')['credits_used'].sum().reset_index()
            fig_cr = px.bar(cr_agg, x='month', y='credits_used',
                            title=t("monthly_credits_title"),
                            labels={'credits_used': t("credits_label"), 'month': t("month_label")},
                            color_discrete_sequence=['#06d6a0'])
            fig_cr.update_traces(marker_line_width=0)
        apply_chart_theme(fig_cr)
        st.plotly_chart(fig_cr, use_container_width=True)

        # Breakdown by tier and client type
        col_cr1, col_cr2 = st.columns(2)

        with col_cr1:
            st.subheader(t("credits_by_tier"))
            if credits_view == t("daily"):
                cr_tier = df_credits_daily.groupby(['date', 'subscription_tier'])['credits_used'].sum().reset_index()
                fig_cr_tier = px.line(cr_tier, x='date', y='credits_used', color='subscription_tier',
                                     title=t("credits_by_tier_title"), markers=True,
                                     color_discrete_sequence=CHART_COLORS)
            elif credits_view == t("weekly"):
                cr_tier = df_credits_daily.groupby(['week', 'subscription_tier'])['credits_used'].sum().reset_index()
                fig_cr_tier = px.bar(cr_tier, x='week', y='credits_used', color='subscription_tier',
                                    title=t("credits_by_tier_title"), barmode='group',
                                    color_discrete_sequence=CHART_COLORS)
            else:
                cr_tier = df_credits_daily.groupby(['month', 'subscription_tier'])['credits_used'].sum().reset_index()
                fig_cr_tier = px.bar(cr_tier, x='month', y='credits_used', color='subscription_tier',
                                    title=t("credits_by_tier_title"), barmode='group',
                                    color_discrete_sequence=CHART_COLORS)
            apply_chart_theme(fig_cr_tier)
            st.plotly_chart(fig_cr_tier, use_container_width=True)

        with col_cr2:
            st.subheader(t("credits_by_client"))
            if credits_view == t("daily"):
                cr_ct = df_credits_daily.groupby(['date', 'client_type'])['credits_used'].sum().reset_index()
                fig_cr_ct = px.line(cr_ct, x='date', y='credits_used', color='client_type',
                                   title=t("credits_by_client_title"), markers=True,
                                   color_discrete_sequence=CHART_COLORS[3:])
            elif credits_view == t("weekly"):
                cr_ct = df_credits_daily.groupby(['week', 'client_type'])['credits_used'].sum().reset_index()
                fig_cr_ct = px.bar(cr_ct, x='week', y='credits_used', color='client_type',
                                  title=t("credits_by_client_title"), barmode='group',
                                  color_discrete_sequence=CHART_COLORS[3:])
            else:
                cr_ct = df_credits_daily.groupby(['month', 'client_type'])['credits_used'].sum().reset_index()
                fig_cr_ct = px.bar(cr_ct, x='month', y='credits_used', color='client_type',
                                  title=t("credits_by_client_title"), barmode='group',
                                  color_discrete_sequence=CHART_COLORS[3:])
            apply_chart_theme(fig_cr_ct)
            st.plotly_chart(fig_cr_ct, use_container_width=True)

        st.markdown("---")


        # ══════════════════════════════════════════════════════════════
        # SECTION 4: Overall Metrics (existing)
        # ══════════════════════════════════════════════════════════════
        st.header(t("overall_metrics"))

        query_overall = f"""
        SELECT
            COUNT(DISTINCT userid) as total_users,
            COUNT(DISTINCT profileid) as total_profiles,
            SUM(TRY_CAST(total_messages AS INTEGER)) as total_messages,
            SUM(TRY_CAST(chat_conversations AS INTEGER)) as total_conversations,
            SUM(TRY_CAST(credits_used AS DOUBLE)) as total_credits,
            SUM(TRY_CAST(overage_credits_used AS DOUBLE)) as total_overage
        FROM {table_name}
        {where_clause}
        """
        df_overall = fetch_data(query_overall)

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric(t("total_users"), safe_int(df_overall['total_users'].iloc[0]),
                      help=t("total_users_help"))
        with col2:
            st.metric(t("total_profiles"), safe_int(df_overall['total_profiles'].iloc[0]),
                      help=t("total_profiles_help"))
        with col3:
            st.metric(t("total_messages"), f"{safe_int(df_overall['total_messages'].iloc[0]):,}",
                      help=t("total_messages_help"))
        with col4:
            st.metric(t("chat_conversations"), f"{safe_int(df_overall['total_conversations'].iloc[0]):,}",
                      help=t("chat_conversations_help"))
        with col5:
            st.metric(t("credits_used"), f"{safe_float(df_overall['total_credits'].iloc[0]):,.1f}",
                      help=t("credits_used_help"))
        with col6:
            st.metric(t("overage_credits"), f"{safe_float(df_overall['total_overage'].iloc[0]):,.1f}",
                      help=t("overage_credits_help"))

        st.markdown("---")

        # ══════════════════════════════════════════════════════════════
        # SECTION 5: Usage by Client Type (existing)
        # ══════════════════════════════════════════════════════════════
        st.header(t("usage_by_client"))

        query_client = f"""
        SELECT
            client_type,
            COUNT(DISTINCT userid) as unique_users,
            SUM(TRY_CAST(total_messages AS INTEGER)) as total_messages,
            SUM(TRY_CAST(chat_conversations AS INTEGER)) as total_conversations,
            SUM(TRY_CAST(credits_used AS DOUBLE)) as total_credits
        FROM {table_name}
        {where_clause}
        GROUP BY client_type
        ORDER BY total_messages DESC
        """
        df_client = fetch_data(query_client)
        for c in ['unique_users', 'total_messages', 'total_conversations']:
            df_client[c] = df_client[c].apply(safe_int)
        df_client['total_credits'] = df_client['total_credits'].apply(safe_float)

        col1, col2 = st.columns(2)
        with col1:
            fig_client_pie = px.pie(
                df_client, values='total_messages', names='client_type',
                title=t("messages_by_client"), hole=0.45,
                color_discrete_sequence=CHART_COLORS
            )
            fig_client_pie.update_traces(textinfo='label+percent', textposition='outside',
                                         pull=[0.03] * len(df_client))
            apply_chart_theme(fig_client_pie)
            st.plotly_chart(fig_client_pie, use_container_width=True)

        with col2:
            fig_client_bar = px.bar(
                df_client, x='client_type', y='total_credits',
                title=t("credits_used_by_client"),
                color='client_type', text='total_credits',
                color_discrete_sequence=CHART_COLORS,
                labels={'total_credits': 'Credits', 'client_type': 'Client Type'}
            )
            fig_client_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside',
                                          marker_line_width=0)
            fig_client_bar.update_layout(showlegend=False, bargap=0.4)
            apply_chart_theme(fig_client_bar)
            st.plotly_chart(fig_client_bar, use_container_width=True)

        st.markdown("---")

        # ══════════════════════════════════════════════════════════════
        # SECTION 6: Top 10 Users by Messages (existing)
        # ══════════════════════════════════════════════════════════════
        st.header(t("top_users_header"))

        query_top_users = f"""
        SELECT
            userid,
            SUM(TRY_CAST(total_messages AS INTEGER)) as total_messages,
            SUM(TRY_CAST(chat_conversations AS INTEGER)) as total_conversations,
            SUM(TRY_CAST(credits_used AS DOUBLE)) as total_credits
        FROM {table_name}
        {where_clause}
        GROUP BY userid
        ORDER BY total_messages DESC
        LIMIT 10
        """
        df_top = fetch_data(query_top_users)
        df_top['userid'] = df_top['userid'].str.replace("'", "").str.replace('"', '')
        df_top['total_messages'] = df_top['total_messages'].apply(safe_int)
        df_top['total_conversations'] = df_top['total_conversations'].apply(safe_int)
        df_top['total_credits'] = df_top['total_credits'].apply(safe_float)

        userids = df_top['userid'].tolist()
        umap = get_usernames_batch(userids)
        df_top['username'] = df_top['userid'].map(umap)

        col1, col2 = st.columns([2, 3])
        with col1:
            st.subheader(t("leaderboard"))
            for idx, row in df_top.iterrows():
                rank = idx + 1
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
                st.markdown(f"**{medal} {row['username']}** — {row['total_messages']:,} {t('messages_word')}")

        with col2:
            fig_top = px.bar(
                df_top, x='username', y='total_messages',
                title=t("messages_sent"), color='total_messages',
                color_continuous_scale='Purples',
                labels={'total_messages': 'Messages', 'username': 'User'}
            )
            fig_top.update_traces(marker_line_width=0)
            fig_top.update_layout(xaxis_tickangle=-45, showlegend=False, height=400, coloraxis_showscale=False)
            apply_chart_theme(fig_top)
            st.plotly_chart(fig_top, use_container_width=True)

        st.markdown("---")


        # ══════════════════════════════════════════════════════════════
        # SECTION 7: Daily Activity Trends (existing)
        # ══════════════════════════════════════════════════════════════
        st.header(t("daily_activity_header"))

        query_daily = f"""
        SELECT
            date,
            SUM(TRY_CAST(total_messages AS INTEGER)) as messages,
            SUM(TRY_CAST(chat_conversations AS INTEGER)) as conversations,
            SUM(TRY_CAST(credits_used AS DOUBLE)) as credits,
            COUNT(DISTINCT userid) as active_users
        FROM {table_name}
        {where_clause}
        GROUP BY date
        ORDER BY date
        """
        df_daily = fetch_data(query_daily)
        df_daily['date'] = pd.to_datetime(df_daily['date'])
        df_daily['messages'] = df_daily['messages'].apply(safe_int)
        df_daily['conversations'] = df_daily['conversations'].apply(safe_int)
        df_daily['credits'] = df_daily['credits'].apply(safe_float)
        df_daily['active_users'] = df_daily['active_users'].apply(safe_int)

        fig_daily = make_subplots(
            rows=2, cols=2,
            subplot_titles=(t("total_messages_chart"), t("chat_conversations_chart"), t("credits_used_chart"), t("active_users_chart")),
            vertical_spacing=0.15, horizontal_spacing=0.15
        )
        fig_daily.add_trace(
            go.Scatter(x=df_daily['date'], y=df_daily['messages'],
                       mode='lines+markers', name='Messages',
                       line=dict(color='#4361ee', width=2.5), marker=dict(size=5)),
            row=1, col=1)
        fig_daily.add_trace(
            go.Scatter(x=df_daily['date'], y=df_daily['conversations'],
                       mode='lines+markers', name='Conversations',
                       line=dict(color='#f72585', width=2.5), marker=dict(size=5)),
            row=1, col=2)
        fig_daily.add_trace(
            go.Scatter(x=df_daily['date'], y=df_daily['credits'],
                       mode='lines+markers', name='Credits',
                       line=dict(color='#06d6a0', width=2.5), marker=dict(size=5)),
            row=2, col=1)
        fig_daily.add_trace(
            go.Scatter(x=df_daily['date'], y=df_daily['active_users'],
                       mode='lines+markers', name='Active Users',
                       line=dict(color='#f77f00', width=2.5), marker=dict(size=5)),
            row=2, col=2)
        fig_daily.update_layout(height=600, showlegend=False,
                                title=dict(text=t("daily_activity_overview"), x=0.5, xanchor='center'))
        apply_chart_theme(fig_daily)
        st.plotly_chart(fig_daily, use_container_width=True)

        st.markdown("---")

        # ══════════════════════════════════════════════════════════════
        # SECTION 8: Daily Trends by Client Type (existing)
        # ══════════════════════════════════════════════════════════════
        st.header(t("daily_trends_client"))

        query_daily_client = f"""
        SELECT
            date,
            client_type,
            SUM(TRY_CAST(total_messages AS INTEGER)) as messages,
            SUM(TRY_CAST(chat_conversations AS INTEGER)) as conversations
        FROM {table_name}
        {where_clause}
        GROUP BY date, client_type
        ORDER BY date
        """
        df_dc = fetch_data(query_daily_client)
        df_dc['date'] = pd.to_datetime(df_dc['date'])
        df_dc['messages'] = df_dc['messages'].apply(safe_int)
        df_dc['conversations'] = df_dc['conversations'].apply(safe_int)

        col1, col2 = st.columns(2)
        with col1:
            fig_msg_client = px.line(
                df_dc, x='date', y='messages', color='client_type',
                title=t("daily_messages_by_client"), markers=True,
                color_discrete_sequence=CHART_COLORS,
                labels={'messages': 'Messages', 'date': 'Date', 'client_type': 'Client'}
            )
            fig_msg_client.update_traces(line=dict(width=2.5), marker=dict(size=5))
            apply_chart_theme(fig_msg_client)
            st.plotly_chart(fig_msg_client, use_container_width=True)

        with col2:
            fig_conv_client = px.line(
                df_dc, x='date', y='conversations', color='client_type',
                title=t("daily_convos_by_client"), markers=True,
                color_discrete_sequence=CHART_COLORS[2:],
                labels={'conversations': 'Conversations', 'date': 'Date', 'client_type': 'Client'}
            )
            fig_conv_client.update_traces(line=dict(width=2.5), marker=dict(size=5))
            apply_chart_theme(fig_conv_client)
            st.plotly_chart(fig_conv_client, use_container_width=True)

        st.markdown("---")


        # ══════════════════════════════════════════════════════════════
        # SECTION 9: Credits Analysis (existing)
        # ══════════════════════════════════════════════════════════════
        st.header(t("credits_analysis"))

        query_credits_user = f"""
        SELECT
            userid,
            SUM(TRY_CAST(credits_used AS DOUBLE)) as total_credits,
            SUM(TRY_CAST(overage_credits_used AS DOUBLE)) as total_overage,
            MAX(TRY_CAST(overage_cap AS DOUBLE)) as overage_cap,
            MAX(overage_enabled) as overage_enabled
        FROM {table_name}
        {where_clause}
        GROUP BY userid
        ORDER BY total_credits DESC
        """
        df_credits = fetch_data(query_credits_user)
        df_credits['userid'] = df_credits['userid'].str.replace("'", "").str.replace('"', '')
        df_credits['total_credits'] = df_credits['total_credits'].apply(safe_float)
        df_credits['total_overage'] = df_credits['total_overage'].apply(safe_float)
        df_credits['overage_cap'] = df_credits['overage_cap'].apply(safe_float)

        umap_credits = get_usernames_batch(df_credits['userid'].tolist())
        df_credits['username'] = df_credits['userid'].map(umap_credits)
        df_credits['combined_credits'] = df_credits['total_credits'] + df_credits['total_overage']

        col1, col2 = st.columns(2)
        with col1:
            fig_credits = px.bar(
                df_credits.head(15), x='username', y='combined_credits',
                title=t("top15_credits"),
                color='combined_credits', color_continuous_scale='Sunset',
                labels={'combined_credits': 'Credits', 'username': 'User'}
            )
            fig_credits.update_traces(marker_line_width=0)
            fig_credits.update_layout(xaxis_tickangle=-45, showlegend=False, coloraxis_showscale=False)
            apply_chart_theme(fig_credits)
            st.plotly_chart(fig_credits, use_container_width=True)

        with col2:
            df_credits_summary = pd.DataFrame({
                'Category': [t("base_credits"), t("overage_credits")],
                'Amount': [
                    df_credits['total_credits'].sum(),
                    df_credits['total_overage'].sum()
                ]
            })
            fig_overage = px.pie(
                df_credits_summary, values='Amount', names='Category',
                title=t("base_vs_overage"), hole=0.45,
                color_discrete_sequence=['#4361ee', '#f72585']
            )
            fig_overage.update_traces(textinfo='label+percent', textposition='outside',
                                       pull=[0.03, 0.03])
            apply_chart_theme(fig_overage)
            st.plotly_chart(fig_overage, use_container_width=True)

        # Monthly credit usage by user table
        st.subheader(t("credit_usage_by_month"))

        query_credits_monthly = f"""
        SELECT
            userid,
            DATE_FORMAT(DATE_PARSE(date, '%Y-%m-%d'), '%Y-%m') as month,
            SUM(TRY_CAST(credits_used AS DOUBLE)) as credits_used
        FROM {table_name}
        {where_clause}
        GROUP BY userid, DATE_FORMAT(DATE_PARSE(date, '%Y-%m-%d'), '%Y-%m')
        ORDER BY month, userid
        """
        df_credits_monthly = fetch_data(query_credits_monthly)
        df_credits_monthly['userid'] = df_credits_monthly['userid'].str.replace("'", "").str.replace('"', '')
        df_credits_monthly['credits_used'] = df_credits_monthly['credits_used'].apply(safe_float)

        umap_monthly = get_usernames_batch(df_credits_monthly['userid'].unique().tolist())
        df_credits_monthly['User'] = df_credits_monthly['userid'].map(umap_monthly)

        df_pivot = df_credits_monthly.pivot_table(
            index='User', columns='month', values='credits_used',
            aggfunc='sum', fill_value=0
        )
        df_pivot = df_pivot[sorted(df_pivot.columns)]
        df_pivot['Total'] = df_pivot.sum(axis=1)
        df_pivot = df_pivot.sort_values('Total', ascending=False)
        df_pivot = df_pivot.round(1)

        st.dataframe(df_pivot, use_container_width=True, height=400)

        st.markdown("---")

        # ══════════════════════════════════════════════════════════════
        # SECTION 10: Subscription Tier Breakdown (existing)
        # ══════════════════════════════════════════════════════════════
        st.header(t("tier_breakdown"))

        query_tier = f"""
        SELECT
            subscription_tier,
            COUNT(DISTINCT userid) as unique_users,
            SUM(TRY_CAST(total_messages AS INTEGER)) as total_messages,
            SUM(TRY_CAST(credits_used AS DOUBLE)) as total_credits
        FROM {table_name}
        {where_clause}
        GROUP BY subscription_tier
        ORDER BY total_messages DESC
        """
        df_tier = fetch_data(query_tier)
        df_tier['unique_users'] = df_tier['unique_users'].apply(safe_int)
        df_tier['total_messages'] = df_tier['total_messages'].apply(safe_int)
        df_tier['total_credits'] = df_tier['total_credits'].apply(safe_float)

        col1, col2 = st.columns(2)
        with col1:
            fig_tier_users = px.bar(
                df_tier, x='subscription_tier', y='unique_users',
                title=t("users_by_tier"), color='subscription_tier',
                color_discrete_sequence=CHART_COLORS,
                labels={'unique_users': 'Users', 'subscription_tier': 'Tier'}
            )
            fig_tier_users.update_traces(marker_line_width=0)
            fig_tier_users.update_layout(showlegend=False, bargap=0.4)
            apply_chart_theme(fig_tier_users)
            st.plotly_chart(fig_tier_users, use_container_width=True)

        with col2:
            fig_tier_credits = px.bar(
                df_tier, x='subscription_tier', y='total_credits',
                title=t("credits_by_tier_chart"), color='subscription_tier',
                color_discrete_sequence=CHART_COLORS[3:],
                labels={'total_credits': 'Credits', 'subscription_tier': 'Tier'}
            )
            fig_tier_credits.update_traces(marker_line_width=0)
            fig_tier_credits.update_layout(showlegend=False, bargap=0.4)
            apply_chart_theme(fig_tier_credits)
            st.plotly_chart(fig_tier_credits, use_container_width=True)

        st.markdown("---")


        # ══════════════════════════════════════════════════════════════
        # SECTION 10b: Profile Distribution
        # ══════════════════════════════════════════════════════════════
        st.header(t("profile_distribution"))
        st.caption(t("profile_distribution_caption"))

        query_profiles = f"""
        SELECT
            profileid,
            COUNT(DISTINCT userid) as unique_users,
            SUM(TRY_CAST(total_messages AS INTEGER)) as total_messages,
            SUM(TRY_CAST(credits_used AS DOUBLE)) as total_credits
        FROM {table_name}
        {where_clause}
        GROUP BY profileid
        ORDER BY unique_users DESC
        """
        df_profiles = fetch_data(query_profiles)
        df_profiles['unique_users'] = df_profiles['unique_users'].apply(safe_int)
        df_profiles['total_messages'] = df_profiles['total_messages'].apply(safe_int)
        df_profiles['total_credits'] = df_profiles['total_credits'].apply(safe_float)
        df_profiles['profileid'] = df_profiles['profileid'].fillna('Unknown')

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            fig_profile_users = px.bar(
                df_profiles.head(15), x='profileid', y='unique_users',
                title=t("users_per_profile"), color='unique_users',
                color_continuous_scale='Blues',
                labels={'unique_users': 'Users', 'profileid': 'Profile ID'}
            )
            fig_profile_users.update_traces(marker_line_width=0)
            fig_profile_users.update_layout(xaxis_tickangle=-45, showlegend=False, coloraxis_showscale=False)
            apply_chart_theme(fig_profile_users)
            st.plotly_chart(fig_profile_users, use_container_width=True)

        with col_p2:
            fig_profile_credits = px.bar(
                df_profiles.head(15), x='profileid', y='total_credits',
                title=t("credits_per_profile"), color='total_credits',
                color_continuous_scale='Oranges',
                labels={'total_credits': 'Credits', 'profileid': 'Profile ID'}
            )
            fig_profile_credits.update_traces(marker_line_width=0)
            fig_profile_credits.update_layout(xaxis_tickangle=-45, showlegend=False, coloraxis_showscale=False)
            apply_chart_theme(fig_profile_credits)
            st.plotly_chart(fig_profile_credits, use_container_width=True)

        # Profile summary table
        st.subheader(t("profile_summary"))
        df_profile_display = df_profiles[['profileid', 'unique_users', 'total_messages', 'total_credits']].copy()
        df_profile_display.columns = ['Profile ID', 'Users', 'Messages', 'Credits']
        df_profile_display['Credits'] = df_profile_display['Credits'].round(1)
        st.dataframe(df_profile_display, use_container_width=True, hide_index=True)

        st.markdown("---")


        # ══════════════════════════════════════════════════════════════
        # SECTION 11: User Engagement Analysis (existing)
        # ══════════════════════════════════════════════════════════════
        st.header(t("user_engagement"))

        query_users = f"""
        SELECT
            userid,
            SUM(TRY_CAST(total_messages AS INTEGER)) as total_messages,
            SUM(TRY_CAST(chat_conversations AS INTEGER)) as total_conversations,
            SUM(TRY_CAST(credits_used AS DOUBLE)) as total_credits
        FROM {table_name}
        {where_clause}
        GROUP BY userid
        ORDER BY total_messages DESC
        """
        df_users = fetch_data(query_users)
        df_users['userid'] = df_users['userid'].str.replace("'", "").str.replace('"', '')
        df_users['total_messages'] = df_users['total_messages'].apply(safe_int)
        df_users['total_conversations'] = df_users['total_conversations'].apply(safe_int)
        df_users['total_credits'] = df_users['total_credits'].apply(safe_float)

        umap_users = get_usernames_batch(df_users['userid'].tolist())
        df_users['username'] = df_users['userid'].map(umap_users)

        # User segmentation
        st.subheader(t("user_segmentation"))

        def categorize_user(row):
            if row['total_messages'] >= 100 or row['total_conversations'] >= 20:
                return 'Power Users'
            elif row['total_messages'] >= 20 or row['total_conversations'] >= 5:
                return 'Active Users'
            elif row['total_messages'] > 0:
                return 'Light Users'
            else:
                return 'Idle Users'

        df_users['category'] = df_users.apply(categorize_user, axis=1)
        category_counts = df_users['category'].value_counts()
        pie_data = pd.DataFrame({'Category': category_counts.index, 'Count': category_counts.values})

        color_map = {'Power Users': '#4361ee', 'Active Users': '#06d6a0',
                     'Light Users': '#f77f00', 'Idle Users': '#e63946'}
        colors = [color_map.get(cat, '#999999') for cat in pie_data['Category']]

        col1, col2 = st.columns([2, 1])
        with col1:
            fig_seg = go.Figure(data=[go.Pie(
                labels=pie_data['Category'], values=pie_data['Count'], hole=0.45,
                marker=dict(colors=colors, line=dict(color=current_theme['bg'], width=3)),
                textinfo='label+percent+value', textposition='auto',
                hovertemplate='<b>%{label}</b><br>Users: %{value}<br>%{percent}<extra></extra>'
            )])
            fig_seg.update_layout(title=t("user_distribution"), height=450,
                                  showlegend=True,
                                  legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05))
            apply_chart_theme(fig_seg)
            st.plotly_chart(fig_seg, use_container_width=True)

        with col2:
            st.markdown(f"### {t('category_definitions')}")
            st.markdown(f"""
            **{t('category_power')}**
            {t('category_power_desc')}

            **{t('category_active')}**
            {t('category_active_desc')}

            **{t('category_light')}**
            {t('category_light_desc')}

            **{t('category_idle')}**
            {t('category_idle_desc')}
            """)
            st.markdown("---")
            st.markdown(f"### {t('quick_stats')}")
            for _, row in pie_data.iterrows():
                pct = (row['Count'] / pie_data['Count'].sum() * 100)
                st.metric(row['Category'], f"{row['Count']} {t('users_unit')}", f"{pct:.1f}%")

        st.markdown("---")

        # ── User Activity Timeline ──
        st.subheader(t("user_activity_timeline"))

        query_activity = f"""
        SELECT
            userid,
            MAX(profileid) as profileid,
            MAX(date) as last_active_date,
            MIN(date) as first_active_date,
            COUNT(DISTINCT date) as active_days
        FROM {table_name}
        {where_clause}
        GROUP BY userid
        """
        df_activity = fetch_data(query_activity)
        df_activity['userid'] = df_activity['userid'].str.replace("'", "").str.replace('"', '')
        df_activity['last_active_date'] = pd.to_datetime(df_activity['last_active_date'])
        df_activity['first_active_date'] = pd.to_datetime(df_activity['first_active_date'])
        df_activity['active_days'] = df_activity['active_days'].apply(safe_int)
        df_activity['days_since_last_active'] = (pd.Timestamp.now() - df_activity['last_active_date']).dt.days

        umap_act = get_usernames_batch(df_activity['userid'].tolist())
        df_activity['username'] = df_activity['userid'].map(umap_act)

        df_act_merged = df_activity.merge(
            df_users[['userid', 'category', 'total_messages', 'total_credits']],
            on='userid', how='left'
        )
        df_act_merged['profileid'] = df_act_merged['profileid'].fillna('')

        col1, col2 = st.columns(2)
        with col1:
            df_recent = df_act_merged.nsmallest(15, 'days_since_last_active')
            fig_last = px.bar(
                df_recent, y='username', x='days_since_last_active',
                title=t("days_since_last"),
                color='days_since_last_active', color_continuous_scale='Tealgrn_r',
                orientation='h', labels={'days_since_last_active': 'Days Ago', 'username': 'User'}
            )
            fig_last.update_traces(marker_line_width=0)
            fig_last.update_layout(height=500, yaxis={'categoryorder': 'total ascending'}, coloraxis_showscale=False)
            apply_chart_theme(fig_last)
            st.plotly_chart(fig_last, use_container_width=True)

        with col2:
            df_most = df_act_merged.nlargest(15, 'active_days')
            fig_days = px.bar(
                df_most, y='username', x='active_days',
                title=t("total_active_days"),
                color='active_days', color_continuous_scale='Purples',
                orientation='h', labels={'active_days': 'Active Days', 'username': 'User'}
            )
            fig_days.update_traces(marker_line_width=0)
            fig_days.update_layout(height=500, yaxis={'categoryorder': 'total ascending'}, coloraxis_showscale=False)
            apply_chart_theme(fig_days)
            st.plotly_chart(fig_days, use_container_width=True)

        # Detailed table
        st.markdown(f"#### {t('detailed_user_table')}")
        df_display = df_act_merged[['username', 'profileid', 'category', 'last_active_date',
                                     'days_since_last_active', 'active_days',
                                     'total_messages', 'total_credits']].copy()
        df_display.columns = ['User', 'Profile', 'Category', 'Last Active', 'Days Ago',
                              'Active Days', 'Messages', 'Credits']
        df_display['Last Active'] = df_display['Last Active'].dt.strftime('%Y-%m-%d')
        df_display = df_display.sort_values('Days Ago')

        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            cat_filter = st.multiselect(t("filter_by_category"),
                                        options=['All'] + sorted(df_display['Category'].dropna().unique().tolist()),
                                        default=['All'])
        with filter_col2:
            rec_filter = st.selectbox(t("filter_by_recency"),
                                      [t("all_users"), t("active_last_7"), t("recent_last_30"),
                                       t("inactive_30plus"), t("dormant_90plus")])
        with filter_col3:
            sort_by = st.selectbox(t("sort_by"), ['Days Ago', 'Active Days', 'Messages', 'Credits'])

        df_f = df_display.copy()
        if 'All' not in cat_filter:
            df_f = df_f[df_f['Category'].isin(cat_filter)]
        if rec_filter == t("active_last_7"):
            df_f = df_f[df_f['Days Ago'] <= 7]
        elif rec_filter == t("recent_last_30"):
            df_f = df_f[df_f['Days Ago'] <= 30]
        elif rec_filter == t("inactive_30plus"):
            df_f = df_f[df_f['Days Ago'] > 30]
        elif rec_filter == t("dormant_90plus"):
            df_f = df_f[df_f['Days Ago'] > 90]
        df_f = df_f.sort_values(sort_by, ascending=(sort_by == 'Days Ago'))

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric(t("filtered_users"), len(df_f))
        with m2:
            st.metric(t("avg_days_since_active"), f"{df_f['Days Ago'].mean():.1f}" if len(df_f) else "N/A")
        with m3:
            st.metric(t("avg_active_days"), f"{df_f['Active Days'].mean():.1f}" if len(df_f) else "N/A")
        with m4:
            st.metric(t("active_last_week"), len(df_f[df_f['Days Ago'] <= 7]))

        st.dataframe(df_f, use_container_width=True, height=400, hide_index=True)

        st.markdown("---")

        # ══════════════════════════════════════════════════════════════
        # SECTION 12: User Engagement Funnel (existing)
        # ══════════════════════════════════════════════════════════════
        st.header(t("engagement_funnel"))

        total_users = len(df_users)
        users_with_messages = len(df_users[df_users['total_messages'] > 0])
        users_with_convos = len(df_users[df_users['total_conversations'] > 0])
        active_users_count = len(df_users[df_users['total_messages'] >= 20])
        power_users = len(df_users[df_users['total_messages'] >= 100])

        funnel_data = pd.DataFrame({
            'Stage': [t("funnel_all_users"), t("funnel_sent_messages"), t("funnel_had_convos"),
                      t("funnel_active_users"), t("funnel_power_users")],
            'Count': [total_users, users_with_messages, users_with_convos, active_users_count, power_users]
        })
        funnel_data['Percentage'] = (funnel_data['Count'] / max(total_users, 1) * 100).round(1)

        col1, col2 = st.columns([3, 2])
        with col1:
            fig_funnel = go.Figure(go.Funnel(
                y=funnel_data['Stage'], x=funnel_data['Count'],
                textposition="inside", textinfo="value+percent initial", opacity=0.9,
                marker={"color": ['#4361ee', '#3a0ca3', '#7209b7', '#f72585', '#4cc9f0'],
                        "line": {"width": 0}},
                connector={"line": {"color": 'rgba(128,128,128,0.2)', "width": 1}}
            ))
            fig_funnel.update_layout(title=t("funnel_title"), height=500,
                                     margin=dict(l=20, r=20, t=60, b=20))
            apply_chart_theme(fig_funnel)
            st.plotly_chart(fig_funnel, use_container_width=True)

        with col2:
            st.subheader(t("funnel_metrics"))
            for _, row in funnel_data.iterrows():
                st.metric(label=row['Stage'], value=f"{row['Count']} users",
                          delta=f"{row['Percentage']}% of total")
                st.markdown("")

            st.markdown("---")
            st.subheader(t("conversion_rates"))
            if total_users > 0:
                st.markdown(f"**{t('message_activation')}:** {users_with_messages / total_users * 100:.1f}%")
                if users_with_messages > 0:
                    st.markdown(f"**{t('conversation_rate')}:** {users_with_convos / users_with_messages * 100:.1f}%")
                    st.markdown(f"**{t('active_retention')}:** {active_users_count / users_with_messages * 100:.1f}%")
                if active_users_count > 0:
                    st.markdown(f"**{t('power_user_growth')}:** {power_users / active_users_count * 100:.1f}%")

    except Exception as e:
        st.error(t("error_fetching", error=str(e)))
        st.info(t("ensure_info"))
        st.markdown(t("ensure_list"))

if __name__ == "__main__":
    main()
