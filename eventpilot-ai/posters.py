"""Generates modern, creative event posters and hero banners (no internet needed).
If an event has a real image (uploaded file or URL) that is used instead."""
import hashlib
import math
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from utils import fmt_date_short, fmt_price, fmt_time

def _default_poster_dir() -> Path:
    env = os.getenv("POSTER_DIR")
    if env:
        return Path(env)
    if Path("data/posters").exists():
        return Path("data/posters")
    if Path("eventpilot-ai/data/posters").exists():
        return Path("eventpilot-ai/data/posters")
    return Path("data/posters")


POSTER_DIR = _default_poster_dir()

THEMES = {  # category -> (top colour, bottom colour, accent colour, display label)
    "Workshop":   ("#071526", "#0f3460", "#00d2d3", "🤖 TECH & WORKSHOP"),
    "Networking": ("#062226", "#114b5f", "#1dd1a1", "🤝 NETWORKING"),
    "Cultural":   ("#3b0918", "#781d42", "#ffb142", "🎭 CULTURAL FEST"),
    "Career":     ("#0d1b2a", "#1b263b", "#38bdf8", "💼 CAREER & TECH"),
    "Music":      ("#18052e", "#440061", "#f368e0", "🎸 LIVE MUSIC"),
    "Sports":     ("#260803", "#7a1a08", "#ff793f", "🏃 SPORTS & RUN"),
    "Comedy":     ("#1b0c26", "#481547", "#ff9f43", "🎤 COMEDY NIGHT"),
    "Other":      ("#0f172a", "#1e293b", "#94a3b8", "🎟️ FEATURED EVENT"),
}

_FONT_FILES = ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "segoeuib.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]


def font(size: int):
    for name in _FONT_FILES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def hex_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def theme(category: str):
    info = THEMES.get(category, THEMES["Other"])
    return hex_rgb(info[0]), hex_rgb(info[1])


def theme_accent(category: str):
    info = THEMES.get(category, THEMES["Other"])
    return hex_rgb(info[2])


def category_badge_label(category: str):
    info = THEMES.get(category, THEMES["Other"])
    return info[3]


def _gradient(w, h, c1, c2, horizontal=False):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    n = w if horizontal else h
    for i in range(n):
        t = i / max(n - 1, 1)
        col = tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))
        d.line([(i, 0), (i, h)] if horizontal else [(0, i), (w, i)], fill=col)
    return img


def _wrap(draw, text, fnt, max_w):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _fit(draw, text, fnt, max_w):
    """Shorten text with an ellipsis so it fits max_w pixels."""
    if draw.textlength(text, font=fnt) <= max_w:
        return text
    while text and draw.textlength(text + "...", font=fnt) > max_w:
        text = text[:-1]
    return text.rstrip() + "..."


def _draw_music_art(d, w, h, accent, rnd):
    """Stage lights, audio visualizer equalizer and acoustic pulse rings."""
    # Top spotlights
    d.polygon([(0, 0), (int(w * 0.42), int(h * 0.45)), (int(w * 0.12), int(h * 0.45))], fill=(255, 255, 255, 22))
    d.polygon([(w, 0), (int(w * 0.88), int(h * 0.45)), (int(w * 0.58), int(h * 0.45))], fill=(255, 255, 255, 22))
    # Concentric sound rings
    cx, cy = w // 2, int(h * 0.28)
    for r in (50, 95, 145, 195, 245):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*accent, 35), width=2)
    # Equalizer bars
    bars = 21
    bw = 14
    gap = 8
    total_w = bars * bw + (bars - 1) * gap
    sx = (w - total_w) // 2
    base_y = int(h * 0.44)
    for i in range(bars):
        dist = abs(i - bars // 2) / (bars // 2)
        height = int((100 - dist * 40) * (0.4 + 0.6 * math.sin(i * 0.5 + 1.2) ** 2))
        x = sx + i * (bw + gap)
        alpha = int(140 + 100 * (height / 100))
        d.rounded_rectangle([x, base_y - height, x + bw, base_y], radius=6, fill=(*accent, alpha))
    # Glowing particles
    for _ in range(12):
        px, py = rnd.randint(40, w - 40), rnd.randint(60, int(h * 0.48))
        pr = rnd.randint(3, 8)
        d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(255, 255, 255, rnd.randint(50, 160)))


