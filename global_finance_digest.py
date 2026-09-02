#!/usr/bin/env python3
"""Send a daily global finance-news digest through Gmail SMTP."""

from __future__ import annotations

import argparse
import email.utils
import html
import os
import re
import smtplib
import ssl
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

RECIPIENTS = ["dakangwj@gmail.com", "jasminewxr@gmail.com"]
BEIJING = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc
STATE_FILE = Path(__file__).with_name(".last_sent_london_date")
SOURCES = [
    ("Global markets", "https://news.google.com/rss/search?q=" + quote("global finance markets economy when:1d") + "&hl=en-GB&gl=GB&ceid=GB:en"),
    ("Central banks", "https://news.google.com/rss/search?q=" + quote("central bank inflation interest rates when:1d") + "&hl=en-GB&gl=GB&ceid=GB:en"),
    ("Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def text(node: ET.Element | None, tag: str) -> str:
    value = node.findtext(tag) if node is not None else ""
    return re.sub(r"\s+", " ", value or "").strip()


def get_feed(label: str, url: str) -> list[dict[str, object]]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (finance-digest/1.0)"})
    with urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())
    articles = []
    for item in root.findall(".//item"):
        published = None
        raw_date = text(item, "pubDate")
        if raw_date:
            try:
                published = email.utils.parsedate_to_datetime(raw_date).astimezone(UTC)
            except (TypeError, ValueError):
                pass
        articles.append({
            "title": text(item, "title"),
            "link": text(item, "link"),
            "source": label,
            "published": published,
        })
    return articles


def recent_articles() -> list[dict[str, object]]:
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    collected = []
    for label, url in SOURCES:
        try:
            collected.extend(get_feed(label, url))
        except Exception as error:  # A single unavailable source must not stop delivery.
            print(f"Warning: could not read {label}: {error}", file=sys.stderr)
    seen = set()
    unique = []
    for article in sorted(collected, key=lambda a: a["published"] or datetime.min.replace(tzinfo=UTC), reverse=True):
        title = str(article["title"])
        normalized = re.sub(r"[^a-z0-9]", "", title.lower())
        if not title or normalized in seen:
            continue
        published = article["published"]
        if published is not None and published < cutoff:
            continue
        seen.add(normalized)
        unique.append(article)
    return unique[:10]


def render(articles: list[dict[str, object]]) -> tuple[str, str]:
    now = datetime.now(BEIJING)
    subject = f"Global finance briefing | {now:%d %b %Y}"
    lines = [f"Global finance briefing - {now:%d %B %Y, %H:%M} Beijing", ""]
    rows = []
    for number, article in enumerate(articles, 1):
        title = str(article["title"])
        link = str(article["link"])
        source = str(article["source"])
        lines.extend([f"{number}. {title}", f"   {source}: {link}", ""])
        rows.append(f'<li style="margin:0 0 16px"><a href="{html.escape(link, quote=True)}" style="color:#0b57d0;text-decoration:none"><strong>{html.escape(title)}</strong></a><br><span style="color:#666;font-size:13px">{html.escape(source)}</span></li>')
    if not articles:
        lines.append("No qualifying articles were available from the configured sources.")
        rows.append("<li>No qualifying articles were available from the configured sources.</li>")
    plain = "\n".join(lines)
    body = "".join(rows)
    html_body = f'''<html><body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;line-height:1.45;color:#202124;max-width:680px;margin:auto"><h2 style="margin-bottom:4px">Global finance briefing</h2><p style="margin-top:0;color:#666">{now:%d %B %Y, %H:%M} Beijing time</p><ol style="padding-left:22px">{body}</ol><p style="font-size:12px;color:#777">Selected from public news feeds published in the preceding 24 hours.</p></body></html>'''
    return subject, plain, html_body


def send(subject: str, plain: str, html_body: str) -> None:
    user = os.environ.get("GMAIL_USER", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not user or not password:
        raise RuntimeError("Set GMAIL_USER and GMAIL_APP_PASSWORD in .env before sending.")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = user
    message["To"] = ", ".join(RECIPIENTS)
    message.set_content(plain)
    message.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Send regardless of Beijing time and prior delivery.")
    parser.add_argument("--preview", action="store_true", help="Print the digest instead of sending it.")
    args = parser.parse_args()
    load_dotenv(Path(__file__).with_name(".env"))
    now = datetime.now(BEIJING)
    today = now.date().isoformat()
    already_sent = STATE_FILE.exists() and STATE_FILE.read_text().strip() == today
    if not args.force and not args.preview and (now.hour != 8 or already_sent):
        print(f"Skipped: Beijing time is {now:%H:%M}; already sent today: {already_sent}.")
        return 0
    articles = recent_articles()
    subject, plain, html_body = render(articles)
    if args.preview:
        print(subject + "\n\n" + plain)
        return 0
    send(subject, plain, html_body)
    STATE_FILE.write_text(today + "\n", encoding="utf-8")
    print(f"Sent {len(articles)} articles to {', '.join(RECIPIENTS)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
