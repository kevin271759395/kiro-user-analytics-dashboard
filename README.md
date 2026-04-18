# ⚡ Kiro Users Report

[中文版 README](README_zh.md)

A Streamlit dashboard for visualizing Kiro usage metrics. Connects to your Kiro user report data in S3 via AWS Glue and Athena, and presents interactive charts covering subscriptions, active users, credits, messages, conversations, client types, user engagement, and more. Also includes a Prompt Logging viewer for browsing inline suggestions and chat conversations logged by Kiro.

![Dashboard](images/dashboard-1.png)
![Dashboard](images/dashboard-2.png)
![Dashboard](images/dashboard-3.png)
![Dashboard](images/dashboard-4.png)
![Dashboard](images/dashboard-5.png)

## Prerequisites

- Kiro user report data export enabled in the AWS console (see below)
- [Terraform](https://www.terraform.io/downloads) >= 1.0
- [AWS CLI](https://aws.amazon.com/cli/) configured with appropriate credentials
- Python 3.8+

## Enable Kiro User Reports

Before using this dashboard, you need to enable user report data export in the AWS console. Navigate to the Kiro settings page and configure the S3 bucket where user reports will be delivered.

![Kiro Settings](images/kiro-settings.png)

Once enabled, Kiro will deliver daily user report CSV files to your specified S3 bucket.

For detailed instructions, see the [Kiro User Activity documentation](https://kiro.dev/docs/enterprise/monitor-and-track/user-activity/).

## Quick Start

```bash
git clone https://github.com/aws-samples/sample-kiro-user-analytics-dashboard.git
cd sample-kiro-user-analytics-dashboard

# 1. Configure your variables
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# Edit terraform/terraform.tfvars with your values (see Configuration below)

# 2. Deploy everything (infra + crawler + app config)
./deploy.sh

# 3. Start the dashboard
cd app
pip install -r requirements.txt
streamlit run app.py
```

The dashboard will be available at `http://localhost:8501`.

## Configuration

Edit `terraform/terraform.tfvars` with your values:

| Variable | Required | Description |
|---|---|---|
| `aws_region` | No (default: `us-east-1`) | AWS region for all resources |
| `aws_account_id` | Yes | Your AWS account ID |
| `s3_bucket_name` | Yes | S3 bucket name including prefix (e.g. `kiro-dev/user`) |
| `glue_database_name` | No | Glue catalog database name |
| `glue_crawler_schedule` | No | Cron schedule for the Glue crawler |
| `identity_store_id` | Yes | IAM Identity Center Identity Store ID (e.g. `d-1234567890`) for resolving user IDs to usernames |
| `prompt_log_s3_uri` | No | S3 URI where Kiro prompt logs are stored (e.g. `s3://my-bucket/kiro-prompt-logs/`). Leave empty to disable the Prompt Logging viewer. |
| `project_name` | No | Prefix for resource naming |
| `tags` | No | Tags applied to all resources |

The S3 data path is constructed automatically as:
```
s3://{s3_bucket_name}/AWSLogs/{aws_account_id}/KiroLogs/user_report/{aws_region}/
```

> The Glue table name is auto-discovered from the database at runtime — no need to configure it manually.

## What `deploy.sh` Does

1. Runs `terraform init` and `terraform apply` to provision:
   - Glue database, crawler, and IAM role
   - Athena workgroup and results S3 bucket
   - IAM policies for app access (including conditional prompt log S3 read access)
2. Generates `app/.env` from Terraform outputs (including `PROMPT_LOG_S3_URI`)
3. Starts the Glue crawler and waits for it to finish

After that, you just start the Streamlit app.

## Data Schema

The dashboard expects Kiro user report CSV data with these columns:

| Column | Type | Description |
|---|---|---|
| `date` | string | Date of the report activity (YYYY-MM-DD) |
| `userid` | string | ID of the user for whom the activity is reported |
| `client_type` | string | `KIRO_IDE`, `KIRO_CLI`, or `PLUGIN` |
| `subscription_tier` | string | Kiro subscription plan (Pro, ProPlus, Power) |
| `profileid` | string | Profile associated with the user activity |
| `total_messages` | integer | Messages sent to and from Kiro (prompts, tool calls, responses) |
| `chat_conversations` | integer | Number of conversations by the user during the day |
| `credits_used` | double | Credits consumed from the user subscription plan during the day |
| `overage_enabled` | string | Whether overage is enabled for this user |
| `overage_cap` | double | Overage limit set by admin (or max credits for plan if overage not enabled) |
| `overage_credits_used` | double | Total overage credits used, if overage is enabled |
| `programming_language` | string | Programming language associated with the activity |

## Dashboard Sections

The dashboard has two main pages, selectable from the top navigation dropdown.

### 📊 Usage Dashboard

All sections share a global filter bar at the top: date range picker + programming language selector.

- **Subscription Overview** — Total / Active / Pending subscriptions per tier (Pro, Pro+, Power), with pie charts for tier distribution and active vs pending ratio
- **Active Users (DAU / WAU / MAU)** — Daily, weekly, and monthly active user counts with time granularity toggle, plus breakdowns by client type and subscription tier
- **Credits Consumed (Daily / Weekly / Monthly)** — Credit consumption trends with time granularity toggle, plus breakdowns by subscription tier and client type
- **Overall Metrics** — Total users, profiles, messages, conversations, credits, and overage credits
- **Usage by Client Type** — KIRO_CLI vs KIRO_IDE breakdown (messages pie chart + credits bar chart)
- **Top 10 Users** — Leaderboard by messages sent
- **Daily Activity Trends** — Messages, conversations, credits, and active users over time (4-panel subplot)
- **Daily Trends by Client Type** — Per-client daily line charts for messages and conversations
- **Credits Analysis** — Top 15 users by credits, base vs overage split pie chart, monthly credit usage pivot table by user
- **Subscription Tier Breakdown** — Users and credits by tier
- **Profile Distribution** — Users per profile (Top 15), credits per profile (Top 15), and profile summary table
- **User Engagement** — Segmentation (Power / Active / Light / Idle users), user activity timeline with recency and active days charts, filterable detail table with profile column
- **Engagement Funnel** — Conversion rates across engagement stages

### 📝 Prompt Logging

Requires `prompt_log_s3_uri` to be configured. Reads Kiro prompt log JSON files directly from S3. For details on enabling prompt logging, see the [Kiro Prompt Logging documentation](https://kiro.dev/docs/enterprise/monitor-and-track/prompt-logging/).

- **💬 Chat Conversations** — Session tree view grouped by `conversationId`. Each session expands to show the full dialogue (user prompts + Kiro responses), with trigger type badges (MANUAL / INLINE_CHAT), follow-up prompts, and reference links. Supports filtering by user and trigger type, with pagination.
- **⚡ Inline Suggestions** — Browse accepted inline code suggestions with `leftContext`, `rightContext`, and `completions`. Includes a Top 15 files chart and filtering by user / file name.
- **📊 Activity Timeline** — Daily activity trends (inline vs chat), hourly heatmap (day × hour), per-user activity breakdown, and chat trigger type distribution.
- **Global search** across prompts, responses, conversation IDs, and file names.

## Project Structure

```
.
├── deploy.sh                        # One-click deploy script
├── terraform/
│   ├── main.tf                      # Glue, Athena, S3, IAM resources
│   ├── variables.tf                 # Input variables
│   ├── outputs.tf                   # Outputs (fed into app/.env)
│   └── terraform.tfvars.example     # Example configuration
└── app/
    ├── app.py                       # Streamlit dashboard (main + navigation)
    ├── prompt_logging.py            # Prompt Logging viewer module
    ├── config.py                    # Environment variable loader
    └── requirements.txt             # Python dependencies
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.