def _draw_comedy_art(d, w, h, accent, rnd):
    """Overhead conical spotlight and vintage microphone icon."""
    cx = w // 2
    # Conical spotlight beam from top center to stage pool
    d.polygon([(cx - 40, 0), (cx + 40, 0), (w - 30, int(h * 0.48)), (30, int(h * 0.48))], fill=(255, 255, 255, 26))
    # Glowing circular stage floor
    d.ellipse([int(w * 0.15), int(h * 0.38), int(w * 0.85), int(h * 0.50)], fill=(*accent, 45))
    # Stylized microphone silhouette
    my = int(h * 0.24)
    # Mic capsule (classic rounded vintage head)
    d.rounded_rectangle([cx - 24, my - 44, cx + 24, my + 14], radius=16, fill=(255, 255, 255, 200))
    # Grille lines
    for gy in range(my - 34, my + 10, 8):
        d.line([(cx - 18, gy), (cx + 18, gy)], fill=(40, 40, 60, 220), width=2)
    # Neck and stand
    d.rectangle([cx - 14, my + 14, cx + 14, my + 22], fill=(255, 255, 255, 180))
    d.rectangle([cx - 5, my + 22, cx + 5, my + 85], fill=(255, 255, 255, 180))
    # Stand base
    d.ellipse([cx - 40, my + 80, cx + 40, my + 96], fill=(255, 255, 255, 180))
    # Ambient stage sparkles
    for _ in range(16):
        px, py = rnd.randint(50, w - 50), rnd.randint(40, int(h * 0.46))
        d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(*accent, rnd.randint(80, 220)))


def _draw_workshop_art(d, w, h, accent, rnd):
    """Neural network nodes, synaptic connection lines and tech matrix."""
    # Tech grid lines
    for gx in range(40, w, 60):
        d.line([(gx, 30), (gx, int(h * 0.48))], fill=(*accent, 15), width=1)
    for gy in range(40, int(h * 0.48), 50):
        d.line([(30, gy), (w - 30, gy)], fill=(*accent, 15), width=1)
    # Central processor hexagon
    cx, cy = w // 2, int(h * 0.26)
    r = 60
    hex_pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
               for a in range(0, 360, 60)]
    d.polygon(hex_pts, outline=(*accent, 180), width=3)
    d.polygon([(cx + (r - 16) * math.cos(math.radians(a)), cy + (r - 16) * math.sin(math.radians(a)))
               for a in range(0, 360, 60)], fill=(*accent, 45))
    # Neural nodes
    nodes = [
        (cx - 140, cy - 60), (cx - 160, cy + 50), (cx - 80, cy - 90),
        (cx + 80, cy - 90), (cx + 140, cy - 60), (cx + 160, cy + 50),
        (cx - 70, cy + 95), (cx + 70, cy + 95), (cx - 190, cy), (cx + 190, cy)
    ]
    for nx, ny in nodes:
        d.line([(cx, cy), (nx, ny)], fill=(*accent, 70), width=2)
        d.ellipse([nx - 9, ny - 9, nx + 9, ny + 9], fill=(*accent, 180), outline=(255, 255, 255, 220), width=2)
    d.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(255, 255, 255, 240))


def _draw_cultural_art(d, w, h, accent, rnd):
    """Festive mandala sunburst, concentric rings and golden sparkles."""
    cx, cy = w // 2, int(h * 0.26)
    # Radiating mandala rays
    for angle in range(0, 360, 15):
        rad = math.radians(angle)
        x1 = cx + 55 * math.cos(rad)
        y1 = cy + 55 * math.sin(rad)
        x2 = cx + 185 * math.cos(rad)
        y2 = cy + 185 * math.sin(rad)
        d.line([(x1, y1), (x2, y2)], fill=(*accent, 65), width=2)
    # Concentric patterned rings
    for r in (50, 90, 135, 185):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*accent, 90), width=2)
    # Dandiya / festive diamond motifs
    for angle in range(0, 360, 30):
        rad = math.radians(angle)
        mx = cx + 135 * math.cos(rad)
        my = cy + 135 * math.sin(rad)
        d.ellipse([mx - 7, my - 7, mx + 7, my + 7], fill=(255, 235, 150, 210))
    # Center golden sun
    d.ellipse([cx - 36, cy - 36, cx + 36, cy + 36], fill=(*accent, 140), outline=(255, 255, 255, 200), width=2)
    # Festive bokeh particles
    for _ in range(22):
        px, py = rnd.randint(30, w - 30), rnd.randint(40, int(h * 0.48))
        pr = rnd.randint(3, 9)
        d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(255, 215, 120, rnd.randint(40, 160)))


