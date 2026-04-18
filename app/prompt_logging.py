"""
Prompt Logging viewer — reads Kiro prompt log JSON files from S3,
parses inline-suggestion and chat-conversation records, and renders
an interactive explorer in Streamlit.

Log format reference:
  https://kiro.dev/docs/enterprise/monitor-and-track/prompt-logging/
"""

import gzip
import json
import re
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import boto3
from datetime import datetime, timedelta
from urllib.parse import urlparse
from config import AWS_REGION, PROMPT_LOG_S3_URI


# ── S3 helpers ──────────────────────────────────────────────────────

@st.cache_resource
def _get_s3_client():
    return boto3.client('s3', region_name=AWS_REGION)


def _parse_s3_uri(uri: str):
    """Return (bucket, prefix) from an s3:// URI."""
    parsed = urlparse(uri)
    bucket = parsed.netloc
    prefix = parsed.path.lstrip('/')
    return bucket, prefix


@st.cache_data(ttl=120, show_spinner="Loading prompt logs from S3…")
def list_log_files(s3_uri: str, start_date=None, end_date=None, max_keys=None):
    """List JSON log files under the given S3 URI, optionally filtered by date.

    Filters by the embedded timestamp in the filename when available
    (e.g. ``…_GenerateAssistantResponse_202604171000_xxx.json.gz``),
    falling back to S3 LastModified otherwise.
    """
    bucket, base_prefix = _parse_s3_uri(s3_uri)
    s3 = _get_s3_client()
    files = []

    paginator = s3.get_paginator('list_objects_v2')
    page_config = {}
    if max_keys:
        page_config['MaxItems'] = max_keys
    pages = paginator.paginate(Bucket=bucket, Prefix=base_prefix,
                               **({"PaginationConfig": page_config} if page_config else {}))
    for page in pages:
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not (key.endswith('.json') or key.endswith('.json.gz')):
                continue

            # Try to extract date from filename timestamp (YYYYMMDDHHmm)
            file_date = _extract_file_date(key)

            if file_date:
                # Use the precise filename-embedded date for filtering
                if start_date and file_date < start_date:
                    continue
                if end_date and file_date > end_date:
                    continue
            else:
                # Fallback to S3 LastModified
                last_mod = obj.get('LastModified')
                if start_date and last_mod and last_mod.date() < start_date:
                    continue
                if end_date and last_mod and last_mod.date() > end_date:
                    continue

            files.append({
                'key': key,
                'size': obj['Size'],
                'last_modified': obj.get('LastModified'),
                'bucket': bucket,
                'file_date': file_date,  # extracted date from filename
                'file_ts': _extract_file_timestamp(key),  # full datetime
            })
    return files


# Regex to match the embedded timestamp in log filenames:
# e.g. 154486397967_GenerateAssistantResponse_202604171000_PxOewWyBjDuZfv2W.json.gz
_FILENAME_TS_RE = re.compile(r'_(\d{12})_[A-Za-z0-9]+\.json(?:\.gz)?$')


def _extract_file_timestamp(key: str):
    """Extract a datetime from the filename timestamp (YYYYMMDDHHmm), or None."""
    filename = key.rsplit('/', 1)[-1]
    m = _FILENAME_TS_RE.search(filename)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), '%Y%m%d%H%M')
    except ValueError:
        return None


def _extract_file_date(key: str):
    """Extract just the date portion from the filename timestamp, or None."""
    ts = _extract_file_timestamp(key)
    return ts.date() if ts else None


@st.cache_data(ttl=300, show_spinner=False)
def read_log_file(bucket: str, key: str):
    """Download and parse a single JSON log file from S3.

    Handles:
    - Standard JSON with a top-level ``records`` array
    - NDJSON (one JSON object per line)
    - Single JSON record without a ``records`` wrapper
    """
    s3 = _get_s3_client()
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
    except Exception:
        return None
    raw = resp['Body'].read()
    if key.endswith('.gz'):
        try:
            raw = gzip.decompress(raw)
        except Exception:
            return None
    body = raw.decode('utf-8').strip()
    if not body:
        return None

    # Try standard JSON first
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            return data
        # If the file is a JSON array, wrap it
        if isinstance(data, list):
            return {'records': data}
        return None
    except json.JSONDecodeError:
        pass

    # Try NDJSON (one JSON object per line)
    records = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                # If each line already has 'records', extend
                if 'records' in obj:
                    records.extend(obj['records'])
                else:
                    records.append(obj)
        except json.JSONDecodeError:
            continue
    if records:
        return {'records': records}
    return None


