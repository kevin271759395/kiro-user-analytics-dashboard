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
### deploy和terraform运行的权限和程序运行的权限说明
下面是 `deploy.sh` 和 Terraform 部署所需的 AWS 权限梳理：

---

#### 一、执行 Terraform 的 IAM 权限（部署者/CI 角色）

Terraform 需要创建和管理以下资源，因此执行 `terraform apply` 的身份需要：

**S3**
- `s3:CreateBucket`, `s3:DeleteBucket`, `s3:PutBucketVersioning`, `s3:PutBucketLifecycleConfiguration`
- `s3:PutEncryptionConfiguration`, `s3:PutBucketPublicAccessBlock`
- `s3:GetBucketPolicy`, `s3:GetBucketVersioning`, `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`
- 作用范围：`{project_name}-athena-results` 桶

**Glue**
- `glue:CreateDatabase`, `glue:DeleteDatabase`, `glue:GetDatabase`
- `glue:CreateCrawler`, `glue:DeleteCrawler`, `glue:GetCrawler`, `glue:UpdateCrawler`
- `glue:StartCrawler`（deploy.sh 中手动触发 crawler）

**Athena**
- `athena:CreateWorkGroup`, `athena:DeleteWorkGroup`, `athena:GetWorkGroup`, `athena:UpdateWorkGroup`

**IAM**
- `iam:CreateRole`, `iam:DeleteRole`, `iam:GetRole`, `iam:PassRole`
- `iam:CreatePolicy`, `iam:DeletePolicy`, `iam:GetPolicy`, `iam:GetPolicyVersion`, `iam:ListPolicyVersions`
- `iam:AttachRolePolicy`, `iam:DetachRolePolicy`
- `iam:PutRolePolicy`, `iam:DeleteRolePolicy`, `iam:GetRolePolicy`
- `iam:CreateInstanceProfile`, `iam:DeleteInstanceProfile`, `iam:AddRoleToInstanceProfile`, `iam:RemoveRoleFromInstanceProfile`, `iam:GetInstanceProfile`
- `iam:CreateUser`, `iam:DeleteUser`, `iam:GetUser`
- `iam:AttachUserPolicy`, `iam:DetachUserPolicy`
- 涉及的资源：`glue-crawler-role`, `app-role`, `app-user`, `app-instance-profile` 以及多个 policy

**Terraform State（如果用远程 backend）**
- 对应 S3 + DynamoDB 的读写权限（本项目未配置远程 backend，可忽略）

---

#### 二、deploy.sh 额外需要的权限

除了上面 Terraform 的权限外，deploy.sh 还直接调用了 AWS CLI：

- `glue:StartCrawler` — 启动 Glue Crawler
- `glue:GetCrawler` — 轮询 Crawler 状态直到完成

---