def _draw_sports_art(d, w, h, accent, rnd):
    """Dynamic high-speed racing stripes and energy velocity chevrons."""
    # Fast angled track stripes
    for offset in range(-120, w + 120, 65):
        d.polygon([(offset, 0), (offset + 35, 0), (offset - 75, int(h * 0.50)), (offset - 110, int(h * 0.50))],
                  fill=(*accent, 35))
    # Momentum speed arcs
    cx, cy = w // 2, int(h * 0.26)
    for r in (70, 120, 170, 220):
        d.arc([cx - r, cy - r, cx + r, cy + r], start=160, end=350, fill=(255, 255, 255, 60), width=3)
    # Speed chevrons >>>
    for i in range(4):
        bx = int(w * 0.28) + i * 50
        by = int(h * 0.26)
        d.line([(bx, by - 35), (bx + 25, by), (bx, by + 35)], fill=(*accent, 220), width=5)


def _draw_networking_art(d, w, h, accent, rnd):
    """Constellation network nodes and interconnected ecosystem mesh."""
    cx, cy = w // 2, int(h * 0.26)
    pts = [
        (cx, cy - 80), (cx - 90, cy - 40), (cx + 90, cy - 40),
        (cx - 140, cy + 30), (cx, cy + 20), (cx + 140, cy + 30),
        (cx - 70, cy + 90), (cx + 70, cy + 90), (cx - 180, cy - 10), (cx + 180, cy - 10)
    ]
    # Connecting lines between nearby points
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dist = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
            if dist < 140:
                d.line([pts[i], pts[j]], fill=(*accent, 75), width=2)
    # Pulse rings around center
    for r in (45, 95, 150):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*accent, 40), width=1)
    # Glowing nodes
    for px, py in pts:
        d.ellipse([px - 8, py - 8, px + 8, py + 8], fill=(*accent, 190), outline=(255, 255, 255, 220), width=2)
    d.ellipse([cx - 14, cy + 20 - 14, cx + 14, cy + 20 + 14], fill=(255, 255, 255, 240))


def _draw_career_art(d, w, h, accent, rnd):
    """Ascending isometric data pillars, growth trajectory and modern tech grid."""
    # Data pillars stepping up
    base_y = int(h * 0.38)
    bars = [
        (int(w * 0.16), 50), (int(w * 0.32), 85),
        (int(w * 0.48), 125), (int(w * 0.64), 165), (int(w * 0.80), 205)
    ]
    for x, bh in bars:
        d.rounded_rectangle([x - 24, base_y - bh, x + 24, base_y], radius=8,
                            fill=(*accent, 110), outline=(255, 255, 255, 120), width=2)
    # Upward trending growth line
    growth_pts = [(x, base_y - bh - 14) for x, bh in bars]
    for i in range(len(growth_pts) - 1):
        d.line([growth_pts[i], growth_pts[i + 1]], fill=(255, 255, 255, 220), width=4)
        d.ellipse([growth_pts[i][0] - 6, growth_pts[i][1] - 6, growth_pts[i][0] + 6, growth_pts[i][1] + 6],
                  fill=(255, 255, 255, 255))
    last_pt = growth_pts[-1]
    d.ellipse([last_pt[0] - 8, last_pt[1] - 8, last_pt[0] + 8, last_pt[1] + 8],
              fill=(*accent, 255), outline=(255, 255, 255, 255), width=2)


def _draw_other_art(d, w, h, accent, rnd):
    """Minimalist abstract geometry with glowing gradient rings and rounded cards."""
    cx, cy = w // 2, int(h * 0.26)
    for r in (50, 100, 150, 200):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*accent, 45), width=2)
    d.rounded_rectangle([cx - 100, cy - 70, cx + 100, cy + 70], radius=20,
                        fill=(*accent, 40), outline=(255, 255, 255, 80), width=2)
    for _ in range(10):
        px, py = rnd.randint(40, w - 40), rnd.randint(40, int(h * 0.46))
        pr = rnd.randint(4, 10)
        d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(255, 255, 255, rnd.randint(40, 140)))


