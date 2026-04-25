"""
Internationalization (i18n) module for the Kiro Users Report dashboard.

Architecture:
  - Translations are stored as nested dicts: TRANSLATIONS[locale][key] = text
  - The current locale is stored in st.session_state.locale
  - t(key) returns the translated string for the current locale
  - To add a new language, add a new locale dict to TRANSLATIONS

Usage:
  from i18n import t, init_locale, SUPPORTED_LOCALES
  init_locale()          # call once at app start
  t("dashboard_title")   # returns translated string
"""

import streamlit as st

# Supported locales: code -> display name
SUPPORTED_LOCALES = {
    "en": "English",
    "zh": "中文",
}

DEFAULT_LOCALE = "en"


def init_locale():
    """Initialize locale in session state if not already set."""
    if "locale" not in st.session_state:
        st.session_state.locale = DEFAULT_LOCALE


def set_locale(locale_code: str):
    """Set the current locale."""
    if locale_code in SUPPORTED_LOCALES:
        st.session_state.locale = locale_code


def get_locale() -> str:
    """Get the current locale code."""
    return getattr(st.session_state, "locale", DEFAULT_LOCALE)


def t(key: str, **kwargs) -> str:
    """Get translated string for the current locale.

    Supports format placeholders: t("hello", name="World") with "hello": "Hello {name}"
    Falls back to English if key is missing in current locale.
    """
    locale = get_locale()
    text = TRANSLATIONS.get(locale, {}).get(key)
    if text is None:
        text = TRANSLATIONS.get(DEFAULT_LOCALE, {}).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


# ═══════════════════════════════════════════════════════════════════
# Translation dictionaries
# To add a new language, add a new key (e.g. "ja", "ko") with all keys.
# ═══════════════════════════════════════════════════════════════════