#### 汇总部署执行所需的权限（如果在Ec2上）
需要的完整权限策略：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Full",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:ListBucket",
        "s3:GetBucketPolicy",
        "s3:PutBucketPolicy",
        "s3:DeleteBucketPolicy",
        "s3:GetBucketAcl",
        "s3:PutBucketAcl",
        "s3:GetBucketCORS",
        "s3:PutBucketCORS",
        "s3:GetBucketVersioning",
        "s3:PutBucketVersioning",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetEncryptionConfiguration",
        "s3:PutEncryptionConfiguration",
        "s3:GetLifecycleConfiguration",
        "s3:PutLifecycleConfiguration",
        "s3:GetBucketTagging",
        "s3:PutBucketTagging",
        "s3:GetBucketLogging",
        "s3:PutBucketLogging",
        "s3:GetBucketObjectLockConfiguration",
        "s3:GetBucketRequestPayment",
        "s3:GetBucketWebsite",
        "s3:GetAccelerateConfiguration",
        "s3:GetReplicationConfiguration",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListAllMyBuckets",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::kiro-user-report-dashboard-*",
        "arn:aws:s3:::kiro-user-report-dashboard-*/*"
      ]
    },
    {
      "Sid": "IAMRolesAndPolicies",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies",
        "iam:ListInstanceProfilesForRole",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:GetRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PassRole",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:CreateInstanceProfile",
        "iam:DeleteInstanceProfile",
        "iam:GetInstanceProfile",
        "iam:AddRoleToInstanceProfile",
        "iam:RemoveRoleFromInstanceProfile",
        "iam:CreatePolicy",
        "iam:DeletePolicy",
        "iam:GetPolicy",
        "iam:GetPolicyVersion",
        "iam:ListPolicyVersions",
        "iam:CreatePolicyVersion",
        "iam:DeletePolicyVersion",
        "iam:TagPolicy",
        "iam:UntagPolicy",
        "iam:CreateUser",
        "iam:DeleteUser",
        "iam:GetUser",
        "iam:TagUser",
        "iam:UntagUser",
        "iam:AttachUserPolicy",
        "iam:DetachUserPolicy",
        "iam:ListAttachedUserPolicies",
        "iam:ListUserPolicies"
      ],
      "Resource": [
        "arn:aws:iam::154486397967:role/kiro-user-report-dashboard-*",
        "arn:aws:iam::154486397967:policy/kiro-user-report-dashboard-*",
        "arn:aws:iam::154486397967:instance-profile/kiro-user-report-dashboard-*",
        "arn:aws:iam::154486397967:user/kiro-user-report-dashboard-*"
      ]
    },
    {
      "Sid": "GlueCrawlerAndCatalog",
      "Effect": "Allow",
      "Action": [
        "glue:CreateDatabase",
        "glue:DeleteDatabase",
        "glue:GetDatabase",
        "glue:UpdateDatabase",
        "glue:CreateCrawler",
        "glue:DeleteCrawler",
        "glue:GetCrawler",
        "glue:UpdateCrawler",
        "glue:StartCrawler",
        "glue:StopCrawler",
        "glue:TagResource",
        "glue:UntagResource",
        "glue:GetTags"
      ],
      "Resource": [
        "arn:aws:glue:*:154486397967:catalog",
        "arn:aws:glue:*:154486397967:database/kiro-user-report*",
        "arn:aws:glue:*:154486397967:crawler/kiro-user-report-dashboard-*"
      ]
    },
    {
      "Sid": "AthenaWorkgroup",
      "Effect": "Allow",
      "Action": [
        "athena:CreateWorkGroup",
        "athena:DeleteWorkGroup",
        "athena:GetWorkGroup",
        "athena:UpdateWorkGroup",
        "athena:TagResource",
        "athena:UntagResource",
        "athena:ListTagsForResource"
      ],
      "Resource": "arn:aws:athena:*:154486397967:workgroup/kiro-user-report-dashboard-*"
    }
  ]
}
```

把这个策略交给你的 AWS 管理员，让他们附加到EC2的角色（例如`kiro-reports-role`） 上。

---
#### 三、应用运行时权限（app 角色/用户）

Terraform 已经通过 `athena_access_policy` 和 `prompt_log_s3_policy` 定义了应用所需的权限，梳理如下：

**Athena 查询**
- `athena:StartQueryExecution`, `athena:GetQueryExecution`, `athena:GetQueryResults`, `athena:StopQueryExecution`, `athena:GetWorkGroup`

**Glue Catalog（读取表结构）**
- `glue:GetDatabase`, `glue:GetTable`, `glue:GetTables`, `glue:GetPartitions`

**S3 数据源（读取 Kiro 日志数据）**
- `s3:GetObject`, `s3:ListBucket` — 对 `{s3_bucket_name}/AWSLogs/{account_id}/KiroLogs/...`

**S3 Athena 结果桶（读写）**
- `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` — 对 `{project_name}-athena-results`

**S3 Prompt Log（可选，仅当配置了 `prompt_log_s3_uri`）**
- `s3:GetObject`, `s3:ListBucket` — 对 prompt log 桶和前缀

**Identity Store（用户名解析）**
- `identitystore:DescribeUser` — 代码中调用了 `describe_user`，但 Terraform 中未为此创建 policy，需要手动补充或确保运行身份已有此权限

---

#### 四、总结

| 角色 | 关键权限范围 |
|---|---|
| 部署者（Terraform + deploy.sh） | S3、Glue、Athena、IAM 的完整 CRUD |
| 应用运行时 | Athena 查询、Glue 读取、S3 数据读取、S3 结果读写、IdentityStore 读取、（可选）Prompt Log S3 读取 |

值得注意的是，`identitystore:DescribeUser` 权限在 Terraform 中没有被声明到任何 policy 里，但 `app.py` 运行时会调用它来解析用户名。如果应用运行时遇到权限不足的问题，这是一个需要补充的点。

### 快速部署
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
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

仪表板将在 `http://localhost:8501` 上可用。

### 长期持久运行
最简单的方式是用 `nohup` 或 `screen`/`tmux`，这样断开 SSH 后程序继续运行。

**方案 A：nohup（最简单）**

```bash
cd /home/ec2-user/kiro-user-analytics-dashboard/app
source venv/bin/activate
nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 > streamlit.log 2>&1 &
```

查看日志：`tail -f streamlit.log`
停止程序：`kill $(pgrep -f "streamlit run")`

**方案 B：tmux（推荐，方便随时回来查看）**

```bash
# 创建一个命名会话
tmux new -s dashboard

# 在 tmux 里运行
cd /home/ec2-user/kiro-user-analytics-dashboard/app
source venv/bin/activate
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

然后按 `Ctrl+B` 再按 `D` 脱离会话。下次 SSH 回来用 `tmux attach -t dashboard` 重新接入。

**方案 C：systemd（生产环境推荐，开机自启）**

```bash
sudo tee /etc/systemd/system/streamlit-dashboard.service << 'EOF'
[Unit]
Description=Kiro User Report Dashboard
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/kiro-user-analytics-dashboard/app
ExecStart=/home/ec2-user/kiro-user-analytics-dashboard/app/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=5
EnvironmentFile=/home/ec2-user/kiro-user-analytics-dashboard/app/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable streamlit-dashboard
sudo systemctl start streamlit-dashboard
```

查看状态：`sudo systemctl status streamlit-dashboard`
查看日志：`sudo journalctl -u streamlit-dashboard -f`

别忘了在 EC2 安全组里开放 8501 端口，否则外部访问不了。

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
