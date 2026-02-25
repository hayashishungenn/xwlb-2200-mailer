# xwlb-2200-mailer

每天北京时间 22:00 从 `DuckBurnIncense/xin-wen-lian-bo` 抓取当天 `news/YYYYMMDD.md`，并通过 GitHub Actions 发邮件。

## 功能

- 仅邮件推送，不在本仓库保存或更新文稿文件
- 文稿来源：`https://github.com/DuckBurnIncense/xin-wen-lian-bo`
- 默认定时：每天 22:00（北京时间）
- 仅需 3 个 Secrets：`EMAIL_SENDER`、`EMAIL_PASSWORD`、`EMAIL_RECEIVERS`

## GitHub Actions 配置

工作流文件：`.github/workflows/send-mail.yml`

```yaml
schedule:
  - cron: '0 14 * * *' # UTC 14:00 = 北京时间 22:00
```

## 需要的 Secrets

在仓库 `Settings -> Secrets and variables -> Actions` 添加：

- `EMAIL_SENDER`：发件邮箱地址（如 `yourname@gmail.com` / `xxxx@qq.com`）
- `EMAIL_PASSWORD`：邮箱 SMTP 密码（Gmail App Password / QQ 授权码）
- `EMAIL_RECEIVERS`：收件人列表，多个地址用逗号分隔

示例：

```text
alice@gmail.com,bob@qq.com
```

也支持分号或换行分隔。

## 发件邮箱支持

当前自动识别 SMTP：

- `gmail.com` -> `smtp.gmail.com:465` (SSL)
- `qq.com` -> `smtp.qq.com:465` (SSL)
- `outlook.com` / `hotmail.com` / `live.com` -> `smtp.office365.com:587` (STARTTLS)
- `163.com` -> `smtp.163.com:465` (SSL)
- `126.com` -> `smtp.126.com:465` (SSL)

## 手动测试

在 Actions 页面手动运行 `Send XWLB Daily Mail`。

可选：临时指定日期（格式 `YYYYMMDD`）

- 在 workflow_dispatch 的输入里填 `news_date`
- 或设置环境变量 `NEWS_DATE`
