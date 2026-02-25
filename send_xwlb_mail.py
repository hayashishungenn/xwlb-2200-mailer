import html
import os
import re
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

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


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


def convert_inline_markdown(text: str) -> str:
    placeholders: list[str] = []

    def replace_link(match: re.Match[str]) -> str:
        label = html.escape(match.group(1), quote=False)
        url = html.escape(match.group(2), quote=True)
        placeholders.append(f'<a href="{url}">{label}</a>')
        return f"@@LINK{len(placeholders) - 1}@@"

    text_with_links = MARKDOWN_LINK_RE.sub(replace_link, text)
    escaped = html.escape(text_with_links, quote=False)

    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)

    for i, rendered_link in enumerate(placeholders):
        escaped = escaped.replace(f"@@LINK{i}@@", rendered_link)

    return escaped


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html_parts: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            close_list()
            continue

        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            close_list()
            level = len(heading_match.group(1))
            content = convert_inline_markdown(heading_match.group(2).strip())
            html_parts.append(f"<h{level}>{content}</h{level}>")
            continue

        if stripped.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item = convert_inline_markdown(stripped[2:].strip())
            html_parts.append(f"<li>{item}</li>")
            continue

        if re.fullmatch(r"-{3,}", stripped):
            close_list()
            html_parts.append("<hr>")
            continue

        # Keep embedded HTML from source markdown.
        if stripped.startswith("<") and ">" in stripped:
            close_list()
            html_parts.append(stripped)
            continue

        close_list()
        html_parts.append(f"<p>{convert_inline_markdown(stripped)}</p>")

    close_list()
    return "\n".join(html_parts)


def build_html_email(news_date: str, source_url: str, markdown: str) -> str:
    rendered = markdown_to_html(markdown)
    source_url_escaped = html.escape(source_url, quote=True)

    return f"""<!doctype html>
<html lang=\"zh-CN\">
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  </head>
  <body style=\"margin:0;padding:16px;background:#f6f8fa;color:#111;font-family:Arial,Helvetica,sans-serif;line-height:1.6;\">
    <div style=\"max-width:900px;margin:0 auto;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;\">
      <p style=\"margin:0 0 12px 0;color:#444;font-size:14px;\">新闻日期: {news_date}</p>
      <p style=\"margin:0 0 20px 0;color:#444;font-size:14px;\">来源: <a href=\"{source_url_escaped}\">{source_url_escaped}</a></p>
      {rendered}
    </div>
  </body>
</html>
"""


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
    html_body = build_html_email(news_date, source_url, markdown)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
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
