#!/usr/bin/env python3
"""
Cosmos Science News — Daily Article Auto-updater

Fetches science news via RSS feeds and generates Japanese educational content
(summary, vocabulary, quiz) using Claude AI. Rewrites 科学情報.html in-place.

Requirements:
    pip install feedparser anthropic

API Key setup (choose one):
    1. Set environment variable: ANTHROPIC_API_KEY=sk-ant-...
    2. Create .env file in same folder:  ANTHROPIC_API_KEY=sk-ant-...

Usage:
    python update_news.py --edition morning
    python update_news.py --edition evening
"""

import feedparser
import anthropic
import json
import re
import os
import sys
import random
import argparse
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
HTML_FILE = SCRIPT_DIR / "科学情報.html"
LOG_FILE  = SCRIPT_DIR / "update_log.txt"

FEEDS_BY_CAT: dict[str, list[str]] = {
    "space": [
        "https://www.nasa.gov/rss/dyn/breaking_news.rss",
        "https://www.sciencedaily.com/rss/space_time/astronomy.xml",
        "https://www.sciencedaily.com/rss/space_time/exoplanets.xml",
    ],
    "quantum": [
        "https://www.sciencedaily.com/rss/matter_energy/quantum_physics.xml",
        "https://www.sciencedaily.com/rss/matter_energy/physics.xml",
    ],
    "ai": [
        "https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml",
        "https://www.technologyreview.com/feed/",
    ],
    "bio": [
        "https://www.sciencedaily.com/rss/health_medicine/genetics.xml",
        "https://www.sciencedaily.com/rss/health_medicine/biology.xml",
        "https://www.nature.com/nm.rss",
    ],
    "earth": [
        "https://www.sciencedaily.com/rss/earth_climate/climate.xml",
        "https://www.sciencedaily.com/rss/earth_climate/geology.xml",
    ],
}

IMAGES: dict[str, list[str]] = {
    "space": [
        "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?w=1200&q=80",
        "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=900&q=80",
        "https://images.unsplash.com/photo-1516849841032-87cbac4d88f7?w=900&q=80",
        "https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?w=900&q=80",
    ],
    "quantum": [
        "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=900&q=80",
        "https://images.unsplash.com/photo-1614935151651-0bea6508db6b?w=900&q=80",
    ],
    "ai": [
        "https://images.unsplash.com/photo-1576086213369-97a306d36557?w=900&q=80",
        "https://images.unsplash.com/photo-1555255707-c07966088b7b?w=900&q=80",
        "https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=900&q=80",
    ],
    "bio": [
        "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=900&q=80",
        "https://images.unsplash.com/photo-1559757148-5c350d0d3c56?w=900&q=80",
        "https://images.unsplash.com/photo-1576319155264-99536e0be1ee?w=900&q=80",
    ],
    "earth": [
        "https://images.unsplash.com/photo-1509909756405-be0199881695?w=900&q=80",
        "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=900&q=80",
        "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=900&q=80",
    ],
}

# Category order per edition (determines card layout — first = featured)
EDITION_CATS: dict[str, list[str]] = {
    "morning": ["space", "quantum", "ai", "bio", "earth"],
    "evening": ["space", "ai", "bio", "earth", "quantum"],
}

# ── Logging ───────────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── RSS ───────────────────────────────────────────────────────────────────────
def _strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def fetch_feed(url: str) -> list[dict]:
    try:
        d = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0 Cosmos/2.0"})
        results = []
        for e in d.entries[:8]:
            img = None
            for attr in ("media_content", "media_thumbnail"):
                media = getattr(e, attr, None)
                if isinstance(media, list) and media:
                    img = media[0].get("url")
                    break
            if not img:
                for enc in getattr(e, "enclosures", []):
                    if enc.get("type", "").startswith("image"):
                        img = enc.get("url")
                        break

            title = e.get("title", "").strip()
            if len(title) < 10:
                continue

            summary = _strip_tags(
                getattr(e, "summary", "") or getattr(e, "description", "")
            )[:600]

            results.append({
                "title":   title,
                "summary": summary,
                "url":     e.get("link", ""),
                "img":     img,
                "source":  _strip_tags(d.feed.get("title", url.split("/")[2])),
            })
        return results
    except Exception as ex:
        log(f"    RSS error [{url[:55]}]: {ex}")
        return []

