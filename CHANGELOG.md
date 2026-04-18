# Changelog

All notable changes to this project will be documented in this file.

## [v1.1.0] - 2026-04-18

### Added

- **Global Filters** — Date range picker and programming language selector at the top of the dashboard; all sections apply filters via a shared `WHERE` clause.
- **Subscription Overview (Section 1)** — Total / Active / Pending subscriptions per tier (Pro, Pro+, Power), with pie charts for tier distribution and active vs pending ratio.
- **Active Users DAU / WAU / MAU (Section 2)** — Daily, weekly, and monthly active user counts with time granularity toggle, plus breakdowns by client type and subscription tier.
- **Credits Consumed Daily / Weekly / Monthly (Section 3)** — Credit consumption trends with time granularity toggle, plus breakdowns by subscription tier and client type.
- **Profile Distribution (Section 10b)** — Users per profile (Top 15), credits per profile (Top 15), and profile summary table.
- **Overall Metrics** — Added "Total Profiles" metric card (6-column layout).
- **User Activity Table** — Added "Profile" column showing each user's associated Profile ID.
- **Prompt Logging viewer** (`prompt_logging.py`) — New module for browsing Kiro prompt log JSON files from S3:
  - 💬 Chat Conversations — Session tree view grouped by `conversationId`, expandable full dialogue (user prompt + Kiro response), trigger type badges (MANUAL / INLINE_CHAT), follow-up prompts, reference links, user/trigger filtering, pagination.
  - ⚡ Inline Suggestions — Browse accepted inline code suggestions with `leftContext` / `rightContext` / `completions`, Top 15 files chart, user/file filtering.
  - 📊 Activity Timeline — Daily activity trends (inline vs chat), hourly heatmap (day × hour), per-user activity breakdown, chat trigger type distribution.
  - Global keyword search across prompts, responses, conversation IDs, and file names.
- **Page navigation** — Top-level dropdown to switch between 📊 Usage Dashboard and 📝 Prompt Logging.
- **Terraform** — `prompt_log_s3_uri` variable, output, conditional IAM policy for prompt log S3 read access.
- **deploy.sh** — Reads `prompt_log_s3_uri` from Terraform output and writes it to `app/.env`.

### Changed

- All existing sections (4–12) now respect the global date range and programming language filters.

## [v1.0.0] - 2026-02-17

### Init version from source repo

- **Overall Metrics** — Total users, messages, conversations, credits used, overage credits.
- **Usage by Client Type** — Messages pie chart and credits bar chart for KIRO_IDE / KIRO_CLI / PLUGIN.
- **Top 10 Users** — Leaderboard by messages sent with bar chart.
- **Daily Activity Trends** — 4-panel subplot: messages, conversations, credits, active users over time.
- **Daily Trends by Client Type** — Per-client daily line charts for messages and conversations.
- **Credits Analysis** — Top 15 users by credits, base vs overage pie chart, monthly credit usage pivot table by user.
- **Subscription Tier Breakdown** — Users and credits by subscription tier.
- **User Engagement Analysis** — User segmentation (Power / Active / Light / Idle), user activity timeline with recency and active days charts, filterable detail table.
- **Engagement Funnel** — Conversion rates across engagement stages (All Users → Sent Messages → Had Conversations → Active → Power).
- **Terraform infrastructure** — Glue database, crawler, Athena workgroup, S3 results bucket, IAM roles and policies.
- **One-click deploy** — `deploy.sh` provisions infrastructure, generates `app/.env`, runs Glue crawler.
- **Theme toggle** — Light / dark mode with consistent Plotly chart theming.
- **Username resolution** — IAM Identity Center integration for resolving user IDs to display names.
