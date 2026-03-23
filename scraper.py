"""
VC & Startup Morning Digest
Pulls latest stories from TechCrunch, Crunchbase News, VentureBeat,
and StrictlyVC via RSS and sends a formatted digest email via Gmail.

Env vars required:
  GMAIL_USER  — your Gmail address
  GMAIL_PASS  — Gmail App Password
  TO_EMAIL    — recipient email
"""

import os, smtplib, feedparser
from datetime import date, datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Config ────────────────────────────────────────────────────────────────────
TOP_N = 10

FEEDS = [
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/category/venture/feed/",
        "color": "#0a8a00",
    },
    {
        "name": "TechCrunch Startups",
        "url": "https://techcrunch.com/category/startups/feed/",
        "color": "#0a8a00",
    },
    {
        "name": "Crunchbase News",
        "url": "https://news.crunchbase.com/feed/",
        "color": "#1769ff",
    },
    {
        "name": "VentureBeat",
        "url": "https://venturebeat.com/category/business/feed/",
        "color": "#e8460a",
    },
    {
        "name": "StrictlyVC",
        "url": "https://strictlyvc.com/feed/",
        "color": "#7c3aed",
    },
]

# Keywords to prioritize (funding, VC, acquisitions)
PRIORITY_KEYWORDS = [
    "raises", "raised", "funding", "series a", "series b", "series c",
    "seed round", "pre-seed", "venture", "acquisition", "acquires",
    "acquired", "exits", "ipo", "spac", "valuation", "unicorn",
    "fund", "invest", "capital", "backed", "million", "billion",
]

# ── Fetch stories ─────────────────────────────────────────────────────────────
def fetch_stories():
    all_stories = []

    for feed_info in FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:15]:
                title   = entry.get("title", "").strip()
                link    = entry.get("link", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                # Strip HTML tags from summary
                import re
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                summary = summary[:200] + "..." if len(summary) > 200 else summary

                # Parse published date
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                # Score by keyword priority
                text_lower = (title + " " + summary).lower()
                score = sum(2 for kw in PRIORITY_KEYWORDS if kw in text_lower)

                if title and link:
                    all_stories.append({
                        "title":     title,
                        "link":      link,
                        "summary":   summary,
                        "source":    feed_info["name"],
                        "color":     feed_info["color"],
                        "published": published,
                        "score":     score,
                    })
        except Exception as e:
            print(f"⚠️  Failed to fetch {feed_info['name']}: {e}")

    # Deduplicate by title similarity
    seen_titles = set()
    unique = []
    for s in all_stories:
        key = s["title"].lower()[:60]
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(s)

    # Sort: priority score first, then recency
    unique.sort(key=lambda x: (x["score"], x["published"] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return unique[:TOP_N]


# ── Build email ───────────────────────────────────────────────────────────────
def build_email(stories):
    today = date.today().strftime("%A, %B %d")
    subject = f"🚀 VC & Startup Digest — {today}"

    # Plain text
    plain_lines = [f"VC & Startup Digest — {today}\n{'='*40}"]
    for i, s in enumerate(stories, 1):
        plain_lines.append(f"\n{i}. [{s['source']}] {s['title']}")
        if s["summary"]:
            plain_lines.append(f"   {s['summary']}")
        plain_lines.append(f"   {s['link']}")
    plain = "\n".join(plain_lines)

    # HTML
    rows = ""
    for s in stories:
        date_str = ""
        if s["published"]:
            date_str = s["published"].strftime("%-m/%-d")

        rows += f"""
        <tr style="border-bottom:1px solid #1e1e1e">
          <td style="padding:16px 8px;vertical-align:top">
            <div style="margin-bottom:4px">
              <span style="background:{s['color']};color:#fff;font-size:10px;
                           font-weight:600;padding:2px 7px;border-radius:10px;
                           text-transform:uppercase;letter-spacing:0.5px">
                {s['source']}
              </span>
              {"<span style='color:#555;font-size:11px;margin-left:8px'>" + date_str + "</span>" if date_str else ""}
            </div>
            <a href="{s['link']}" style="color:#f0f0f0;font-size:15px;font-weight:600;
                                         text-decoration:none;line-height:1.4;display:block;
                                         margin:6px 0">
              {s['title']}
            </a>
            <p style="color:#888;font-size:13px;margin:4px 0 0;line-height:1.5">
              {s['summary']}
            </p>
          </td>
        </tr>"""

    html = f"""
    <html><body style="font-family:-apple-system,sans-serif;max-width:620px;
                       margin:auto;background:#111;color:#f0f0f0;padding:28px 20px">
      <div style="border-bottom:3px solid #6366f1;padding-bottom:12px;margin-bottom:20px">
        <h1 style="margin:0;font-size:22px;color:#f0f0f0">🚀 VC & Startup Digest</h1>
        <p style="margin:4px 0 0;color:#666;font-size:13px">{today} · Top {len(stories)} stories</p>
      </div>
      <table style="width:100%;border-collapse:collapse">{rows}</table>
      <p style="color:#333;font-size:11px;margin-top:28px;border-top:1px solid #1e1e1e;padding-top:12px">
        Sources: TechCrunch · Crunchbase News · VentureBeat · StrictlyVC
      </p>
    </body></html>"""

    return subject, plain, html


# ── Send email ────────────────────────────────────────────────────────────────
def send_email(subject, plain, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = os.environ["GMAIL_USER"]
    msg["To"]      = os.environ["TO_EMAIL"]
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ["GMAIL_USER"], os.environ["GMAIL_PASS"])
        server.sendmail(os.environ["GMAIL_USER"], os.environ["TO_EMAIL"], msg.as_string())
    print(f"✅ Email sent: {subject}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔍 Fetching stories...")
    stories = fetch_stories()
    if not stories:
        print("⚠️  No stories found.")
    else:
        print(f"📋 Got {len(stories)} stories. Sending email...")
        subject, plain, html = build_email(stories)
        send_email(subject, plain, html)
        for i, s in enumerate(stories, 1):
            print(f"  {i}. [{s['source']}] {s['title']}")