def collect_candidates(cats: list[str]) -> dict[str, list[dict]]:
    by_cat: dict[str, list[dict]] = {}
    for cat in cats:
        pool: list[dict] = []
        for feed_url in FEEDS_BY_CAT.get(cat, []):
            if len(pool) >= 4:
                break
            entries = fetch_feed(feed_url)
            pool.extend(entries[:2])
            log(f"    {cat} ← {feed_url.split('/')[2]}: {len(entries)} entries")
        by_cat[cat] = pool
    return by_cat

# ── Claude generation ─────────────────────────────────────────────────────────
_SYSTEM = (
    "You are an expert science communicator creating bilingual educational content. "
    "Respond with a single valid JSON object only — no markdown fences, no extra text."
)

_PROMPT = """\
Create Cosmos Science News article data from this RSS entry.

Title: {title}
Summary: {summary}
Source: {source}
Category: {cat}
Date: {month_year}

Return JSON with EXACTLY this structure (all string values must use escaped double-quotes internally):
{{
  "title": "Polished English headline — keep scientific terms",
  "excerpt": "Two-sentence English summary of key finding and significance.",
  "body": "<p>English paragraph: what was found and how.</p><p>English paragraph: implications. Source: <em>{source}, {month_year}</em>.</p>",
  "vocab": [
    {{"term": "Term1", "r": "カタカナ読み", "ja": "短い日本語訳", "desc": "日本語解説（50字以内）"}},
    {{"term": "Term2", "r": "カタカナ2", "ja": "訳2", "desc": "解説2"}},
    {{"term": "Term3", "r": "カタカナ3", "ja": "訳3", "desc": "解説3"}},
    {{"term": "Term4", "r": "カタカナ4", "ja": "訳4", "desc": "解説4"}}
  ],
  "quiz": [
    {{"q": "Question 1?", "opts": ["A","B","C","D"], "ans": 0, "fb": "日本語の解説（50字程度）"}},
    {{"q": "Question 2?", "opts": ["A","B","C","D"], "ans": 1, "fb": "日本語解説"}},
    {{"q": "Question 3?", "opts": ["A","B","C","D"], "ans": 2, "fb": "日本語解説"}},
    {{"q": "Question 4?", "opts": ["A","B","C","D"], "ans": 3, "fb": "日本語解説"}},
    {{"q": "Question 5?", "opts": ["A","B","C","D"], "ans": 1, "fb": "日本語解説"}}
  ]
}}

Rules: vocab = 4 key scientific terms. quiz = 5 questions with varied ans (0-3). No backtick characters in any value.
"""

