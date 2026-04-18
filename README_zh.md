# ⚡ Kiro 用户报告仪表板

[English README](README.md)

基于 Streamlit 的 Kiro 使用指标可视化仪表板。通过 AWS Glue 和 Athena 连接 S3 中的 Kiro 用户报告数据，提供涵盖订阅概览、活跃用户、Credits 消耗、消息、对话、客户端类型、用户参与度等维度的交互式图表。同时包含 Prompt Logging 查看器，可浏览 Kiro 记录的内联建议和聊天对话日志。

![Dashboard](images/dashboard-1.png)
![Dashboard](images/dashboard-2.png)
![Dashboard](images/dashboard-3.png)
![Dashboard](images/dashboard-4.png)
![Dashboard](images/dashboard-5.png)

## 前置条件

- 在 AWS 控制台中启用 Kiro 用户报告数据导出（见下文）
- [Terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli) >= 1.0
- [AWS CLI](https://aws.amazon.com/cli/) 已配置相应凭证
- Python 3.8+

## 启用 Kiro 用户报告

使用本仪表板前，需要在 AWS 控制台中启用用户报告数据导出。进入 Kiro 设置页面，配置用于接收用户报告的 S3 存储桶。

![Kiro Settings](images/kiro-settings.png)

启用后，Kiro 会每天将用户报告 CSV 文件投递到指定的 S3 存储桶。

详细说明请参阅 [Kiro 用户活动文档](https://kiro.dev/docs/enterprise/monitor-and-track/user-activity/)。

## 快速开始

```bash
git clone https://github.com/aws-samples/sample-kiro-user-analytics-dashboard.git
cd sample-kiro-user-analytics-dashboard

# 1. 配置变量
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# 编辑 terraform/terraform.tfvars，填入你的值（见下方"配置"部分）

# 2. 一键部署（基础设施 + 爬虫 + 应用配置）
./deploy.sh

# 3. 启动仪表板
cd app
pip install -r requirements.txt
streamlit run app.py
```

仪表板将在 `http://localhost:8501` 上可用。

## 配置

编辑 `terraform/terraform.tfvars`，填入你的值：

| 变量 | 必填 | 说明 |
|---|---|---|
| `aws_region` | 否（默认 `us-east-1`） | 所有资源所在的 AWS 区域 |
| `aws_account_id` | 是 | 你的 AWS 账户 ID |
| `s3_bucket_name` | 是 | S3 存储桶名称（含前缀，如 `kiro-dev/user`） |
| `glue_database_name` | 否 | Glue 目录数据库名称 |
| `glue_crawler_schedule` | 否 | Glue 爬虫的 Cron 调度表达式 |
| `identity_store_id` | 是 | IAM Identity Center 身份存储 ID（如 `d-1234567890`），用于将用户 ID 解析为用户名 |
| `prompt_log_s3_uri` | 否 | Kiro Prompt 日志存储的 S3 URI（如 `s3://my-bucket/kiro-prompt-logs/`）。留空则禁用 Prompt Logging 查看器。 |
| `project_name` | 否 | 资源命名前缀 |
| `tags` | 否 | 应用到所有资源的标签 |

S3 数据路径自动构建为：
```
s3://{s3_bucket_name}/AWSLogs/{aws_account_id}/KiroLogs/user_report/{aws_region}/
```

> Glue 表名在运行时自动从数据库中发现，无需手动配置。

## `deploy.sh` 做了什么

1. 执行 `terraform init` 和 `terraform apply`，创建以下资源：
   - Glue 数据库、爬虫及 IAM 角色
   - Athena 工作组和结果 S3 存储桶
   - 应用访问的 IAM 策略（包括条件性的 Prompt Log S3 读取权限）
2. 从 Terraform 输出生成 `app/.env`（包含 `PROMPT_LOG_S3_URI`）
3. 启动 Glue 爬虫并等待完成

之后只需启动 Streamlit 应用即可。

## 数据结构

仪表板期望的 Kiro 用户报告 CSV 数据包含以下列：

| 列名 | 类型 | 说明 |
|---|---|---|
| `date` | string | 报告活动日期（YYYY-MM-DD） |
| `userid` | string | 活动所属用户的 ID |
| `client_type` | string | `KIRO_IDE`、`KIRO_CLI` 或 `PLUGIN` |
| `subscription_tier` | string | Kiro 订阅计划（Pro、ProPlus、Power） |
| `profileid` | string | 与用户活动关联的 Profile |
| `total_messages` | integer | 发送给 Kiro 和从 Kiro 接收的消息数（包括 prompt、工具调用、响应） |
| `chat_conversations` | integer | 用户当天的对话数 |
| `credits_used` | double | 当天从用户订阅计划中消耗的 Credits |
| `overage_enabled` | string | 该用户是否启用了超额 |
| `overage_cap` | double | 管理员设置的超额上限（未启用超额时显示计划最大 Credits） |
| `overage_credits_used` | double | 已使用的超额 Credits 总数（如启用超额） |
| `programming_language` | string | 与活动关联的编程语言 |

## 仪表板功能

仪表板包含两个主页面，通过顶部导航下拉菜单切换。

### 📊 使用量仪表板

所有板块共享顶部的全局筛选栏：日期范围选择器 + 编程语言选择器。

- **订阅概览** — 按 Tier（Pro、Pro+、Power）展示 Total / Active / Pending 订阅数，含 Tier 分布饼图和 Active vs Pending 比例饼图
- **活跃用户（DAU / WAU / MAU）** — 日、周、月活跃用户数，支持时间粒度切换，含按客户端类型和订阅 Tier 的细分图表
- **Credits 消耗（日 / 周 / 月）** — Credits 消耗趋势，支持时间粒度切换，含按订阅 Tier 和客户端类型的细分图表
- **总体指标** — 总用户数、总 Profile 数、总消息数、总对话数、总 Credits、总超额 Credits
- **按客户端类型的使用量** — KIRO_CLI vs KIRO_IDE 分布（消息饼图 + Credits 柱状图）
- **Top 10 用户** — 按消息数排名的排行榜
- **每日活动趋势** — 消息、对话、Credits、活跃用户的时间序列（4 面板子图）
- **按客户端类型的每日趋势** — 按客户端的每日消息和对话折线图
- **Credits 分析** — Top 15 用户 Credits 排名、基础 vs 超额 Credits 饼图、按用户按月的 Credits 使用透视表
- **订阅 Tier 分布** — 按 Tier 的用户数和 Credits
- **Profile 分布** — 按 Profile 的用户数（Top 15）、按 Profile 的 Credits（Top 15）、Profile 汇总表
- **用户参与度** — 用户分层（Power / Active / Light / Idle），用户活动时间线（最近活跃天数、总活跃天数图表），可筛选的详细用户表（含 Profile 列）
- **参与度漏斗** — 各参与阶段的转化率

### 📝 Prompt Logging

需要配置 `prompt_log_s3_uri`。直接从 S3 读取 Kiro Prompt 日志 JSON 文件。启用 Prompt Logging 的详细说明请参阅 [Kiro Prompt Logging 文档](https://kiro.dev/docs/enterprise/monitor-and-track/prompt-logging/)。

- **💬 聊天对话** — 按 `conversationId` 分组的会话树视图。每个会话可展开查看完整对话流（用户 prompt + Kiro 响应），含触发类型标签（MANUAL / INLINE_CHAT）、后续建议 prompt 和参考链接。支持按用户和触发类型筛选，分页浏览。
- **⚡ 内联建议** — 浏览已接受的内联代码建议，展示 `leftContext`、`rightContext` 和 `completions`。包含 Top 15 文件统计图表，支持按用户/文件名筛选。
- **📊 活动时间线** — 每日活动趋势（内联 vs 聊天）、按小时热力图（星期 × 小时）、按用户的活动统计、聊天触发类型分布。
- **全局搜索** — 可搜索 prompt、response、conversationId、文件名等字段。

## 项目结构

```
.
├── deploy.sh                        # 一键部署脚本
├── terraform/
│   ├── main.tf                      # Glue、Athena、S3、IAM 资源
│   ├── variables.tf                 # 输入变量
│   ├── outputs.tf                   # 输出（写入 app/.env）
│   └── terraform.tfvars.example     # 配置示例
└── app/
    ├── app.py                       # Streamlit 仪表板（主程序 + 导航）
    ├── prompt_logging.py            # Prompt Logging 查看器模块
    ├── config.py                    # 环境变量加载器
    └── requirements.txt             # Python 依赖
```

## 安全

详见 [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications)。

## 许可证

本项目基于 MIT-0 许可证授权。详见 [LICENSE](LICENSE) 文件。