# ── Record parsing ──────────────────────────────────────────────────

def parse_log_records(files, progress_bar=None):
    """Parse all log files and return two DataFrames: inline_suggestions, chat_logs."""
    inline_rows = []
    chat_rows = []
    total = len(files)

    for idx, f in enumerate(files):
        if progress_bar:
            progress_bar.progress((idx + 1) / total, text=f"Parsing {idx+1}/{total} files…")
        data = read_log_file(f['bucket'], f['key'])
        if not data or 'records' not in data:
            continue
        source_file = f['key']
        file_ts = f.get('file_ts')  # datetime from filename, e.g. 202604171000
        for rec in data['records']:
            # ── Inline suggestion ──
            if 'generateCompletionsEventRequest' in rec:
                req = rec['generateCompletionsEventRequest']
                resp = rec.get('generateCompletionsEventResponse', {})
                inline_rows.append({
                    'source_file': source_file,
                    'type': 'inline_suggestion',
                    'userId': req.get('userId', ''),
                    'timestamp': req.get('timeStamp', ''),
                    'fileName': req.get('fileName', ''),
                    'leftContext': req.get('leftContext', ''),
                    'rightContext': req.get('rightContext', ''),
                    'customizationArn': req.get('customizationArn'),
                    'completions': resp.get('completions', []),
                    'requestId': resp.get('requestId', ''),
                })
            # ── Chat conversation ──
            if 'generateAssistantResponseEventRequest' in rec:
                req = rec['generateAssistantResponseEventRequest']
                resp = rec.get('generateAssistantResponseEventResponse', {})
                meta = resp.get('messageMetadata', {})
                # Try multiple locations for conversationId:
                # 1. response messageMetadata (original)
                # 2. request-level conversationId
                # 3. record-level conversationId
                conv_id = (
                    meta.get('conversationId')
                    or req.get('conversationId')
                    or rec.get('conversationId')
                    or ''
                )
                chat_rows.append({
                    'source_file': source_file,
                    'source_file_ts': file_ts,  # hour-level ts from filename
                    'type': 'chat',
                    'userId': req.get('userId', ''),
                    'timestamp': req.get('timeStamp', ''),
                    'prompt': req.get('prompt', ''),
                    'chatTriggerType': req.get('chatTriggerType', ''),
                    'customizationArn': req.get('customizationArn'),
                    'assistantResponse': resp.get('assistantResponse', ''),
                    'followupPrompts': resp.get('followupPrompts', ''),
                    'conversationId': conv_id,
                    'utteranceId': meta.get('utteranceId', ''),
                    'codeReferenceEvents': resp.get('codeReferenceEvents', []),
                    'supplementaryWebLinks': resp.get('supplementaryWebLinksEvent', []),
                    'requestId': resp.get('requestId', ''),
                })

    df_inline = pd.DataFrame(inline_rows) if inline_rows else pd.DataFrame()
    df_chat = pd.DataFrame(chat_rows) if chat_rows else pd.DataFrame()

    # Parse timestamps
    for df in [df_inline, df_chat]:
        if not df.empty and 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
            df.sort_values('timestamp', ascending=False, inplace=True)

    # ── Session splitting fallback ──
    # If all chat messages share a single conversationId (or all are empty),
    # split them into separate sessions using:
    #   - Different source log file (each file covers ~1 hour)
    #   - Time gap > 30 min between consecutive messages
    #   - Different user
    if not df_chat.empty:
        unique_ids = df_chat['conversationId'].replace('', pd.NA).dropna().unique()
        needs_splitting = (len(unique_ids) <= 1)

        if needs_splitting and len(df_chat) > 1:
            df_chat = df_chat.sort_values('timestamp').reset_index(drop=True)
            session_gap = pd.Timedelta(minutes=30)
            session_ids = []
            current_session = 0
            prev_ts = None
            prev_user = None
            prev_source = None

            for _, row in df_chat.iterrows():
                ts = row['timestamp']
                user = row['userId']
                source = row.get('source_file', '')
                new_session = False

                if prev_ts is not None:
                    # Different source file = different hourly log batch
                    if source != prev_source:
                        new_session = True
                    # Time gap > 30 min
                    elif pd.notna(ts) and pd.notna(prev_ts) and (ts - prev_ts) > session_gap:
                        new_session = True
                    # Different user
                    elif user != prev_user:
                        new_session = True

                if new_session:
                    current_session += 1

                prev_ts = ts
                prev_user = user
                prev_source = source
                session_ids.append(current_session)

            # Build readable session IDs using the first timestamp of each session
            df_chat['_session_num'] = session_ids
            session_start_ts = df_chat.groupby('_session_num')['timestamp'].min()
            df_chat['conversationId'] = df_chat['_session_num'].map(
                lambda s: f"session-{session_start_ts[s].strftime('%Y%m%d-%H%M')}"
                if pd.notna(session_start_ts[s]) else f"session-{s}"
            )
            df_chat.drop(columns=['_session_num'], inplace=True)
            df_chat.sort_values('timestamp', ascending=False, inplace=True)

    return df_inline, df_chat