def _draw_category_art(layer, category: str, w: int, h: int, seed: int):
    """Dispatches to the dedicated creative procedural artwork for each category."""
    rnd = random.Random(seed)
    d = ImageDraw.Draw(layer)
    accent = theme_accent(category)
    cat_lower = category.lower()

    if "music" in cat_lower:
        _draw_music_art(d, w, h, accent, rnd)
    elif "comedy" in cat_lower:
        _draw_comedy_art(d, w, h, accent, rnd)
    elif "workshop" in cat_lower:
        _draw_workshop_art(d, w, h, accent, rnd)
    elif "cultural" in cat_lower:
        _draw_cultural_art(d, w, h, accent, rnd)
    elif "sport" in cat_lower:
        _draw_sports_art(d, w, h, accent, rnd)
    elif "network" in cat_lower:
        _draw_networking_art(d, w, h, accent, rnd)
    elif "career" in cat_lower:
        _draw_career_art(d, w, h, accent, rnd)
    else:
        _draw_other_art(d, w, h, accent, rnd)


def _sig(event, extra="") -> str:
    raw = "|".join(str(event.get(k, "")) for k in
                   ("title", "category", "event_date", "city", "start_time",
                    "base_price", "image_url")) + extra + "_v2_nobgletter"
    return hashlib.md5(raw.encode()).hexdigest()[:8]


def make_poster(event: dict) -> str:
    """600x800 portrait poster with rich creative artwork (no letter watermarks). Returns file path."""
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    path = POSTER_DIR / f"auto_{event['id']}_{_sig(event)}.jpg"
    if path.exists():
        return str(path)

    W, H = 600, 800
    category = event.get("category", "Other")
    c1, c2 = theme(category)
    accent = theme_accent(category)

    # Base gradient background
    img = _gradient(W, H, c1, c2)

    # Draw dedicated category artwork layer (no letters!)
    art_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_category_art(art_layer, category, W, H, seed=event.get("id", 1))
    img = Image.alpha_composite(img.convert("RGBA"), art_layer)

    # Cinematic dark gradient fade at the bottom for crystal-clear readability
    fade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fade)
    fade_start = int(H * 0.38)
    for y in range(fade_start, H):
        t = (y - fade_start) / (H - fade_start)
        alpha = int(235 * (t ** 1.3))
        fd.line([(0, y), (W, y)], fill=(10, 15, 24, alpha))
    img = Image.alpha_composite(img, fade)

    # Glassmorphism category badge chip on top left
    label = category_badge_label(category)
    cf = font(20)
    badge_tw = ImageDraw.Draw(img).textlength(label, font=cf)
    badge_w = int(badge_tw + 34)

    chip_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(chip_layer)
    cd.rounded_rectangle([32, 32, 32 + badge_w, 72], radius=20, fill=(255, 255, 255, 45),
                         outline=(255, 255, 255, 80), width=1)
    img = Image.alpha_composite(img, chip_layer).convert("RGB")
    d = ImageDraw.Draw(img)
    d.text((49, 52), label, font=cf, fill="white", anchor="lm")

    # Event Title
    size = 54
    while True:
        tf = font(size)
        lines = _wrap(d, event["title"], tf, W - 68)
        if len(lines) <= 3 or size <= 34:
            break
        size -= 4

    lh = int(size * 1.18)
    # Position text so everything fits cleanly
    y_title = H - 230 - (len(lines) - 1) * lh
    for ln in lines:
        d.text((34, y_title), ln, font=tf, fill="white")
        y_title += lh

    # Date and time stamp
    d.text((34, H - 150), f"📅 {fmt_date_short(event['event_date'])}  ·  {fmt_time(event['start_time'])}",
           font=font(26), fill=(241, 245, 249))

    # Venue and city
    venue_str = _fit(d, f"📍 {event['venue']}, {event['city']}", font(22), W - 68)
    d.text((34, H - 112), venue_str, font=font(22), fill=(203, 213, 225))

    # Price highlight pill
    price_text = "Free Entry" if not event["base_price"] else f"Tickets from {fmt_price(event['base_price'])}"
    pf = font(22)
    pw = d.textlength(price_text, font=pf)
    d.rounded_rectangle([34, H - 74, int(34 + pw + 28), H - 34], radius=14,
                        fill=(*accent, 220))
    d.text((48, H - 54), price_text, font=pf, fill=(15, 23, 42), anchor="lm")

    img.save(path, quality=90)
    return str(path)


