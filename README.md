# AI Fringe Report

Field notes on real science that changes how we see reality. Every morning an AI agent gathers new findings in five sections (Machine minds, The cosmos, The deep past, Nature of reality, and Beyond the fringe), checks them against an evidence standard, adds a picture where it safely can, and publishes to GitHub Pages. Every day is kept in the vault.

## How it works

| File | Job |
|---|---|
| `content.py` | What the site covers: sections, prompts, status labels, blocked sources, and the story validator. Edit this to add or retune a section. |
| `gather.py` | Daily: asks Claude (with web search) for each section's stories, validates them, adds an agency photo or a drawn plate, saves `data/YYYY-MM-DD.json`. |
| `images.py` | Picture safety: fetches only NASA/NOAA/USGS images and re-encodes them; rebuilds every AI drawing from a strict allowlist. |
| `build.py` | Turns `data/` into the website in `site/`. Standard library only. |
| `themes/field-journal/` | **Every visual choice**: colors, fonts, layout, background drawings. |
| `config.json` | Site name, tagline, URL, theme name, GoatCounter code. |

Each story carries two lines that show the shift in thinking: *What we thought / What we're finding*. In Beyond the fringe these become *The claim / What the evidence says*, plus a verdict (Unverified, Under investigation, Disputed, Contradicted, Debunked, Confirmed).

## Setup

1. Create a public repo named `ai-fringe-report` and upload everything here, including the hidden `.github` folder.
2. Create a new, separate Anthropic API key for this project (ideally in its own Console workspace with a monthly spend limit). Add it under Settings, Secrets and variables, Actions, as `ANTHROPIC_API_KEY`.
3. Settings, Pages: set Source to **GitHub Actions**.
4. Settings, Actions, General, Workflow permissions: **Read and write**, so the daily archive can be saved.
5. If your GitHub username or repo name differ, update `site_url` in `config.json`. Share links and link previews depend on it.
6. Actions tab, Daily AI Fringe Report, **Run workflow**. After that it runs daily at 14:00 UTC.

## Turning on visitor counting (GoatCounter)

Create a free account at goatcounter.com and pick a code (for example `aifringe`, giving `aifringe.goatcounter.com`). Put just the code in `config.json`:

```json
"goatcounter_code": "aifringe"
```

That's all. The build adds the counter, opens the security policy to exactly that one address, and updates the privacy line in the footer. GoatCounter counts unique visitors without cookies. The counting script is served from this repo rather than GoatCounter's servers, so no outside code runs on the page. Once the site carries ads, GoatCounter's terms call for a paid plan.

## Changing the look

All visuals live in `themes/field-journal/`. To adjust: edit the tokens at the top of `theme.css` (colors, fonts, page width, and `--bg-strength` for how visible the background drawings are), or replace `background.svg`. To make a whole new look: copy the folder to `themes/<new-name>/`, change it freely, and set `"theme": "<new-name>"` in `config.json`. The Python never needs to change, because the pages use plain structural class names (`.story`, `.shift`, `.badge`, `.story-figure`, and so on).

Keep fonts inside the theme folder: the security policy blocks fonts loaded from other sites.

## Safety choices

- The API key exists only in the gather job. Permissions default to none; only gather can write to the repo, and only deploy can publish.
- Every GitHub Action is pinned to an exact commit, and Pillow is pinned to a release that was at least two weeks old when chosen.
- Story text is escaped, links must be `https://`, tabloid and pseudo-science sites are blocked at search time and again in code, and repeats from the last 14 days are filtered out.
- Real photos come only from NASA, NOAA, and USGS pages, are re-encoded (which strips hidden data and neutralizes malformed files), and are credited. Agency pages occasionally include third-party images, so the credit names the agency and the original link stays one click away.
- AI drawings are rebuilt from an allowlist of shapes and attributes; scripts, links, styles, and outside references cannot survive. They are labeled as illustrations.
- A strict Content-Security-Policy allows only the site's own files (plus GoatCounter's counting address, if set).
- If every section fails, the run stops and yesterday's site stays up.
- Beyond the fringe attributes claims to their sources and never calls a named person a hoaxer in its own voice.

## Local preview

```bash
python build.py --preview    # builds site/ from the sample entries in sample/
```

Then open `site/index.html`. To test a real gather, put `ANTHROPIC_API_KEY=...` in a `.env` file (gitignored), run `pip install -r requirements.txt`, then `python gather.py`.

## Licenses

Fonts: Newsreader and IBM Plex Mono, SIL Open Font License (see `themes/field-journal/fonts/`). Counter script: GoatCounter's `count.js`, ISC license.
