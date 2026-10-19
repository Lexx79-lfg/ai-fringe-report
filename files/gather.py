"""Gather today's stories: python gather.py

Runs in the GitHub Actions 'gather' job, the only place the API key exists.
"""
import json
import os
import sys
from datetime import date, datetime, timezone

import anthropic
from dotenv import load_dotenv

from content import (BLOCKED_DOMAINS, FRINGE_PROMPT, PLATE_PROMPT, ROOT, SCIENCE_PROMPT,
                     SECTIONS, clean_story, load_days, normalize_url)
from images import fetch_open_image, sanitize_svg

MODEL = "claude-sonnet-5-5"
RECENT_DAYS = 14
DATA_DIR = ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"


def reply_text(response):
    return "".join(b.text for b in response.content if b.type == "text")


def ask_for_stories(client, section, recent_titles, today):
    avoid = "\n".join(f"- {t}" for t in recent_titles[:40]) or "- (none yet)"
    request = (
        f"Today is {today}. Section: {section['name']}.\nFocus: {section['focus']}\n"
        f"Find {section['count']} stories from {section['window']}.\n"
        f"Already covered recently, do not repeat these:\n{avoid}"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=FRINGE_PROMPT if section["kind"] == "fringe" else SCIENCE_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5,
                "blocked_domains": BLOCKED_DOMAINS}],
        messages=[{"role": "user", "content": request}],
    )
    text = reply_text(response)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array in reply: {text[:300]!r}")
    stories = json.loads(text[start:end + 1])
    if not isinstance(stories, list):
        raise ValueError("Reply was not a list")
    return stories


def draw_plate(client, story):
    response = client.messages.create(
        model=MODEL,
        max_tokens=6000,
        system=PLATE_PROMPT,
        messages=[{"role": "user", "content": f"Title: {story['title']}\nSummary: {story['summary']}"}],
    )
    return sanitize_svg(reply_text(response), f"Ink drawing for: {story['title']}")


def add_picture(client, story, is_lead):
    """Agency photo if the story is from NASA/NOAA/USGS; otherwise a drawn plate for lead stories."""
    try:
        image = fetch_open_image(story["url"], story["title"], IMAGES_DIR)
        if image:
            story["image"] = image
            return
    except Exception as err:
        print(f"  image skipped for {story['url']}: {err}")
    if is_lead:
        try:
            plate = draw_plate(client, story)
            if plate:
                story["plate"] = plate
            else:
                print("  plate rejected by the sanitizer or cut off")
        except Exception as err:
            print(f"  plate skipped: {err}")


def main():
    load_dotenv()
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    today = date.today().isoformat()

    recent = [d for d in load_days(DATA_DIR) if d["date"] != today][:RECENT_DAYS]
    seen_urls, titles = set(), {s["id"]: [] for s in SECTIONS}
    for day in recent:
        for sid, stories in day.get("sections", {}).items():
            for s in stories:
                seen_urls.add(normalize_url(s.get("url", "")))
                titles.setdefault(sid, []).append(s.get("title", ""))

    sections, failures = {}, []
    for section in SECTIONS:
        sid = section["id"]
        try:
            raw = ask_for_stories(client, section, titles[sid], today)
        except Exception as err:  # one bad section should not sink the report
            print(f"[{sid}] failed: {err}")
            failures.append(sid)
            raw = []
        kept = [s for s in (clean_story(r, section["kind"], seen_urls) for r in raw) if s]
        for i, story in enumerate(kept):
            add_picture(client, story, is_lead=(i == 0))
        print(f"[{sid}] received {len(raw)}, kept {len(kept)}")
        sections[sid] = kept

    total = sum(len(v) for v in sections.values())
    if total == 0:
        print("No usable stories today; leaving the published site unchanged.")
        sys.exit(1)  # stops the workflow so yesterday's site stays up

    DATA_DIR.mkdir(exist_ok=True)
    record = {
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODEL,
        "failed_sections": failures,
        "sections": sections,
    }
    out = DATA_DIR / f"{today}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {out.name} with {total} stories.")


if __name__ == "__main__":
    main()