def local_poster(event: dict) -> str:
    """A local image file for the event (uploaded one, else generated)."""
    img = (event.get("image_url") or "").strip()
    if img and not img.startswith("http") and Path(img).exists():
        return img
    return make_poster(event)


def poster_for(event: dict) -> str:
    """Path or URL to show on cards / detail pages."""
    img = (event.get("image_url") or "").strip()
    if img.startswith(("http://", "https://")):
        return img
    return local_poster(event)


def make_banner(event: dict) -> str:
    """1400x440 panoramic hero banner with creative artwork and poster card. Returns file path."""
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    path = POSTER_DIR / f"banner_{event['id']}_{_sig(event, 'b')}.jpg"
    if path.exists():
        return str(path)

    W, H = 1400, 440
    category = event.get("category", "Other")
    c1, c2 = theme(category)
    accent = theme_accent(category)

    # Horizontal gradient
    img = _gradient(W, H, c1, c2, horizontal=True)

    # Dedicated horizontal artwork
    art_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_category_art(art_layer, category, W, H, seed=event.get("id", 1) + 77)
    img = Image.alpha_composite(img.convert("RGBA"), art_layer)

    # Dark overlay on left for high-contrast typography
    left_fade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lfd = ImageDraw.Draw(left_fade)
    for x in range(int(W * 0.72)):
        alpha = int(220 * (1.0 - (x / (W * 0.72)) ** 2))
        lfd.line([(x, 0), (x, H)], fill=(10, 15, 24, alpha))
    img = Image.alpha_composite(img, left_fade)

    # Featured badge chip
    label = "⭐ FEATURED  ·  " + category_badge_label(category)
    cf = font(22)
    badge_tw = ImageDraw.Draw(img).textlength(label, font=cf)
    badge_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge_layer)
    bd.rounded_rectangle([56, 44, int(56 + badge_tw + 34), 86], radius=21,
                         fill=(255, 255, 255, 45), outline=(255, 255, 255, 75), width=1)
    img = Image.alpha_composite(img, badge_layer).convert("RGB")
    d = ImageDraw.Draw(img)
    d.text((73, 65), label, font=cf, fill="white", anchor="lm")

    # Title
    size = 62
    while True:
        tf = font(size)
        lines = _wrap(d, event["title"], tf, 780)
        if len(lines) <= 2 or size <= 36:
            break
        size -= 4

    y = 114
    for ln in lines:
        d.text((56, y), ln, font=tf, fill="white")
        y += int(size * 1.18)

    meta = (f"📅 {fmt_date_short(event['event_date'])} · {fmt_time(event['start_time'])}"
            f"   |   📍 {event['venue']}, {event['city']}")
    d.text((56, H - 110), meta[:75], font=font(24), fill=(241, 245, 249))

    price_text = "Free Entry" if not event["base_price"] else f"Tickets from {fmt_price(event['base_price'])}"
    pf = font(24)
    pw = d.textlength(price_text, font=pf)
    d.rounded_rectangle([56, H - 68, int(56 + pw + 32), H - 24], radius=14, fill=(*accent, 230))
    d.text((72, H - 46), price_text, font=pf, fill=(15, 23, 42), anchor="lm")

    # Poster card pasted on the right
    try:
        poster = Image.open(local_poster(event)).convert("RGB")
        ph = H - 60
        pw = int(poster.width * ph / poster.height)
        poster = poster.resize((pw, ph))
        mask = Image.new("L", (pw, ph), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], radius=20, fill=255)
        img = img.convert("RGB")
        img.paste(poster, (W - pw - 60, 30), mask)
    except Exception:
        pass

    img.convert("RGB").save(path, quality=90)
    return str(path)