TRANSLATIONS = {
    "en": {
        # ── Header ──
        "dashboard_title": "⚡ Kiro Users Report",
        "dashboard_subtitle": "Usage metrics across your organization",
        "navigate": "📂 Navigate",
        "nav_usage": "📊 Usage Dashboard",
        "nav_prompt_log": "📝 Prompt Logging",
        "refresh_data": "🔄 Refresh Data",
        "language": "🌐 Language",

        # ── Filters ──
        "filters": "🔍 Filters",
        "start_date": "Start Date",
        "end_date": "End Date",
        "programming_language": "Programming Language",
        "filter_by_language_help": "Filter metrics by programming language",
        "data_range": "📅 Data range: **{min_date}** to **{max_date}**",

        # ── Metric Definitions ──
        "metric_definitions": "ℹ️ Metric Definitions",
        "metric_definitions_body": """
**Date**: Date of the report activity.

**UserId**: ID of the user for whom the activity is reported.

**Client Type**: KIRO_IDE, KIRO_CLI, or PLUGIN.

**Subscription Tier**: Kiro subscription plan — Pro, ProPlus, Power.

**ProfileId**: Profile associated with the user activity.

**Total Messages**: Number of messages sent to and from Kiro. Includes user prompts, tool calls, and Kiro responses.

**Chat Conversations**: Number of conversations by the user during the day.

**Credits Used**: Credits consumed from the user subscription plan during the day.

**Overage Enabled**: Whether overage is enabled for this user.

**Overage Cap**: Overage limit set by the admin when overage is enabled. If overage is not enabled, shows the maximum credits included for the subscription plan as a preset value.

**Overage Credits Used**: Total number of overage credits used by the user, if overage is enabled.

---

📖 **Learn more about Kiro metrics**: [Kiro Documentation - Monitor and Track](https://kiro.dev/docs/enterprise/monitor-and-track/)
""",

        # ── Section 1: Subscription Overview ──
        "subscription_overview": "📋 Subscription Overview",
        "subscription_overview_caption": "Mirrors the official Kiro console dashboard — subscriptions by tier and status",
        "total_subs_per_tier": "Total Subscriptions per Tier",
        "total_subs_per_tier_caption": "Total subscriptions broken down by tier (Pro, Pro+, Power)",
        "all_tiers": "All Tiers",
        "active_subs_per_tier": "Active Subscriptions per Tier",
        "active_subs_caption": "Users who have started using Kiro (you are being charged)",
        "all_active": "All Active",
        "pending_subs_per_tier": "Pending Subscriptions per Tier",
        "pending_subs_caption": "Users who have not yet started using Kiro (not being charged)",
        "all_pending": "All Pending",
        "pct_of_total": "{pct}% of total",
        "subs_by_tier": "Subscriptions by Tier",
        "active_vs_pending": "Active vs Pending Subscriptions",

        # ── Section 2: Active Users ──
        "active_users_header": "👥 Active Users (DAU / WAU / MAU)",
        "active_users_caption": "Unique users actively utilizing Kiro — daily, weekly, and monthly views with breakdowns",
        "time_granularity": "Time Granularity",
        "daily_dau": "Daily (DAU)",
        "weekly_wau": "Weekly (WAU)",
        "monthly_mau": "Monthly (MAU)",
        "dau_title": "Daily Active Users (DAU)",
        "wau_title": "Weekly Active Users (WAU)",
        "mau_title": "Monthly Active Users (MAU)",
        "active_users_label": "Active Users",
        "date_label": "Date",
        "week_label": "Week",
        "month_label": "Month",
        "by_client_type": "By Client Type",
        "by_subscription_tier": "By Subscription Tier",
        "active_users_by_client": "Active Users by Client Type",
        "active_users_by_tier": "Active Users by Tier",

        # ── Section 3: Credits Consumed ──
        "credits_consumed_header": "💳 Credits Consumed (Daily / Weekly / Monthly)",
        "credits_consumed_caption": "Total Kiro credits consumed with time-based views and breakdowns by tier and client type",
        "daily": "Daily",
        "weekly": "Weekly",
        "monthly": "Monthly",
        "daily_credits_title": "Daily Credits Consumed",
        "weekly_credits_title": "Weekly Credits Consumed",
        "monthly_credits_title": "Monthly Credits Consumed",
        "credits_label": "Credits",
        "credits_by_tier": "Credits by Subscription Tier",
        "credits_by_tier_title": "Credits by Tier",
        "credits_by_client": "Credits by Client Type",
        "credits_by_client_title": "Credits by Client Type",

        # ── Section 4: Overall Metrics ──
        "overall_metrics": "📈 Overall Metrics",
        "total_users": "Total Users",
        "total_users_help": "Unique users who have used Kiro",
        "total_profiles": "Total Profiles",
        "total_profiles_help": "Unique Kiro profiles associated with user activity",
        "total_messages": "Total Messages",
        "total_messages_help": "Total messages sent to Kiro",
        "chat_conversations": "Chat Conversations",
        "chat_conversations_help": "Total chat conversations initiated",
        "credits_used": "Credits Used",
        "credits_used_help": "Total credits consumed across all users and client types",
        "overage_credits": "Overage Credits",
        "overage_credits_help": "Total overage credits consumed",

        # ── Section 5: Usage by Client Type ──
        "usage_by_client": "🖥️ Usage by Client Type",
        "messages_by_client": "Messages by Client Type",
        "credits_used_by_client": "Credits Used by Client Type",

        # ── Section 6: Top 10 Users ──
        "top_users_header": "🏆 Top 10 Users by Messages",
        "leaderboard": "🥇 Leaderboard",
        "messages_sent": "Messages Sent",
        "messages_word": "messages",

        # ── Section 7: Daily Activity Trends ──
        "daily_activity_header": "📅 Daily Activity Trends",
        "total_messages_chart": "Total Messages",
        "chat_conversations_chart": "Chat Conversations",
        "credits_used_chart": "Credits Used",
        "active_users_chart": "Active Users",
        "daily_activity_overview": "Daily Activity Overview",

        # ── Section 8: Daily Trends by Client Type ──
        "daily_trends_client": "📊 Daily Trends by Client Type",
        "daily_messages_by_client": "Daily Messages by Client Type",
        "daily_convos_by_client": "Daily Conversations by Client Type",

        # ── Section 9: Credits Analysis ──
        "credits_analysis": "💰 Credits Analysis",
        "top15_credits": "Top 15 Users by Total Credits",
        "base_vs_overage": "Base vs Overage Credits",
        "base_credits": "Base Credits",
        "credit_usage_by_month": "📅 Credit Usage by User by Month",

        # ── Section 10: Subscription Tier Breakdown ──
        "tier_breakdown": "🎫 Subscription Tier Breakdown",
        "users_by_tier": "Users by Subscription Tier",
        "credits_by_tier_chart": "Credits by Subscription Tier",

        # ── Section 10b: Profile Distribution ──
        "profile_distribution": "🆔 Profile Distribution",
        "profile_distribution_caption": "Kiro profiles associated with user activity — users per profile and activity breakdown",
        "users_per_profile": "Users per Profile (Top 15)",
        "credits_per_profile": "Credits per Profile (Top 15)",
        "profile_summary": "📋 Profile Summary",

        # ── Section 11: User Engagement ──
        "user_engagement": "👥 User Engagement Analysis",
        "user_segmentation": "📊 User Segmentation",
        "user_distribution": "User Distribution by Engagement Level",
        "category_definitions": "Category Definitions",
        "category_power": "🚀 Power Users",
        "category_power_desc": "100+ messages OR 20+ conversations",
        "category_active": "💼 Active Users",
        "category_active_desc": "20+ messages OR 5+ conversations",
        "category_light": "🌱 Light Users",
        "category_light_desc": "At least 1 message sent",
        "category_idle": "😴 Idle Users",
        "category_idle_desc": "No activity recorded",
        "quick_stats": "Quick Stats",
        "users_unit": "users",
        "user_activity_timeline": "📅 User Activity Timeline",
        "days_since_last": "Days Since Last Activity (Top 15 Recent)",
        "total_active_days": "Total Active Days (Top 15)",
        "detailed_user_table": "📋 Detailed User Activity Table",
        "filter_by_category": "Filter by Category",
        "filter_by_recency": "Filter by Recency",
        "all_users": "All Users",
        "active_last_7": "Active (Last 7 days)",
        "recent_last_30": "Recent (Last 30 days)",
        "inactive_30plus": "Inactive (30+ days)",
        "dormant_90plus": "Dormant (90+ days)",
        "sort_by": "Sort by",
        "filtered_users": "Filtered Users",
        "avg_days_since_active": "Avg Days Since Active",
        "avg_active_days": "Avg Active Days",
        "active_last_week": "Active Last Week",

        # ── Section 12: Engagement Funnel ──
        "engagement_funnel": "🔻 User Engagement Funnel",
        "funnel_all_users": "All Users",
        "funnel_sent_messages": "Sent Messages",
        "funnel_had_convos": "Had Conversations",
        "funnel_active_users": "Active Users (20+ msgs)",
        "funnel_power_users": "Power Users (100+ msgs)",
        "funnel_title": "User Engagement Funnel",
        "funnel_metrics": "📊 Funnel Metrics",
        "conversion_rates": "🔄 Conversion Rates",
        "message_activation": "Message Activation",
        "conversation_rate": "Conversation Rate",
        "active_retention": "Active Retention",
        "power_user_growth": "Power User Growth",

        # ── Error ──
        "error_fetching": "Error fetching data: {error}",
        "ensure_info": "Please ensure:",
        "ensure_list": """
- AWS credentials are configured
- Glue crawler has run successfully
- Athena database and table exist
- S3 bucket for Athena results is accessible
""",

        # ── Prompt Logging page ──
        "pl_header": "📝 Prompt Logging",
        "pl_caption": "Browse and search Kiro prompt logs — inline suggestions and chat conversations",
        "pl_not_configured": "⚠️ Prompt log S3 URI not configured. Set `PROMPT_LOG_S3_URI` in your `.env` file (e.g. `s3://my-bucket/kiro-prompt-logs/`).",
        "pl_enable_guide": "📖 To enable prompt logging, follow the guide: [Kiro Docs — Logging user prompts](https://kiro.dev/docs/enterprise/monitor-and-track/prompt-logging/)",
        "pl_filters": "🔍 Log Filters",
        "pl_from": "From",
        "pl_to": "To",
        "pl_search": "🔎 Search prompts / responses / filenames",
        "pl_search_placeholder": "Type keywords to filter…",
        "pl_no_files": "No log files found for {start} — {end}.",
        "pl_debug_info": "🔧 Debug Info",
        "pl_found_files": "Found **{count}** log files",
        "pl_log_files": "Log Files",
        "pl_inline_suggestions": "Inline Suggestions",
        "pl_chat_messages": "Chat Messages",
        "pl_unique_users": "Unique Users",
        "pl_tab_chat": "💬 Chat Conversations",
        "pl_tab_inline": "⚡ Inline Suggestions",
        "pl_tab_ai_coding": "🤖 AI Coding Acceptance",
        "pl_tab_timeline": "📊 Activity Timeline",
        "pl_tab_raw": "📋 Chat Conversations RAW Data",
        "pl_user": "User",
        "pl_trigger_type": "Trigger Type",
        "pl_conversations": "Conversations",
        "pl_model_usage": "🤖 Model Usage",
        "pl_messages_by_model": "Messages by Model",
        "pl_top10_sessions_model": "Top 10 Sessions — Model Breakdown",
        "pl_distinct_models": "Distinct Models",
        "pl_most_used_model": "Most Used Model",
        "pl_auto_mode_pct": "Auto Mode %",
        "pl_conversations_by_session": "🗂️ Conversations by Session",
        "pl_conversations_by_session_caption": "Messages grouped by conversationId — expand to see the full dialogue",
        "pl_page": "Page",
        "pl_showing": "Showing {start}–{end} of {total} conversations",
        "pl_no_chat_records": "No chat log records found in the selected date range.",
        "pl_no_match": "No chat records match '{query}'",
    },

    "zh": {
        # ── Header ──
        "dashboard_title": "⚡ Kiro 用户报告",
        "dashboard_subtitle": "组织内的使用指标",
        "navigate": "📂 导航",
        "nav_usage": "📊 使用仪表板",
        "nav_prompt_log": "📝 提示日志",
        "refresh_data": "🔄 刷新数据",
        "language": "🌐 语言",

        # ── Filters ──
        "filters": "🔍 筛选条件",
        "start_date": "开始日期",
        "end_date": "结束日期",
        "programming_language": "编程语言",
        "filter_by_language_help": "按编程语言筛选指标",
        "data_range": "📅 数据范围：**{min_date}** 至 **{max_date}**",

        # ── Metric Definitions ──
        "metric_definitions": "ℹ️ 指标定义",
        "metric_definitions_body": """
**日期**：报告活动的日期。

**用户ID**：报告活动所属用户的ID。

**客户端类型**：KIRO_IDE、KIRO_CLI 或 PLUGIN。

**订阅层级**：Kiro 订阅计划 — Pro、ProPlus、Power。

**配置文件ID**：与用户活动关联的配置文件。

**总消息数**：发送到 Kiro 和从 Kiro 发出的消息数量。包括用户提示、工具调用和 Kiro 响应。

**聊天会话数**：用户当天的会话数量。

**已用积分**：当天从用户订阅计划中消耗的积分。

**是否启用超额**：该用户是否启用了超额使用。

**超额上限**：启用超额时管理员设置的超额限制。如果未启用超额，则显示订阅计划中包含的最大积分作为预设值。

**已用超额积分**：如果启用了超额，用户使用的超额积分总数。

---

📖 **了解更多 Kiro 指标**：[Kiro 文档 - 监控与追踪](https://kiro.dev/docs/enterprise/monitor-and-track/)
""",

        # ── Section 1: Subscription Overview ──
        "subscription_overview": "📋 订阅概览",
        "subscription_overview_caption": "对应 Kiro 控制台官方仪表板 — 按层级和状态划分的订阅",
        "total_subs_per_tier": "各层级总订阅数",
        "total_subs_per_tier_caption": "按层级（Pro、Pro+、Power）划分的总订阅数",
        "all_tiers": "所有层级",
        "active_subs_per_tier": "各层级活跃订阅数",
        "active_subs_caption": "已开始使用 Kiro 的用户（正在计费）",
        "all_active": "全部活跃",
        "pending_subs_per_tier": "各层级待激活订阅数",
        "pending_subs_caption": "尚未开始使用 Kiro 的用户（未计费）",
        "all_pending": "全部待激活",
        "pct_of_total": "占总数 {pct}%",
        "subs_by_tier": "按层级订阅分布",
        "active_vs_pending": "活跃 vs 待激活订阅",

        # ── Section 2: Active Users ──
        "active_users_header": "👥 活跃用户（DAU / WAU / MAU）",
        "active_users_caption": "正在使用 Kiro 的唯一用户 — 每日、每周和每月视图及细分",
        "time_granularity": "时间粒度",
        "daily_dau": "每日 (DAU)",
        "weekly_wau": "每周 (WAU)",
        "monthly_mau": "每月 (MAU)",
        "dau_title": "每日活跃用户 (DAU)",
        "wau_title": "每周活跃用户 (WAU)",
        "mau_title": "每月活跃用户 (MAU)",
        "active_users_label": "活跃用户",
        "date_label": "日期",
        "week_label": "周",
        "month_label": "月",
        "by_client_type": "按客户端类型",
        "by_subscription_tier": "按订阅层级",
        "active_users_by_client": "按客户端类型的活跃用户",
        "active_users_by_tier": "按层级的活跃用户",

        # ── Section 3: Credits Consumed ──
        "credits_consumed_header": "💳 积分消耗（每日 / 每周 / 每月）",
        "credits_consumed_caption": "Kiro 积分消耗总量，按时间维度查看，并按层级和客户端类型细分",
        "daily": "每日",
        "weekly": "每周",
        "monthly": "每月",
        "daily_credits_title": "每日积分消耗",
        "weekly_credits_title": "每周积分消耗",
        "monthly_credits_title": "每月积分消耗",
        "credits_label": "积分",
        "credits_by_tier": "按订阅层级的积分",
        "credits_by_tier_title": "按层级积分",
        "credits_by_client": "按客户端类型的积分",
        "credits_by_client_title": "按客户端类型积分",

        # ── Section 4: Overall Metrics ──
        "overall_metrics": "📈 总体指标",
        "total_users": "总用户数",
        "total_users_help": "使用过 Kiro 的唯一用户",
        "total_profiles": "总配置文件数",
        "total_profiles_help": "与用户活动关联的唯一 Kiro 配置文件",
        "total_messages": "总消息数",
        "total_messages_help": "发送到 Kiro 的总消息数",
        "chat_conversations": "聊天会话数",
        "chat_conversations_help": "发起的聊天会话总数",
        "credits_used": "已用积分",
        "credits_used_help": "所有用户和客户端类型消耗的总积分",
        "overage_credits": "超额积分",
        "overage_credits_help": "消耗的超额积分总数",

        # ── Section 5: Usage by Client Type ──
        "usage_by_client": "🖥️ 按客户端类型使用情况",
        "messages_by_client": "按客户端类型的消息",
        "credits_used_by_client": "按客户端类型的积分使用",

        # ── Section 6: Top 10 Users ──
        "top_users_header": "🏆 消息数前10用户",
        "leaderboard": "🥇 排行榜",
        "messages_sent": "已发送消息",
        "messages_word": "条消息",

        # ── Section 7: Daily Activity Trends ──
        "daily_activity_header": "📅 每日活动趋势",
        "total_messages_chart": "总消息数",
        "chat_conversations_chart": "聊天会话数",
        "credits_used_chart": "已用积分",
        "active_users_chart": "活跃用户",
        "daily_activity_overview": "每日活动概览",

        # ── Section 8: Daily Trends by Client Type ──
        "daily_trends_client": "📊 按客户端类型的每日趋势",
        "daily_messages_by_client": "按客户端类型的每日消息",
        "daily_convos_by_client": "按客户端类型的每日会话",

        # ── Section 9: Credits Analysis ──
        "credits_analysis": "💰 积分分析",
        "top15_credits": "积分前15用户",
        "base_vs_overage": "基础积分 vs 超额积分",
        "base_credits": "基础积分",
        "credit_usage_by_month": "📅 按用户按月积分使用",

        # ── Section 10: Subscription Tier Breakdown ──
        "tier_breakdown": "🎫 订阅层级细分",
        "users_by_tier": "按订阅层级的用户",
        "credits_by_tier_chart": "按订阅层级的积分",

        # ── Section 10b: Profile Distribution ──
        "profile_distribution": "🆔 配置文件分布",
        "profile_distribution_caption": "与用户活动关联的 Kiro 配置文件 — 每个配置文件的用户数和活动细分",
        "users_per_profile": "每个配置文件的用户数（前15）",
        "credits_per_profile": "每个配置文件的积分（前15）",
        "profile_summary": "📋 配置文件摘要",

        # ── Section 11: User Engagement ──
        "user_engagement": "👥 用户参与度分析",
        "user_segmentation": "📊 用户分层",
        "user_distribution": "按参与度级别的用户分布",
        "category_definitions": "分类定义",
        "category_power": "🚀 重度用户",
        "category_power_desc": "100+ 条消息 或 20+ 次会话",
        "category_active": "💼 活跃用户",
        "category_active_desc": "20+ 条消息 或 5+ 次会话",
        "category_light": "🌱 轻度用户",
        "category_light_desc": "至少发送过1条消息",
        "category_idle": "😴 闲置用户",
        "category_idle_desc": "无活动记录",
        "quick_stats": "快速统计",
        "users_unit": "位用户",
        "user_activity_timeline": "📅 用户活动时间线",
        "days_since_last": "距上次活动天数（最近15位）",
        "total_active_days": "总活跃天数（前15位）",
        "detailed_user_table": "📋 详细用户活动表",
        "filter_by_category": "按分类筛选",
        "filter_by_recency": "按活跃时间筛选",
        "all_users": "所有用户",
        "active_last_7": "活跃（最近7天）",
        "recent_last_30": "近期（最近30天）",
        "inactive_30plus": "不活跃（30天以上）",
        "dormant_90plus": "休眠（90天以上）",
        "sort_by": "排序方式",
        "filtered_users": "筛选后用户数",
        "avg_days_since_active": "平均不活跃天数",
        "avg_active_days": "平均活跃天数",
        "active_last_week": "上周活跃",

        # ── Section 12: Engagement Funnel ──
        "engagement_funnel": "🔻 用户参与漏斗",
        "funnel_all_users": "所有用户",
        "funnel_sent_messages": "发送过消息",
        "funnel_had_convos": "有过会话",
        "funnel_active_users": "活跃用户（20+条消息）",
        "funnel_power_users": "重度用户（100+条消息）",
        "funnel_title": "用户参与漏斗",
        "funnel_metrics": "📊 漏斗指标",
        "conversion_rates": "🔄 转化率",
        "message_activation": "消息激活率",
        "conversation_rate": "会话转化率",
        "active_retention": "活跃留存率",
        "power_user_growth": "重度用户增长率",

        # ── Error ──
        "error_fetching": "获取数据出错：{error}",
        "ensure_info": "请确认：",
        "ensure_list": """
- AWS 凭证已配置
- Glue 爬虫已成功运行
- Athena 数据库和表已存在
- Athena 结果的 S3 存储桶可访问
""",

        # ── Prompt Logging page ──
        "pl_header": "📝 提示日志",
        "pl_caption": "浏览和搜索 Kiro 提示日志 — 内联建议和聊天会话",
        "pl_not_configured": "⚠️ 提示日志 S3 URI 未配置。请在 `.env` 文件中设置 `PROMPT_LOG_S3_URI`（例如 `s3://my-bucket/kiro-prompt-logs/`）。",
        "pl_enable_guide": "📖 要启用提示日志，请参阅指南：[Kiro 文档 — 记录用户提示](https://kiro.dev/docs/enterprise/monitor-and-track/prompt-logging/)",
        "pl_filters": "🔍 日志筛选",
        "pl_from": "从",
        "pl_to": "到",
        "pl_search": "🔎 搜索提示 / 响应 / 文件名",
        "pl_search_placeholder": "输入关键词筛选…",
        "pl_no_files": "在 {start} — {end} 范围内未找到日志文件。",
        "pl_debug_info": "🔧 调试信息",
        "pl_found_files": "找到 **{count}** 个日志文件",
        "pl_log_files": "日志文件",
        "pl_inline_suggestions": "内联建议",
        "pl_chat_messages": "聊天消息",
        "pl_unique_users": "唯一用户",
        "pl_tab_chat": "💬 聊天会话",
        "pl_tab_inline": "⚡ 内联建议",
        "pl_tab_ai_coding": "🤖 AI 编码接受度",
        "pl_tab_timeline": "📊 活动时间线",
        "pl_tab_raw": "📋 聊天会话原始数据",
        "pl_user": "用户",
        "pl_trigger_type": "触发类型",
        "pl_conversations": "会话数",
        "pl_model_usage": "🤖 模型使用情况",
        "pl_messages_by_model": "按模型的消息数",
        "pl_top10_sessions_model": "前10会话 — 模型细分",
        "pl_distinct_models": "不同模型数",
        "pl_most_used_model": "最常用模型",
        "pl_auto_mode_pct": "自动模式占比",
        "pl_conversations_by_session": "🗂️ 按会话分组的对话",
        "pl_conversations_by_session_caption": "按 conversationId 分组的消息 — 展开查看完整对话",
        "pl_page": "页码",
        "pl_showing": "显示第 {start}–{end} 条，共 {total} 个会话",
        "pl_no_chat_records": "在所选日期范围内未找到聊天日志记录。",
        "pl_no_match": "没有匹配 '{query}' 的聊天记录",
    },
}
