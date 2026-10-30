# GitHub Action 自动阅读配置指南

## 📋 概述

使用 GitHub Action 可以让你的微信读书自动阅读程序在云端自动运行，无需本地电脑24小时开机。本指南将详细介绍如何配置和使用 GitHub Action 进行自动阅读。

## 🚀 快速开始

### 步骤 1: Fork 项目

1. 访问 [WeRead Bot 项目主页](https://github.com/funnyzak/weread-bot)
2. 点击右上角的 **Fork** 按钮
3. 选择你的 GitHub 账户，完成 Fork

### 步骤 2: 配置 Secrets

Fork 完成后，需要在你的仓库中配置必要的环境变量：

1. 进入你 Fork 的仓库
2. 点击 **Settings** 选项卡
3. 在左侧菜单中选择 **Secrets and variables** → **Actions**
4. 点击 **New repository secret** 添加以下配置：

#### 必需配置

| Secret 名称 | 说明 | 获取方法 |
|------------|------|----------|
| `WEREAD_CURL_STRING` | 微信读书的 cURL 请求字符串 | 本地执行 `python weread-bot.py --login --login-output ./scan.txt` 扫码生成，或参考主文档"获取 cURL 字符串"章节抓包 |
| `GH_PAT` | 用于回写 Cookie 和记录每日计划的 Personal Access Token | 见下方"每日多次阅读与 Cookie 自动回写" |

#### 每日多次阅读与 Cookie 自动回写

workflow 每小时触发三次，由 `plan` 任务按北京时间决定本次是否阅读、读多久：

- 每天随机确定目标阅读时长（默认 240-360 分钟，即 4-6 小时），每段阅读只在阅读窗口（默认 07:30-23:00）内开始；
- 一次触发可以安排多段阅读：每段 60-120 分钟（`SESSION_MINUTES`），段与段之间休息 `MIN_GAP_MINUTES` 的 1-2 倍（默认 45-90 分钟），整个任务不超过 330 分钟；每天通常 3-5 段，最多 `MAX_DAILY_RUNS` 段；
- 每段开始前再随机等待 1-10 分钟；
- 计入的时长取自成功上报的 `rt` 之和（服务端计入的阅读时长），不含开始前等待和休息。`plan` 用最近几次"计入时长 / 阅读段时长"的实测比例换算需要读多久；
- GitHub 经常延迟或丢弃定时触发（实测每天可能只有约 6 次）。`plan` 会记录最近的触发时间估算实际间隔：触发频繁时每次安排一段并随机决定是否阅读；触发稀疏时每次触发都读，一次安排多段，距上次结束不足间隔或在窗口开始前 3 小时内的触发会在任务内等待后再读；
- 不阅读的触发约 10 秒结束。

每次运行开始时会刷新 Cookie。刷新后的 Cookie 只在内存中，如果不写回 Secret，几天后 Secret 中的旧 Cookie 就会失效。配置 `GH_PAT` 后，workflow 会：

1. 用 `--save-curl` 把刷新后的 Cookie 和阅读位置写到临时文件（不进入日志和 artifact）；
2. 用 `gh secret set` 回写 `WEREAD_CURL_STRING`；
3. 在仓库变量 `READ_PLAN` 中记录当天的目标时长、已读时长、阅读段数、计入比例、上次结束时间和最近的触发时间。

创建 `GH_PAT`：GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token：

- Repository access 选 **Only select repositories**，只选你 Fork 的仓库；
- Repository permissions：**Secrets** 设为 Read and write，**Variables** 设为 Read and write；
- 生成后保存为仓库 Secret `GH_PAT`。

未配置 `GH_PAT` 时，workflow 改为按概率触发（不记录次数），Cookie 也不会回写。

在 **Secrets and variables → Actions → Variables** 中可以配置（均为可选）：

| Variable 名称 | 说明 | 默认值 |
|--------------|------|------|
| `WEREAD_BOOKS` | 书籍列表，JSON，结构同 `reading.books`。扫码生成的 cURL 不含书籍，必须配置 | 无 |
| `DAILY_MINUTES` | 每天阅读总时长范围（分钟） | `240-360` |
| `SESSION_MINUTES` | 单段阅读时长范围（分钟） | `60-120` |
| `MAX_DAILY_RUNS` | 每天最多阅读段数 | `8` |
| `READING_WINDOW` | 允许开始阅读的北京时间段 | `07:30-23:00` |
| `MIN_GAP_MINUTES` | 两次阅读的最小间隔（分钟） | `45` |
| `READ_PLAN` | 由 workflow 自动维护，无需手动创建 | - |

`WEREAD_BOOKS` 示例（书籍和章节 ID 取自网页阅读页 URL 或抓包 cURL 中的 `b`、`c` 字段）：

```json
[{"name": "明朝那些事", "book_id": "a57325c05c8ed3a57224187", "chapters": [{"chapter_id": "a87322c014a87ff679a21ea", "chapter_index": 4}]}]
```

Cookie 回写后，cURL 中会带上最近一次的阅读位置，后续运行从该位置继续。

#### 多用户

- 将多个 cURL 片段写入同一个 `WEREAD_CURL_STRING`，**片段之间至少插入两个空行**，程序会自动拆分为多个用户。
- 通过 `MAX_CONCURRENT_USERS` 控制并发执行账号数量，默认 1 表示顺序执行，建议从 1 开始再逐步提高。
- 单个片段只绑定一个账号的 cURL，确保不同用户分段清晰，避免粘连。

示例（Secret 内容，注意两空行分隔）：

```
curl 'https://weread.qq.com/web/book/read' -H 'cookie: wr_skey=user1; ...' --data-raw '{...}'


curl 'https://weread.qq.com/web/book/read' -H 'cookie: wr_skey=user2; ...' --data-raw '{...}'
```

#### 可选运行配置

| Secret 名称 | 说明 | 默认值 |
|------------|------|------|
| `MAX_CONCURRENT_USERS` | 多用户并发数量（>=1） | 1 |
| `MAX_CONSECUTIVE_FAILURES` | 单个用户连续阅读失败上限，达到后结束该会话 | 5 |
| `HACK_COOKIE_REFRESH_QL` | Cookie 刷新首选 `ql` 值，失败时自动尝试其他兼容形式 | false |
| `NOTIFICATION_ONLY_ON_FAILURE` | 仅失败通知开关（true/false），覆盖 workflow 运行参数 | false |
| `HISTORY_ENABLED` | 是否启用执行历史持久化 | true |
| `HISTORY_FILE` | 执行历史输出路径 | logs/run-history.json |
| `HISTORY_MAX_ENTRIES` | 最近执行记录保留条数 | 50 |
| `HISTORY_PERSIST_RUNTIME_ERROR` | 运行时异常是否写入失败历史 | true |

#### 可选通知配置

根据你使用的通知方式，添加相应的 Secret：

**PushPlus 推送加**
| Secret 名称 | 说明 |
|------------|------|
| `PUSHPLUS_TOKEN` | PushPlus 的推送令牌 |

**Telegram 通知**
| Secret 名称 | 说明 |
|------------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID |

**WxPusher 通知**
| Secret 名称 | 说明 |
|------------|------|
| `WXPUSHER_SPT` | WxPusher 的 SPT |

**Bark 通知**
| Secret 名称 | 说明 |
|------------|------|
| `BARK_SERVER` | Bark 服务器地址 |
| `BARK_DEVICE_KEY` | Bark 设备密钥 |
| `BARK_SOUND` | Bark 推送声音（可选） |

**Ntfy 通知**
| Secret 名称 | 说明 |
|------------|------|
| `NTFY_SERVER` | Ntfy 服务器地址 |
| `NTFY_TOPIC` | Ntfy 主题 |
| `NTFY_TOKEN` | Ntfy 访问令牌（可选） |

**Apprise 通用通知**
| Secret 名称 | 说明 |
|------------|------|
| `APPRISE_URL` | Apprise 通知 URL |

> **获取方式**：支持 Discord、Slack、Email 等数十种服务，详见 [Apprise 文档](https://github.com/caronc/apprise)

**飞书通知**
| Secret 名称 | 说明 |
|------------|------|
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook URL |
| `FEISHU_MSG_TYPE` | 消息类型：text/rich_text（可选） |

> **获取方式**：
> 1. 在飞书桌面版群聊中添加机器人
> 2. 选择"自定义机器人"
> 3. 获取 Webhook URL
> 4. 示例：`https://open.feishu.cn/open-apis/bot/v2/hook/your_webhook_token`

**企业微信通知**
| Secret 名称 | 说明 |
|------------|------|
| `WEWORK_WEBHOOK_URL` | 企业微信机器人 Webhook URL |
| `WEWORK_MSG_TYPE` | 消息类型：text/markdown/news（可选） |

> **获取方式**：
> 1. 在企业微信群聊中添加机器人
> 2. 选择"自定义机器人"
> 3. 获取 Webhook URL
> 4. 示例：`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_webhook_key`

**钉钉通知**
| Secret 名称 | 说明 |
|------------|------|
| `DINGTALK_WEBHOOK_URL` | 钉钉机器人 Webhook URL |
| `DINGTALK_MSG_TYPE` | 消息类型：text/markdown/link（可选） |

> **获取方式**：
> 1. 在钉钉群聊中添加机器人
> 2. 选择"自定义机器人"
> 3. 获取 Webhook URL
> 4. 示例：`https://oapi.dingtalk.com/robot/send?access_token=your_access_token`

**GOTify 通知**
| Secret 名称 | 说明 |
|------------|------|
| `GOTIFY_SERVER` | GOTify 服务器地址 |
| `GOTIFY_TOKEN` | GOTify 访问令牌 |
| `GOTIFY_PRIORITY` | 消息优先级（可选，默认 5） |
| `GOTIFY_TITLE` | 消息标题（可选） |

> **获取方式**：
> 1. 访问你的 GOTify 服务器，登录后进入“应用”页面，创建新应用以获取访问令牌（Token）。
> 2. GOTify 服务器地址通常为你的部署地址，如 `https://gotify.example.com`。
> 3. 优先级和标题可根据需要自定义，留空则使用默认值。


**代理配置（可选）**
| Secret 名称 | 说明 |
|------------|------|
| `HTTP_PROXY` | HTTP 代理地址 |
| `HTTPS_PROXY` | HTTPS 代理地址 |

**Hack 配置（可选）**
| Secret 名称 | 说明 | 默认值 |
|------------|------|--------|
| `HACK_COOKIE_REFRESH_QL` | Cookie 刷新时首选的 `ql` 值 | `false` |

> **Hack 配置说明：**
> - `HACK_COOKIE_REFRESH_QL`: 控制 Cookie 刷新请求首选的 `ql` 参数值，作为全局默认值
>   - `false` (默认): 优先使用 `"ql": false`
>   - `true`: 优先使用 `"ql": true`
> - 首选形式失败时，程序会自动尝试相反值和省略 `ql`
> - 三种形式均失败时，需要重新获取登录 cURL
> - GitHub Actions Secrets 只能设置全局默认值；如果多用户需要不同取值，请改用配置文件中的 `curl_config.users[].cookie_refresh_ql`

### 步骤 3: 启用 GitHub Actions

1. 在你的仓库中点击 **Actions** 选项卡
2. 如果看到"Actions are disabled"提示，点击 **I understand my workflows, go ahead and enable them**
3. 找到 **Auto Reading Bot** workflow

### 步骤 4: 运行 Action

#### 手动触发

1. 在 **Actions** 页面，选择 **Auto Reading Bot** workflow
2. 点击 **Run workflow** 按钮
3. 配置运行参数：
   - **阅读时长**: 格式为 `60-90`，表示随机 60-90 分钟；留空时使用 `plan` 按当日剩余时长计算的值
   - **阅读模式**: 选择阅读策略
   - **启用通知**: 是否发送完成通知
   - **启用执行历史**: 是否在运行后保存最近执行记录
   - **历史保留条数**: 最近执行记录最多保留多少条

手动触发不受每日计划限制，会立即阅读，并计入当天完成次数。

#### 定时触发

workflow 已启用每小时三次的定时触发（`7,27,47 * * * *`），实际是否阅读、读多久由 `plan` 任务决定，见上方"每日多次阅读与 Cookie 自动回写"。不阅读的触发约 10 秒结束。`plan` 任务每次都会调用接口保持定时任务启用，避免仓库 60 天无活动后被 GitHub 停用。

## ⚙️ 配置参数说明

### 阅读模式

| 模式 | 说明 |
|------|------|
| `smart_random` | 智能随机模式，优先继续当前书籍和章节 |
| `sequential` | 顺序阅读模式，按书籍顺序阅读 |
| `pure_random` | 纯随机模式，完全随机选择书籍和章节 |

### 运行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `target_duration` | 留空 | 手动触发时可直接填写；留空则使用 `plan` 按当日剩余时长计算的值 |
| `reading_mode` | `smart_random` | 阅读模式 |
| `notify_enabled` | `true` | 是否启用通知 |
| `notify_only_on_failure` | `false` | 仅失败时发送通知 |
| `history_enabled` | `true` | 是否启用执行历史持久化 |
| `history_max_entries` | `50` | 执行历史最多保留多少条 |

当在 GitHub Actions 中手动触发 `auto-reading.yml` 时，可以直接在界面填写 `target_duration` 覆盖本次阅读时长；若留空，则使用 `plan` 按当日剩余时长计算的值。定时运行的时长由 `DAILY_MINUTES`、`SESSION_MINUTES` 控制，不再读取 `TARGET_DURATION`。

同时，你也可以直接在界面勾选以上两个通知开关：`notify_enabled` 控制是否生成阅读成功摘要，`notify_only_on_failure` 则对应 `config.yaml` 中的 `notification.only_on_failure`，会自动关闭 `session_success` 和 `multi_user_summary` 两类成功事件，仅保留失败/异常通知。

如果希望默认采用“仅失败通知”策略（无需每次触发都勾选），可以设置仓库 Secret `NOTIFICATION_ONLY_ON_FAILURE=true`。该 Secret 会通过环境变量覆盖运行参数，在 workflow 中自动传递给 `NOTIFICATION_ONLY_ON_FAILURE`。

执行历史同样支持“仓库 Secret 默认值 + 手动触发临时覆盖”的组合方式。默认情况下，workflow 会把 `logs/run-history.json` 与 `logs/weread.log` 一起上传为 artifact；如果你通过 Secret 自定义了 `HISTORY_FILE`，建议同步调整 workflow 中的 artifact 路径。

## 🎯 高级配置

### 自定义配置文件

如需更详细的配置，可以修改 workflow 文件中的 config.yaml 内容：

```yaml
human_simulation:
  enabled: true
  reading_speed_variation: true  # 每次会话随机整体速度，并缓慢漂移
  break_probability: 0.03        # 每页休息概率（两次休息至少间隔 8 页和 10 分钟，读满 30 分钟后概率翻倍，不再继续增加）
  break_duration: "30-240"       # 休息时长范围，多数偏短
  skim_probability: 0.08         # 每页开始连续快速翻 2-4 页的概率
  long_read_probability: 0.06    # 每页停留较久的概率
  rotate_user_agent: false       # 是否轮换 User-Agent

network:
  timeout: 30                    # 请求超时时间
  retry_times: 3                 # 重试次数
  retry_delay: "5-15"           # 重试延迟范围
  rate_limit: 10                # 速率限制（请求/秒）

history:
  enabled: true                  # 是否记录最近执行历史
  file: "logs/run-history.json"  # 历史文件路径
  max_entries: 50                # 最多保留最近 50 条
  persist_runtime_error: true    # 运行时异常也落失败记录
```

## 📊 运行监控

### 查看运行日志与历史

1. 在 **Actions** 页面选择具体的运行记录
2. 点击 **plan** job 查看本次是否阅读及原因；阅读时点击 **read** job
3. 展开 **Run WeRead Bot** 步骤查看详细日志
4. 在页面底部 **Artifacts** 区域下载 `weread-runtime-<run_id>`，查看 `logs/weread.log` 和 `logs/run-history.json`

### 运行状态

- ✅ **成功**: 阅读任务正常完成
- ❌ **失败**: 检查错误日志，通常是配置问题
- ⏸️ **取消**: 手动取消或超时（read 任务 355 分钟）
- ⏭️ **read 任务跳过**: 本次触发按计划不阅读，属于正常情况

程序退出码如下：

- `0`：所有用户成功。
- `1`：配置错误、运行失败或部分用户失败。
- `130`：手动取消或系统中断。

scheduled和daemon模式会为每次会话单独写历史。单次失败不会结束常驻进程。

## ❓ 常见问题

### Q: Action 运行失败怎么办？

A: 检查以下几点：
1. `WEREAD_CURL_STRING` 是否正确配置
2. cURL 字符串是否已过期（建议定期更新）
3. 查看运行日志中的具体错误信息

### Q: 如何更新 cURL 字符串？

A: 
1. 本地执行 `python weread-bot.py --login --login-output ./scan.txt` 扫码，或重新从网页版抓包
2. 在仓库 Settings → Secrets 中更新 `WEREAD_CURL_STRING`
3. 配置了 `GH_PAT` 时，之后每次运行会自动回写刷新后的 Cookie，通常无需再手动更新

### Q: 可以同时运行多个 Action 吗？

A: 不建议同时运行多个相同账户的 Action，可能导致账户异常。如需多账户，请使用不同的配置。

### Q: GitHub Actions 有使用限制吗？

A: 公开仓库使用标准 runner 不计分钟数；私有仓库的免费额度为每月 2000 分钟。按默认每天阅读 4-6 小时计算，每月约 8000-11000 分钟，私有仓库会超出额度，请保持 Fork 为公开仓库。公开仓库的运行日志和 artifact 任何人可见，日志已脱敏，但书名和阅读时间可见。

### Q: 如何调整每天的运行次数和时间？

A: 修改仓库 Variables `DAILY_MINUTES`、`SESSION_MINUTES`、`MAX_DAILY_RUNS`、`READING_WINDOW`、`MIN_GAP_MINUTES`，无需改 workflow。`plan` 任务日志会显示当日已读分钟数、估算的触发间隔和本次决定；也可以在 Variables 中查看 `READ_PLAN`。

### Q: GitHub Actions 里的执行历史保存在哪里？

A: 当前 workflow 会在任务结束后上传 artifact，默认包含 `logs/weread.log` 和 `logs/run-history.json`。进入单次运行详情页后，在底部 **Artifacts** 区域下载即可。

### Q: 遇到 Cookie 刷新失败怎么办？

A: 程序会按首选值、相反值和省略 `ql` 的顺序自动尝试。三种形式均失败时：
1. 检查网络连接和 Action 日志中的认证错误
2. 本地扫码（`--login`）或重新抓包获取最新 cURL
3. 更新 `WEREAD_CURL_STRING` 后重新运行 Action
4. 未配置 `GH_PAT` 时 Cookie 不会回写，Secret 中的 Cookie 通常几天后失效

### Q: 如何判断是否需要调整 Hack 配置？

A: 查看运行日志中的错误信息：
- 搜索关键词：`cookie`、`refresh`、`ql`、`认证`
- 日志会显示每次尝试采用的 `ql` 形式
- 三种形式均未返回 `wr_skey` 时，优先更新该账号的 cURL
- 如果看到 401/403 认证错误，也可能是此配置问题

## 🔒 安全提示

1. **不要在公开仓库中暴露** cURL 字符串或其他敏感信息
2. **定期更新** cURL 字符串以保持有效性
3. **合理设置**运行频率，避免被检测为异常行为
4. **及时关注**账户状态，如有异常立即停止使用

---

如有问题或建议，欢迎在 [Issues](../../issues) 中反馈。
