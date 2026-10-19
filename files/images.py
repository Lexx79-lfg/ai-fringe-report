"""Images for the AI Fringe Report, handled so they are safe to publish and share.

Two sources only:
1. Real photos from public agencies whose work is free to reuse (NASA, NOAA, USGS).
   Downloaded at gather time, resized, and re-encoded so the repo stays small and
   any malformed file is neutralized.
2. Ink "plates" drawn by Claude as SVG. Every plate is rebuilt from a strict allowlist
   of shapes and attributes, so it cannot carry scripts, links, or external content.
"""
import hashlib
import html
import io
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

# Hosts whose own images are generally free to reuse with credit. Pages on these
# sites can still show third-party images, so the credit line names the agency
# and the original link stays one click away.
OPEN_IMAGE_HOSTS = {"nasa.gov": "NASA", "noaa.gov": "NOAA", "usgs.gov": "USGS"}

MAX_PAGE_BYTES = 2_000_000
MAX_IMAGE_BYTES = 8_000_000
MAX_IMAGE_WIDTH = 1200
USER_AGENT = "AIFringeReport/1.0 (+https://github.com/Lexx79-lfg/ai-fringe-report)"


def agency_for(url):
    host = urlsplit(url).netloc.lower().split(":")[0]
    for domain, name in OPEN_IMAGE_HOSTS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return None


class _AllowlistRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only if it stays on an allowlisted https host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://") or not agency_for(newurl):
            raise urllib.error.HTTPError(newurl, code, "redirect to non-allowlisted host", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_AllowlistRedirects)


def _get(url, limit):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _opener.open(req, timeout=20) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise ValueError("response too large")
    return data


class _OgImage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.image, self.alt = None, None

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        a = dict(attrs)
        prop = (a.get("property") or a.get("name") or "").lower()
        if prop in ("og:image", "og:image:secure_url") and not self.image:
            self.image = a.get("content")
        elif prop == "og:image:alt" and not self.alt:
            self.alt = a.get("content")


def fetch_open_image(story_url, title, images_dir):
    """Return {"src", "credit", "alt"} for a reusable agency image, or None."""
    agency = agency_for(story_url)
    if not agency or not story_url.startswith("https://"):
        return None
    from PIL import Image  # only needed in the gather job

    page = _get(story_url, MAX_PAGE_BYTES).decode("utf-8", errors="replace")
    parser = _OgImage()
    parser.feed(page)
    if not parser.image:
        return None
    image_url = urljoin(story_url, parser.image.strip())
    if not image_url.startswith("https://") or not agency_for(image_url):
        return None

    raw = _get(image_url, MAX_IMAGE_BYTES)
    with Image.open(io.BytesIO(raw)) as img:
        if img.format not in ("JPEG", "PNG", "WEBP"):
            return None
        img = img.convert("RGB")
        if img.width > MAX_IMAGE_WIDTH:
            img = img.resize((MAX_IMAGE_WIDTH, round(img.height * MAX_IMAGE_WIDTH / img.width)))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=80, optimize=True, progressive=True)  # strips metadata
    data = out.getvalue()
    name = hashlib.sha256(data).hexdigest()[:16] + ".jpg"
    images_dir.mkdir(parents=True, exist_ok=True)
    (images_dir / name).write_bytes(data)
    alt = " ".join((parser.alt or title).split())[:200]
    return {"src": f"images/{name}", "credit": f"Image: {agency}", "alt": alt}


# ---------- SVG plates ----------

PLATE_VIEWBOX = "0 0 400 300"
ALLOWED_TAGS = {"svg", "g", "path", "circle", "ellipse", "line", "polyline", "polygon", "rect", "text"}
NUM = re.compile(r"^-?[0-9.]+(e-?[0-9]+)?$")
NUM_LIST = re.compile(r"^[-0-9.,eE\s]+$")
PATH_D = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9.,\-eE\s]+$")
TRANSFORM = re.compile(r"^(\s*(translate|rotate|scale|matrix|skewX|skewY)\([-0-9.,eE\s]+\)\s*)+$")
ATTRS = {
    "d": PATH_D, "points": NUM_LIST, "transform": TRANSFORM, "stroke-dasharray": NUM_LIST,
    **{k: NUM for k in ("cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2",
                        "width", "height", "stroke-width", "opacity", "font-size")},
}
CHOICES = {
    "fill": {"none", "currentColor"},
    "stroke": {"none", "currentColor"},
    "stroke-linecap": {"butt", "round", "square"},
    "stroke-linejoin": {"miter", "round", "bevel"},
    "text-anchor": {"start", "middle", "end"},
}
MAX_ELEMENTS = 400
MAX_SVG_CHARS = 40_000


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def sanitize_svg(source, label):
    """Rebuild an SVG from allowlisted parts. Returns safe markup or None."""
    if not source:
        return None
    source = re.sub(r"<!--.*?-->", "", source, flags=re.S)  # drawing notes are harmless; drop them
    if len(source) > MAX_SVG_CHARS or "<!" in source:
        return None  # anything else starting "<!" (doctype, entities, CDATA) is refused
    start, end = source.find("<svg"), source.rfind("</svg>")
    if start == -1 or end == -1:
        return None
    try:
        root = ElementTree.fromstring(source[start:end + 6])
    except ElementTree.ParseError:
        return None
    if _local(root.tag) != "svg":
        return None

    count = 0

    def render(el):
        nonlocal count
        tag = _local(el.tag)
        if tag not in ALLOWED_TAGS or tag == "svg":
            return ""
        count += 1
        if count > MAX_ELEMENTS:
            raise ValueError("too many elements")
        parts = []
        for key, value in el.attrib.items():
            key, value = _local(key), value.strip()
            if key in CHOICES:
                if value not in CHOICES[key]:
                    value = "currentColor" if key in ("fill", "stroke") and value != "none" else None
                    if value is None:
                        continue
            elif key in ATTRS:
                if not ATTRS[key].match(value) or len(value) > 8000:
                    continue
            else:
                continue  # drops style, href, on*, class, id, and everything else
            parts.append(f'{key}="{html.escape(value)}"')
        attrs = (" " + " ".join(parts)) if parts else ""
        if tag == "text":
            text = html.escape(" ".join("".join(el.itertext()).split())[:40])
            return f"<text{attrs}>{text}</text>"
        children = "".join(render(child) for child in el)
        return f"<{tag}{attrs}>{children}</{tag}>"

    try:
        body = "".join(render(child) for child in root)
    except ValueError:
        return None
    if count == 0:
        return None
    safe_label = html.escape(" ".join(label.split())[:160])
    return (f'<svg class="plate-svg" viewBox="{PLATE_VIEWBOX}" role="img" aria-label="{safe_label}" '
            f'fill="none" stroke="currentColor" stroke-width="1.5">{body}</svg>')