# ── Rendering helpers ───────────────────────────────────────────────

def _truncate(text, max_len=200):
    if not text:
        return ''
    text = str(text)
    return text[:max_len] + '…' if len(text) > max_len else text


def _render_chat_bubble(role, content, theme_colors):
    """Render a chat message bubble."""
    if role == 'user':
        bg = theme_colors.get('accent', '#4361ee') + '22'
        border_color = theme_colors.get('accent', '#4361ee')
        label = '👤 User'
    else:
        bg = theme_colors.get('secondary_bg', '#f8f9fa')
        border_color = '#06d6a0'
        label = '🤖 Kiro'
    st.markdown(f"""
    <div style="background:{bg}; border-left:4px solid {border_color};
                padding:12px 16px; border-radius:8px; margin:8px 0;
                color:{theme_colors.get('text','#1f2937')};">
        <div style="font-weight:600; font-size:0.85rem; margin-bottom:6px; opacity:0.7;">{label}</div>
        <div style="white-space:pre-wrap; font-size:0.95rem;">{content}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_code_block(code, filename='', theme_colors=None):
    """Render a code snippet block."""
    tc = theme_colors or {}
    bg = tc.get('secondary_bg', '#f8f9fa')
    header = f'<div style="font-size:0.8rem;opacity:0.6;margin-bottom:4px;">📄 {filename}</div>' if filename else ''
    st.markdown(f"""
    <div style="background:{bg}; padding:12px 16px; border-radius:8px; margin:8px 0;
                border:1px solid {tc.get('border','#e5e7eb')};">
        {header}
        <pre style="margin:0; white-space:pre-wrap; font-size:0.85rem;
                    color:{tc.get('text','#1f2937')}; font-family:monospace;">{code}</pre>
    </div>
    """, unsafe_allow_html=True)


# ── Main page renderer ─────────────────────────────────────────────

def render_prompt_logging_page(apply_chart_theme_fn, chart_colors, theme_colors, get_username_fn=None):
    """Render the full Prompt Logging page inside the Streamlit app."""

    st.header("📝 Prompt Logging")
    st.caption("Browse and search Kiro prompt logs — inline suggestions and chat conversations")

    if not PROMPT_LOG_S3_URI:
        st.warning(
            "⚠️ Prompt log S3 URI not configured. "
            "Set `PROMPT_LOG_S3_URI` in your `.env` file "
            "(e.g. `s3://my-bucket/kiro-prompt-logs/`)."
        )
        st.info(
            "📖 To enable prompt logging, follow the guide: "
            "[Kiro Docs — Logging user prompts]"
            "(https://kiro.dev/docs/enterprise/monitor-and-track/prompt-logging/)"
        )
        return

    # ── Filters ──
    st.markdown("#### 🔍 Log Filters")
    fc1, fc2, fc3 = st.columns([2, 2, 3])
    with fc1:
        log_start = st.date_input("From", value=datetime.utcnow().date() - timedelta(days=7),
                                  key='pl_start')
    with fc2:
        log_end = st.date_input("To", value=datetime.utcnow().date(), key='pl_end')
    with fc3:
        search_query = st.text_input("🔎 Search prompts / responses / filenames",
                                     key='pl_search',
                                     placeholder="Type keywords to filter…")

    # ── Load files ──
    with st.spinner("Listing log files…"):
        files = list_log_files(PROMPT_LOG_S3_URI, start_date=log_start, end_date=log_end)

    if not files:
        st.info(f"No log files found for {log_start} — {log_end}.")
        with st.expander("🔧 Debug Info", expanded=True):
            bucket, prefix = _parse_s3_uri(PROMPT_LOG_S3_URI)
            st.markdown(f"- **S3 URI:** `{PROMPT_LOG_S3_URI}`")
            st.markdown(f"- **Bucket:** `{bucket}`")
            st.markdown(f"- **Prefix:** `{prefix}`")
            st.markdown(f"- **Date range:** `{log_start}` — `{log_end}`")
            # Try listing without date filter to see if any files exist at all
            try:
                s3 = _get_s3_client()
                resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=5)
                sample_keys = [obj['Key'] for obj in resp.get('Contents', [])]
                if sample_keys:
                    st.markdown("**Sample objects under prefix:**")
                    for k in sample_keys:
                        st.markdown(f"  - `{k}`")
                    st.warning("Files exist in S3 but were filtered out by the date range. "
                               "Try expanding the date range.")
                else:
                    st.error("No objects found under this S3 prefix. "
                             "Check that the URI is correct and the app has `s3:ListBucket` + `s3:GetObject` permissions.")
            except Exception as e:
                st.error(f"Error accessing S3: {e}")
        return

    st.markdown(f"Found **{len(files)}** log files")

    # ── Parse ──
    progress = st.progress(0, text="Parsing log files…")
    df_inline, df_chat = parse_log_records(files, progress_bar=progress)
    progress.empty()

    total_inline = len(df_inline)
    total_chat = len(df_chat)

    # Show debug info if no records were parsed despite having files
    if total_inline == 0 and total_chat == 0 and len(files) > 0:
        with st.expander("🔧 Debug: Files found but no records parsed", expanded=True):
            st.warning(f"{len(files)} log files were found but 0 records were parsed. "
                       "Sampling the first file to diagnose…")
            sample = files[0]
            st.markdown(f"- **Key:** `{sample['key']}`")
            st.markdown(f"- **Size:** {sample['size']} bytes")
            try:
                data = read_log_file(sample['bucket'], sample['key'])
                if data is None:
                    st.error("File could not be parsed as JSON. The file may be corrupted or in an unexpected format.")
                elif 'records' not in data:
                    st.error(f"JSON parsed but no `records` key found. Top-level keys: `{list(data.keys())}`")
                    st.json(data)
                else:
                    st.success(f"JSON parsed OK — {len(data['records'])} record(s)")
                    rec = data['records'][0] if data['records'] else {}
                    st.markdown(f"First record keys: `{list(rec.keys())}`")
                    st.json(rec)
            except Exception as e:
                st.error(f"Error reading sample file: {e}")

    # ── Summary metrics ──
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Log Files", len(files))
    with m2:
        st.metric("Inline Suggestions", total_inline)
    with m3:
        st.metric("Chat Messages", total_chat)
    with m4:
        unique_users = set()
        if not df_inline.empty:
            unique_users.update(df_inline['userId'].unique())
        if not df_chat.empty:
            unique_users.update(df_chat['userId'].unique())
        st.metric("Unique Users", len(unique_users))

    st.markdown("---")

    # ── Tab navigation ──
    tab_chat, tab_inline, tab_timeline = st.tabs([
        "💬 Chat Conversations", "⚡ Inline Suggestions", "📊 Activity Timeline"
    ])

    # ══════════════════════════════════════════════════════════════
    # TAB 1: Chat Conversations — session tree view
    # ══════════════════════════════════════════════════════════════
    with tab_chat:
        _render_chat_tab(df_chat, search_query, apply_chart_theme_fn,
                         chart_colors, theme_colors, get_username_fn)

    # ══════════════════════════════════════════════════════════════
    # TAB 2: Inline Suggestions
    # ══════════════════════════════════════════════════════════════
    with tab_inline:
        _render_inline_tab(df_inline, search_query, apply_chart_theme_fn,
                           chart_colors, theme_colors, get_username_fn)

    # ══════════════════════════════════════════════════════════════
    # TAB 3: Activity Timeline
    # ══════════════════════════════════════════════════════════════
    with tab_timeline:
        _render_timeline_tab(df_inline, df_chat, apply_chart_theme_fn,
                             chart_colors, theme_colors)



# ── Chat tab ────────────────────────────────────────────────────────

def _render_chat_tab(df_chat, search_query, apply_chart_theme_fn,
                     chart_colors, theme_colors, get_username_fn):
    if df_chat.empty:
        st.info("No chat log records found in the selected date range.")
        return

    df = df_chat.copy()

    # Apply search filter
    if search_query:
        mask = (
            df['prompt'].str.contains(search_query, case=False, na=False) |
            df['assistantResponse'].str.contains(search_query, case=False, na=False) |
            df['conversationId'].str.contains(search_query, case=False, na=False) |
            df['userId'].str.contains(search_query, case=False, na=False)
        )
        df = df[mask]
        if df.empty:
            st.warning(f"No chat records match '{search_query}'")
            return

    # ── Sidebar filters ──
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        users = ['All'] + sorted(df['userId'].dropna().unique().tolist())
        sel_user = st.selectbox("User", users, key='chat_user_filter')
    with fc2:
        triggers = ['All'] + sorted(df['chatTriggerType'].dropna().unique().tolist())
        sel_trigger = st.selectbox("Trigger Type", triggers, key='chat_trigger_filter')
    with fc3:
        st.metric("Conversations", df['conversationId'].nunique())

    if sel_user != 'All':
        df = df[df['userId'] == sel_user]
    if sel_trigger != 'All':
        df = df[df['chatTriggerType'] == sel_trigger]

    st.markdown("---")

    # ── Session tree view ──
    st.subheader("🗂️ Conversations by Session")
    st.caption("Messages grouped by conversationId — expand to see the full dialogue")

    # Group by conversationId
    conversations = {}
    for _, row in df.iterrows():
        cid = row['conversationId'] or 'unknown'
        if cid not in conversations:
            conversations[cid] = []
        conversations[cid].append(row)

    # Sort conversations by most recent message
    sorted_convos = sorted(conversations.items(),
                           key=lambda x: x[1][0]['timestamp'] if pd.notna(x[1][0]['timestamp']) else pd.Timestamp.min,
                           reverse=True)

    # Pagination
    PAGE_SIZE = 10
    total_convos = len(sorted_convos)
    total_pages = max(1, (total_convos + PAGE_SIZE - 1) // PAGE_SIZE)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1,
                           key='chat_page') - 1
    start_idx = page * PAGE_SIZE
    page_convos = sorted_convos[start_idx:start_idx + PAGE_SIZE]

    st.caption(f"Showing {start_idx+1}–{min(start_idx+PAGE_SIZE, total_convos)} of {total_convos} conversations")

    for cid, messages in page_convos:
        # Sort messages within conversation by timestamp ascending
        messages_sorted = sorted(messages, key=lambda m: m['timestamp'] if pd.notna(m['timestamp']) else pd.Timestamp.min)
        first_ts = messages_sorted[0]['timestamp']
        last_ts = messages_sorted[-1]['timestamp']
        user_id = messages_sorted[0]['userId']
        display_user = get_username_fn(user_id) if get_username_fn else user_id
        ts_str = first_ts.strftime('%Y-%m-%d %H:%M') if pd.notna(first_ts) else '?'
        first_prompt = _truncate(messages_sorted[0].get('prompt', ''), 80)

        label = f"💬 {ts_str} — {display_user} — {len(messages_sorted)} msgs — {first_prompt}"

        with st.expander(label, expanded=False):
            # Session metadata
            meta_c1, meta_c2, meta_c3 = st.columns(3)
            with meta_c1:
                st.markdown(f"**Conversation ID:** `{cid}`")
            with meta_c2:
                st.markdown(f"**User:** {display_user}")
            with meta_c3:
                duration = ''
                if pd.notna(first_ts) and pd.notna(last_ts) and len(messages_sorted) > 1:
                    delta = last_ts - first_ts
                    duration = f"{delta.total_seconds()/60:.1f} min"
                st.markdown(f"**Duration:** {duration or 'single message'}")

            st.markdown("---")

            # Render each message pair
            for msg in messages_sorted:
                trigger_badge = ''
                if msg.get('chatTriggerType') == 'INLINE_CHAT':
                    trigger_badge = ' 🔤 `INLINE_CHAT`'
                elif msg.get('chatTriggerType') == 'MANUAL':
                    trigger_badge = ' ✋ `MANUAL`'

                ts_label = msg['timestamp'].strftime('%H:%M:%S') if pd.notna(msg['timestamp']) else ''
                st.markdown(f"<div style='font-size:0.75rem;opacity:0.5;'>{ts_label}{trigger_badge}</div>",
                            unsafe_allow_html=True)

                # User prompt
                _render_chat_bubble('user', msg.get('prompt', ''), theme_colors)

                # Kiro response
                response = msg.get('assistantResponse', '')
                if response:
                    _render_chat_bubble('assistant', response, theme_colors)

                # Follow-up prompts
                followups = msg.get('followupPrompts', '')
                if followups:
                    st.markdown(f"<div style='font-size:0.8rem;opacity:0.6;margin:4px 0;'>"
                                f"💡 Suggested follow-up: <em>{_truncate(followups, 150)}</em></div>",
                                unsafe_allow_html=True)

                # Web links
                links = msg.get('supplementaryWebLinks', [])
                if links:
                    with st.popover("🔗 Reference Links"):
                        for link in links:
                            st.markdown(f"- [{link.get('title','')}]({link.get('uri','')})")
                            if link.get('snippet'):
                                st.caption(link['snippet'])

                st.markdown("<hr style='margin:8px 0;opacity:0.15;'>", unsafe_allow_html=True)



# ── Inline suggestions tab ──────────────────────────────────────────

def _render_inline_tab(df_inline, search_query, apply_chart_theme_fn,
                       chart_colors, theme_colors, get_username_fn):
    if df_inline.empty:
        st.info("No inline suggestion records found in the selected date range.")
        return

    df = df_inline.copy()

    # Apply search filter
    if search_query:
        mask = (
            df['fileName'].str.contains(search_query, case=False, na=False) |
            df['leftContext'].str.contains(search_query, case=False, na=False) |
            df['userId'].str.contains(search_query, case=False, na=False) |
            df['completions'].astype(str).str.contains(search_query, case=False, na=False)
        )
        df = df[mask]
        if df.empty:
            st.warning(f"No inline suggestion records match '{search_query}'")
            return

    # Filters
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        users = ['All'] + sorted(df['userId'].dropna().unique().tolist())
        sel_user = st.selectbox("User", users, key='inline_user_filter')
    with fc2:
        fnames = ['All'] + sorted(df['fileName'].dropna().unique().tolist())
        sel_file = st.selectbox("File Name", fnames, key='inline_file_filter')
    with fc3:
        st.metric("Total Suggestions", len(df))

    if sel_user != 'All':
        df = df[df['userId'] == sel_user]
    if sel_file != 'All':
        df = df[df['fileName'] == sel_file]

    st.markdown("---")

    # ── Top files chart ──
    st.subheader("📁 Suggestions by File")
    file_counts = df['fileName'].value_counts().head(15).reset_index()
    file_counts.columns = ['fileName', 'count']
    fig_files = px.bar(file_counts, x='count', y='fileName', orientation='h',
                       title='Top 15 Files by Inline Suggestions',
                       color='count', color_continuous_scale='Blues',
                       labels={'count': 'Suggestions', 'fileName': 'File'})
    fig_files.update_traces(marker_line_width=0)
    fig_files.update_layout(yaxis={'categoryorder': 'total ascending'},
                            coloraxis_showscale=False, height=400)
    apply_chart_theme_fn(fig_files)
    st.plotly_chart(fig_files, use_container_width=True)

    st.markdown("---")

    # ── Suggestion list ──
    st.subheader("⚡ Inline Suggestion Records")

    PAGE_SIZE = 20
    total_recs = len(df)
    total_pages = max(1, (total_recs + PAGE_SIZE - 1) // PAGE_SIZE)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1,
                           key='inline_page') - 1
    page_df = df.iloc[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    st.caption(f"Showing {page*PAGE_SIZE+1}–{min((page+1)*PAGE_SIZE, total_recs)} of {total_recs} records")

    for _, row in page_df.iterrows():
        ts_str = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['timestamp']) else '?'
        user_id = row['userId']
        display_user = get_username_fn(user_id) if get_username_fn else user_id
        fname = row.get('fileName', '')
        completions = row.get('completions', [])
        completion_text = completions[0] if completions else ''

        label = f"⚡ {ts_str} — {display_user} — 📄 {fname}"

        with st.expander(label, expanded=False):
            mc1, mc2 = st.columns(2)
            with mc1:
                st.markdown(f"**User:** {display_user}")
                st.markdown(f"**File:** `{fname}`")
            with mc2:
                st.markdown(f"**Request ID:** `{row.get('requestId','')}`")
                st.markdown(f"**Time:** {ts_str}")

            # Context
            left_ctx = row.get('leftContext', '')
            right_ctx = row.get('rightContext', '')
            if left_ctx:
                st.markdown("**Code before cursor (leftContext):**")
                _render_code_block(_truncate(left_ctx, 500), fname, theme_colors)
            if right_ctx:
                st.markdown("**Code after cursor (rightContext):**")
                _render_code_block(_truncate(right_ctx, 500), fname, theme_colors)

            # Completion
            if completion_text:
                st.markdown("**✅ Accepted suggestion:**")
                st.code(completion_text, language=_guess_language(fname))



def _guess_language(filename):
    """Guess code language from filename extension for syntax highlighting."""
    ext_map = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.tsx': 'typescript', '.jsx': 'javascript', '.java': 'java',
        '.go': 'go', '.rs': 'rust', '.rb': 'ruby', '.cs': 'csharp',
        '.cpp': 'cpp', '.c': 'c', '.html': 'html', '.css': 'css',
        '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml',
        '.sh': 'bash', '.sql': 'sql', '.tf': 'hcl',
    }
    if not filename:
        return ''
    for ext, lang in ext_map.items():
        if filename.endswith(ext):
            return lang
    return ''


# ── Timeline tab ────────────────────────────────────────────────────

def _render_timeline_tab(df_inline, df_chat, apply_chart_theme_fn,
                         chart_colors, theme_colors):
    """Render combined activity timeline charts."""

    has_inline = not df_inline.empty
    has_chat = not df_chat.empty

    if not has_inline and not has_chat:
        st.info("No log data available for timeline.")
        return

    # Build unified daily counts
    rows = []
    if has_inline:
        df_i = df_inline.copy()
        df_i['date'] = df_i['timestamp'].dt.date
        daily_i = df_i.groupby('date').size().reset_index(name='count')
        daily_i['type'] = 'Inline Suggestion'
        rows.append(daily_i)
    if has_chat:
        df_c = df_chat.copy()
        df_c['date'] = df_c['timestamp'].dt.date
        daily_c = df_c.groupby('date').size().reset_index(name='count')
        daily_c['type'] = 'Chat Message'
        rows.append(daily_c)

    df_timeline = pd.concat(rows, ignore_index=True)
    df_timeline['date'] = pd.to_datetime(df_timeline['date'])

    # ── Daily activity chart ──
    st.subheader("📈 Daily Prompt Activity")
    fig_daily = px.line(df_timeline, x='date', y='count', color='type',
                        title='Daily Prompt Log Activity', markers=True,
                        labels={'count': 'Records', 'date': 'Date', 'type': 'Type'},
                        color_discrete_sequence=['#4361ee', '#f72585'])
    fig_daily.update_traces(line=dict(width=2.5), marker=dict(size=5))
    apply_chart_theme_fn(fig_daily)
    st.plotly_chart(fig_daily, use_container_width=True)

    # ── Hourly heatmap ──
    st.subheader("🕐 Activity by Hour of Day")
    all_records = []
    if has_inline:
        tmp = df_inline[['timestamp']].copy()
        tmp['type'] = 'Inline'
        all_records.append(tmp)
    if has_chat:
        tmp = df_chat[['timestamp']].copy()
        tmp['type'] = 'Chat'
        all_records.append(tmp)

    df_all = pd.concat(all_records, ignore_index=True)
    df_all['hour'] = df_all['timestamp'].dt.hour
    df_all['day_of_week'] = df_all['timestamp'].dt.day_name()

    heatmap_data = df_all.groupby(['day_of_week', 'hour']).size().reset_index(name='count')
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    heatmap_pivot = heatmap_data.pivot_table(index='day_of_week', columns='hour',
                                              values='count', fill_value=0)
    # Reindex to ensure all days/hours present
    heatmap_pivot = heatmap_pivot.reindex(day_order, fill_value=0)
    all_hours = list(range(24))
    for h in all_hours:
        if h not in heatmap_pivot.columns:
            heatmap_pivot[h] = 0
    heatmap_pivot = heatmap_pivot[sorted(heatmap_pivot.columns)]

    fig_heat = go.Figure(data=go.Heatmap(
        z=heatmap_pivot.values,
        x=[f"{h:02d}:00" for h in heatmap_pivot.columns],
        y=heatmap_pivot.index.tolist(),
        colorscale='Purples',
        hovertemplate='%{y} %{x}<br>Records: %{z}<extra></extra>'
    ))
    fig_heat.update_layout(title='Prompt Activity Heatmap (Day × Hour)',
                           xaxis_title='Hour (UTC)', yaxis_title='',
                           height=350)
    apply_chart_theme_fn(fig_heat)
    st.plotly_chart(fig_heat, use_container_width=True)

    # ── Per-user breakdown ──
    st.subheader("👤 Activity by User")
    user_counts = []
    if has_inline:
        uc_i = df_inline.groupby('userId').size().reset_index(name='inline_count')
        user_counts.append(uc_i.rename(columns={'inline_count': 'count'}).assign(type='Inline'))
    if has_chat:
        uc_c = df_chat.groupby('userId').size().reset_index(name='chat_count')
        user_counts.append(uc_c.rename(columns={'chat_count': 'count'}).assign(type='Chat'))

    df_user_activity = pd.concat(user_counts, ignore_index=True)
    df_user_totals = df_user_activity.groupby('userId')['count'].sum().reset_index()
    df_user_totals = df_user_totals.nlargest(15, 'count')

    df_user_top = df_user_activity[df_user_activity['userId'].isin(df_user_totals['userId'])]
    fig_users = px.bar(df_user_top, x='userId', y='count', color='type',
                       title='Top 15 Users by Prompt Log Activity',
                       barmode='stack',
                       color_discrete_sequence=['#4361ee', '#f72585'],
                       labels={'count': 'Records', 'userId': 'User', 'type': 'Type'})
    fig_users.update_traces(marker_line_width=0)
    fig_users.update_layout(xaxis_tickangle=-45)
    apply_chart_theme_fn(fig_users)
    st.plotly_chart(fig_users, use_container_width=True)

    # ── Chat trigger type breakdown ──
    if has_chat:
        st.subheader("🎯 Chat Trigger Types")
        trigger_counts = df_chat['chatTriggerType'].value_counts().reset_index()
        trigger_counts.columns = ['triggerType', 'count']
        fig_trigger = px.pie(trigger_counts, values='count', names='triggerType',
                             title='Chat Messages by Trigger Type', hole=0.45,
                             color_discrete_sequence=['#06d6a0', '#f77f00', '#4361ee'])
        fig_trigger.update_traces(textinfo='label+percent+value', textposition='outside')
        apply_chart_theme_fn(fig_trigger)
        st.plotly_chart(fig_trigger, use_container_width=True)
