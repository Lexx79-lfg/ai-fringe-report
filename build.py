"""Build the website from data/: python build.py   (or: python build.py --preview)

Uses only the Python standard library. Markup here is purely structural; every visual
choice lives in themes/<theme>/theme.css, so the look can be replaced without touching this.
"""
import html
import re
import shutil
import sys
from datetime import date
from pathlib import Path

from content import CONFIG, LIMITS, ROOT, SECTIONS, clean_text, load_days
from images import sanitize_svg

SITE = ROOT / "site"
THEME = re.sub(r"[^a-z0-9-]", "", CONFIG.get("theme", "field-journal"))
SITE_URL = CONFIG["site_url"].rstrip("/") + "/"
GC_CODE = CONFIG.get("goatcounter_code", "").strip().lower()
if GC_CODE and not re.fullmatch(r"[a-z0-9-]{2,50}", GC_CODE):
    sys.exit("goatcounter_code in config.json should be just the code, like 'aifringe'.")
GC_ENDPOINT = f"https://{GC_CODE}.goatcounter.com" if GC_CODE else ""


def e(value):
    return html.escape(str(value or ""), quote=True)


def long_date(iso):
    d = date.fromisoformat(iso)
    return f"{d:%A, %B} {d.day}, {d.year}"


def plural(n, word):
    if n == 1:
        return f"{n} {word}"
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return f"{n} {word[:-1]}ies"  # entry -> entries, but day -> days
    return f"{n} {word}s"


def csp():
    extra = f" {GC_ENDPOINT}" if GC_ENDPOINT else ""
    return ("default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "
            f"img-src 'self' data:{extra}; connect-src {GC_ENDPOINT or chr(39) + 'none' + chr(39)}; "
            "base-uri 'none'; form-action 'none'")


def story_id(day_iso, n):
    return f"s-{day_iso.replace('-', '')}-{n:02d}"


def render_figure(story, root):
    if story.get("image"):
        img = story["image"]
        src = str(img.get("src", ""))
        if re.fullmatch(r"images/[0-9a-f]{16}\.jpg", src):
            return (f'<figure class="story-figure"><img src="{root}{e(src)}" alt="{e(img.get("alt"))}" loading="lazy">'
                    f'<figcaption>{e(img.get("credit"))}</figcaption></figure>')
    if story.get("plate"):
        svg = sanitize_svg(story["plate"], f"Ink drawing for: {story['title']}")  # re-checked on every build
        if svg:
            return (f'<figure class="story-figure story-figure--plate">{svg}'
                    '<figcaption>Ink drawing by AI. An illustration, not a photograph.</figcaption></figure>')
    return ""


def render_story(story, day_iso, n, kind, root, lead=False):
    story = {**story, **{f: clean_text(story.get(f, ""), lim) for f, lim in LIMITS.items()}}
    sid = story_id(day_iso, n)
    labels = ("The claim", "What the evidence says") if kind == "fringe" else ("What we thought", "What we're finding")
    badge = re.sub(r"[^a-z]+", "-", story["status"].lower()).strip("-")
    shift = ""
    if story.get("thought") or story.get("finding"):
        shift = (f'<dl class="shift"><div class="shift-before"><dt>{labels[0]}</dt><dd>{e(story.get("thought"))}</dd></div>'
                 f'<div class="shift-after"><dt>{labels[1]}</dt><dd>{e(story.get("finding"))}</dd></div></dl>')
    why = f'<p class="story-why">{e(story["why"])}</p>' if story.get("why") else ""
    published = f'<span class="published">published {e(story["published"])}</span>' if story.get("published") else ""
    permalink = f"{SITE_URL}day/{day_iso}.html#{sid}"
    return f"""<article class="story{' story--lead' if lead else ''} story--{kind}" id="{sid}">
  <p class="story-meta"><span class="catalog">No. {e(day_iso.replace('-', '.'))}-{n:02d}</span> <span class="badge badge--{badge}">{e(story['status'])}</span> {published}</p>
  {render_figure(story, root)}
  <h3 class="story-title">{e(story['title'])}</h3>
  <p class="story-summary">{e(story['summary'])}</p>
  {shift}
  {why}
  <p class="story-actions"><a class="story-source" href="{e(story['url'])}" target="_blank" rel="noopener noreferrer">Read the original at {e(story['source'] or 'the source')}</a>
  <button class="share" type="button" data-share-url="{e(permalink)}" data-share-title="{e(story['title'])}">Share</button></p>
</article>"""


