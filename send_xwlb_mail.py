import os
import smtplib
import ssl
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CN_TZ = timezone(timedelta(hours=8))

RAW_BASE_CANDIDATES = [
    "https://raw.githubusercontent.com/DuckBurnIncense/xin-wen-lian-bo/master/news",
    "https://raw.githubusercontent.com/DuckBurnIncense/xin-wen-lian-bo/main/news",
]

# sender domain -> (smtp_host, smtp_port, use_ssl)
SMTP_BY_DOMAIN = {
    "gmail.com": ("smtp.gmail.com", 465, True),
    "qq.com": ("smtp.qq.com", 465, True),
    "outlook.com": ("smtp.office365.com", 587, False),
    "hotmail.com": ("smtp.office365.com", 587, False),
    "live.com": ("smtp.office365.com", 587, False),
    "163.com": ("smtp.163.com", 465, True),
    "126.com": ("smtp.126.com", 465, True),
}


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required env: {name}")
    return value


def resolve_news_date() -> str:
    override = os.getenv("NEWS_DATE", "").strip()
    if override:
        if len(override) != 8 or not override.isdigit():
            raise ValueError("NEWS_DATE must be YYYYMMDD")
        return override
    return datetime.now(CN_TZ).strftime("%Y%m%d")


def fetch_markdown(news_date: str) -> tuple[str, str]:
    headers = {"User-Agent": "xwlb-2200-mailer/1.0"}
    last_error = None

    for base in RAW_BASE_CANDIDATES:
        url = f"{base}/{news_date}.md"
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                if body.strip():
                    return body, url
                last_error = RuntimeError(f"Empty response body: {url}")
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc

    raise RuntimeError(f"Failed to fetch markdown for {news_date}: {last_error}")


def parse_recipients() -> list[str]:
    raw = require_env("EMAIL_RECEIVERS")
    recipients: list[str] = []

    normalized = raw.replace(";", ",").replace("\n", ",")
    for part in normalized.split(","):
        addr = part.strip()
        if addr:
            recipients.append(addr)

    unique: list[str] = []
    seen = set()
    for addr in recipients:
        if addr not in seen:
            unique.append(addr)
            seen.add(addr)

    if not unique:
        raise ValueError("EMAIL_RECEIVERS does not contain any valid address")
    return unique


def resolve_smtp(sender: str) -> tuple[str, int, bool]:
    if "@" not in sender:
        raise ValueError("EMAIL_SENDER must be a valid email address")
    domain = sender.split("@", 1)[1].lower()

    smtp = SMTP_BY_DOMAIN.get(domain)
    if smtp:
        return smtp

    raise ValueError(
        "Unsupported sender domain: "
        f"{domain}. Supported: {', '.join(sorted(SMTP_BY_DOMAIN.keys()))}"
    )


def send_mail(news_date: str, markdown: str, source_url: str) -> None:
    sender = require_env("EMAIL_SENDER")
    password = require_env("EMAIL_PASSWORD")
    recipients = parse_recipients()

    host, port, secure = resolve_smtp(sender)
    subject = f"新闻联播文字稿 {news_date}"

    text_body = (
        f"新闻日期: {news_date}\n"
        f"来源: {source_url}\n\n"
        f"以下为文稿内容：\n\n{markdown}"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    msg.add_attachment(
        markdown.encode("utf-8"),
        maintype="text",
        subtype="markdown",
        filename=f"{news_date}.md",
    )

    context = ssl.create_default_context()
    if secure:
        with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as server:
            server.login(sender, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender, password)
            server.send_message(msg)

    print(
        "Mail sent: "
        f"date={news_date}, sender={sender}, smtp={host}:{port}, recipients={', '.join(recipients)}"
    )


def main() -> int:
    try:
        news_date = resolve_news_date()
        markdown, source_url = fetch_markdown(news_date)
        send_mail(news_date, markdown, source_url)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