def gen_article(client: anthropic.Anthropic, raw: dict, cat: str,
                idx: int, edition: str) -> "dict | None":
    now = datetime.now()
    month_year = f"{now.strftime('%B')} {now.year}"
    prompt = _PROMPT.format(
        title=raw["title"],
        summary=raw["summary"],
        source=raw["source"],
        cat=cat,
        month_year=month_year,
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        text = re.sub(r"^```[a-z]*\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
        data = json.loads(text)

        img_url = raw.get("img") or random.choice(IMAGES.get(cat, IMAGES["space"]))
        hours_ago = random.randint(2, 12)
        date_str = f"{now.strftime('%B')} {now.day}, {now.year}"

        return {
            "id":      f"{edition[0]}{idx + 1}_{now.strftime('%Y%m%d')}",
            "ed":      edition,
            "title":   data["title"],
            "excerpt": data["excerpt"],
            "body":    data["body"],
            "cat":     cat,
            "src":     raw["source"],
            "url":     raw["url"] or "#",
            "time":    f"{hours_ago} hours ago",
            "date":    date_str,
            "img":     img_url,
            "feat":    idx == 0,
            "vocab":   data["vocab"],
            "quiz":    data["quiz"],
        }
    except json.JSONDecodeError as e:
        log(f"    JSON error: {e}")
        return None
    except Exception as e:
        log(f"    Generation error: {e}")
        return None

# ── JS serialization ──────────────────────────────────────────────────────────
def _js(s: str) -> str:
    return (
        str(s)
        .replace("\\", "\\\\")
        .replace('"',  '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace("`",  "'")
    )

def _article_to_js(a: dict) -> str:
    vocab = ",\n  ".join(
        f'V("{_js(v["term"])}","{_js(v["r"])}","{_js(v["ja"])}","{_js(v["desc"])}")'
        for v in a["vocab"]
    )
    quiz = ",\n  ".join(
        'Q("{q}",[{opts}],{ans},"{fb}")'.format(
            q=_js(q["q"]),
            opts=",".join(f'"{_js(o)}"' for o in q["opts"]),
            ans=q["ans"],
            fb=_js(q["fb"]),
        )
        for q in a["quiz"]
    )
    feat = "true" if a["feat"] else "false"
    return (
        f'A("{a["id"]}","{a["ed"]}",\n'
        f'"{_js(a["title"])}",\n'
        f'"{_js(a["excerpt"])}",\n'
        f'"{_js(a["body"])}",\n'
        f'"{a["cat"]}","{_js(a["src"])}","{_js(a["url"])}",\n'
        f'"{a["time"]}","{a["date"]}","{a["img"]}",{feat},\n'
        f'[{vocab}],\n'
        f'[{quiz}])'
    )

def _build_block(articles: list[dict], name: str) -> str:
    body = ",\n\n".join(_article_to_js(a) for a in articles)
    return f"/*{name}_START*/\nconst {name}=[\n{body}\n];\n/*{name}_END*/"

# ── HTML update ───────────────────────────────────────────────────────────────
def update_html(articles: list[dict], edition: str) -> bool:
    name = "MORNING" if edition == "morning" else "EVENING"
    try:
        html = HTML_FILE.read_text(encoding="utf-8")
        new_block = _build_block(articles, name)

        # Prefer marker-based replacement (set after first run)
        html2, n = re.subn(
            rf"/\*{name}_START\*/[\s\S]*?/\*{name}_END\*/",
            new_block, html, count=1,
        )
        if n == 0:
            # First run: no markers yet — fall back to const NAME=[...];
            html2, n = re.subn(
                rf"const {name}=\[[\s\S]*?\];",
                new_block, html, count=1,
            )
        if n == 0:
            log(f"  ERROR: {name} array not found in HTML")
            return False

        HTML_FILE.write_text(html2, encoding="utf-8")
        log(f"  {name} updated ({len(articles)} articles written)")
        return True
    except Exception as e:
        log(f"  HTML write error: {e}")
        return False

# ── API key loader ────────────────────────────────────────────────────────────
def load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Cosmos News Updater")
    parser.add_argument(
        "--edition", choices=["morning", "evening"], required=True,
        help="Which edition to update (morning=06:00 / evening=18:00)",
    )
    args = parser.parse_args()
    edition = args.edition

    api_key = load_api_key()
    if not api_key:
        log("ERROR: ANTHROPIC_API_KEY not found.\n"
            "  Set as env var or create .env with: ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    if not HTML_FILE.exists():
        log(f"ERROR: {HTML_FILE} not found")
        sys.exit(1)

    log(f"=== Cosmos update: {edition} edition ===")
    client = anthropic.Anthropic(api_key=api_key)
    cats   = EDITION_CATS[edition]

    log("Fetching RSS feeds...")
    candidates = collect_candidates(cats)

    log("Generating articles with Claude...")
    articles: list[dict] = []
    for i, cat in enumerate(cats):
        pool = candidates.get(cat, [])
        if not pool:
            log(f"  SKIP {cat}: no RSS candidates")
            continue
        # Evening uses second candidate when available to reduce overlap with morning
        raw = pool[1 % len(pool)] if edition == "evening" and len(pool) > 1 else pool[0]
        log(f"  [{cat}] {raw['title'][:55]}...")
        art = gen_article(client, raw, cat, i, edition)
        if art:
            articles.append(art)
            log(f"    OK: {art['title'][:55]}")
        else:
            log(f"    FAILED — skipping")

    if len(articles) < 3:
        log(f"ERROR: Only {len(articles)}/5 articles generated. Keeping existing content.")
        sys.exit(1)

    log("Writing HTML...")
    ok = update_html(articles, edition)
    log(f"=== {'Done' if ok else 'FAILED'}: {len(articles)} articles ===")
    if not ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