def render_day(day, root, archived):
    total = sum(len(day["sections"].get(s["id"], [])) for s in SECTIONS)
    contents = "".join(
        f'<li><a href="#{s["id"]}">{e(s["name"])}</a> <span class="count">{len(day["sections"].get(s["id"], []))}</span></li>'
        for s in SECTIONS
    )
    note = (f'<p class="archived">An archived entry. <a href="{root}index.html">See today\'s report</a> '
            f'or <a href="{root}vault.html">browse the vault</a>.</p>') if archived else ""
    parts, n = [], 0
    for sec in SECTIONS:
        stories = day["sections"].get(sec["id"], [])
        rendered = []
        for i, story in enumerate(stories):
            n += 1
            rendered.append(render_story(story, day["date"], n, sec["kind"], root, lead=(i == 0)))
        if rendered:
            body = rendered[0] + (f'<div class="story-grid">{"".join(rendered[1:])}</div>' if len(rendered) > 1 else "")
        else:
            body = '<p class="empty">Nothing in this section met the evidence bar today. The vault holds earlier entries.</p>'
        parts.append(f"""<section class="section section--{sec['kind']}" id="{sec['id']}">
  <header class="section-head"><h2>{e(sec['name'])}</h2><p class="section-blurb">{e(sec['blurb'])}</p></header>
  {body}
</section>""")
    return f"""<div class="report-head">
  <h1>{e(long_date(day['date']))}</h1>
  <p class="report-count">{plural(total, 'entry')} in today's journal</p>
  {note}
</div>
<nav class="contents" aria-label="Sections"><ul>{contents}</ul></nav>
{''.join(parts)}"""


def render_vault(days):
    rows = []
    for day in days:
        headline = next((v[0]["title"] for s in SECTIONS if (v := day["sections"].get(s["id"]))), "")
        total = sum(len(v) for v in day["sections"].values())
        rows.append(f'<li><a href="day/{e(day["date"])}.html"><span class="vault-date">{e(long_date(day["date"]))}</span>'
                    f'<span class="vault-headline">{e(headline)}</span><span class="vault-count">{plural(total, "entry")}</span></a></li>')
    listing = "".join(rows) or '<li class="empty">The vault fills one day at a time. The first entry appears after the next daily run.</li>'
    return f"""<div class="report-head"><h1>The vault</h1>
  <p class="report-count">Every past entry, newest first. {plural(len(days), 'day')} so far.</p></div>
<ol class="vault">{listing}</ol>"""


def page(title, description, body, root, active, canonical, banner=""):
    counter = ""
    if GC_ENDPOINT:
        counter = f'<script data-goatcounter="{GC_ENDPOINT}/count" async src="{root}static/count.js"></script>'
    cur = {"today": "", "vault": ""}
    cur[active] = ' aria-current="page"'
    privacy = ("We count visits with GoatCounter, which uses no cookies and does not track you across sites."
               if GC_ENDPOINT else "This site uses no cookies and no tracking.")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp()}">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(CONFIG['site_title'])}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:image" content="{e(SITE_URL)}static/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{root}static/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}theme/theme.css">
<script src="{root}static/app.js" defer></script>
{counter}
</head>
<body>
{banner}
<header class="masthead">
  <div class="masthead-title">
    <p class="wordmark"><a href="{root}index.html">{e(CONFIG['site_title'])}</a></p>
    <p class="tagline">{e(CONFIG['tagline'])}</p>
  </div>
  <div class="masthead-tools">
    <nav class="site-nav" aria-label="Site"><a href="{root}index.html"{cur['today']}>Today's entries</a><a href="{root}vault.html"{cur['vault']}>The vault</a></nav>
    <button id="hum" class="hum" type="button" aria-pressed="false">Play field hum</button>
  </div>
</header>
<main class="page">
{body}
</main>
<footer class="colophon">
  <p>Gathered daily by an AI agent from journals, research institutions, space agencies, news outlets, and fact-checkers. Summaries are written in its own words and link to the original. Photos come from public agencies and are credited; drawings are made by AI. Check the original before sharing.</p>
  <p>{privacy} Built by {e(CONFIG.get('author', ''))}.</p>
</footer>
</body>
</html>
"""


def build(preview=False):
    data_dir = ROOT / ("sample" if preview else "data")
    days = load_days(data_dir)
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "day").mkdir(parents=True)
    shutil.copytree(ROOT / "static", SITE / "static")
    shutil.copytree(ROOT / "themes" / THEME, SITE / "theme")
    if (data_dir / "images").exists():
        shutil.copytree(data_dir / "images", SITE / "images")

    banner = '<p class="preview-banner">Layout preview. Sample entries, not today\'s news.</p>' if preview else ""
    tagline = CONFIG["tagline"]
    if days:
        latest = days[0]
        body = render_day(latest, "", archived=False)
        title = f"{CONFIG['site_title']}: {long_date(latest['date'])}"
    else:
        body = '<div class="report-head"><h1>The first entry is on its way</h1><p class="report-count">The agent publishes after its next daily run.</p></div>'
        title = CONFIG["site_title"]
    (SITE / "index.html").write_text(page(title, tagline, body, "", "today", SITE_URL, banner), encoding="utf-8")

    for day in days:
        lead = next((v[0]["title"] for s in SECTIONS if (v := day["sections"].get(s["id"]))), tagline)
        html_text = page(f"{CONFIG['site_title']}: {long_date(day['date'])}", lead, render_day(day, "../", True),
                         "../", "vault", f"{SITE_URL}day/{day['date']}.html", banner)
        (SITE / "day" / f"{day['date']}.html").write_text(html_text, encoding="utf-8")

    (SITE / "vault.html").write_text(
        page(f"The vault: {CONFIG['site_title']}", tagline, render_vault(days), "", "vault", f"{SITE_URL}vault.html", banner),
        encoding="utf-8")
    print(f"Built site/ with {len(days)} day(s), theme '{THEME}'.")


if __name__ == "__main__":
    build(preview="--preview" in sys.argv)
