"""4x6 leave-behind card renderer (front + back) as print-ready PDF/PNG. Pure Pillow, no browser."""
import asyncio
import hashlib
import re
import tempfile
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "print_assets"
CACHE_DIR = Path(tempfile.gettempdir()) / "imos_print_cards"
S = 2  # supersample: canvas 1875x1275 @300dpi rendered at 2x -> 600dpi output
W, H = 1875, 1275  # 4x6 landscape + 0.125in bleed each side, at 300dpi
PAGE_IN = (6.25, 4.25)

BG = (10, 10, 15, 255)
WHITE = (255, 255, 255, 255)
RED, ORANGE, YELLOW = (255, 59, 48, 255), (255, 149, 0, 255), (255, 214, 10, 255)
GREEN, BLUE = (52, 199, 89, 255), (30, 139, 255, 255)
RAINBOW = [RED, ORANGE, YELLOW, GREEN, BLUE]
SOFT = (237, 237, 240, 255)

FA = {"user-group": "\uf500", "paper-plane": "\uf1d8", "gear": "\uf013", "chart-simple": "\ue473", "arrow": "\uf30b"}
_FONT_FILES = {"mont9": "Montserrat-900.ttf", "mont8": "Montserrat-800.ttf", "inter5": "Inter-500.ttf",
               "inter6": "Inter-600.ttf", "inter7": "Inter-700.ttf", "caveat": "Caveat-700.ttf", "fa": "fa-solid-900.ttf"}
_font_cache: dict = {}
_render_lock = asyncio.Semaphore(1)


def P(v: float) -> int:
    return int(round(v * S))


def font(name: str, size: float) -> ImageFont.FreeTypeFont:
    key = (name, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(ASSETS / "fonts" / _FONT_FILES[name]), P(size))
    return _font_cache[key]


def format_phone(e164: str) -> str:
    digits = re.sub(r"\D", "", e164 or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return e164 or ""


# ---------------------------------------------------------------- primitives
def composite(base: Image.Image, layer: Image.Image, x: int, y: int):
    """alpha_composite that tolerates negative / overflowing positions (crops the layer)."""
    lx, ly = max(0, -x), max(0, -y)
    rx, ry = min(layer.width, base.width - x), min(layer.height, base.height - y)
    if rx <= lx or ry <= ly:
        return
    base.alpha_composite(layer.crop((lx, ly, rx, ry)), (x + lx, y + ly))


def text(draw, x, y, s, f, fill, spacing=0.0):
    """Draw text at top-left (x, y) in 1x coords; spacing = extra letter-spacing (1x px). Returns end x (1x)."""
    if not spacing:
        draw.text((P(x), P(y)), s, font=f, fill=fill, anchor="la")
        return x + f.getlength(s) / S
    cx = P(x)
    for ch in s:
        draw.text((cx, P(y)), ch, font=f, fill=fill, anchor="la")
        cx += f.getlength(ch) + P(spacing)
    return (cx - P(spacing)) / S


def text_w(s, f, spacing=0.0):
    if not spacing:
        return f.getlength(s) / S
    return sum(f.getlength(ch) for ch in s) / S + spacing * (len(s) - 1)


def wrap(s, f, max_w):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if text_w(trial, f) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def rounded_mask(w, h, r):
    m = Image.new("L", (P(w), P(h)), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, P(w) - 1, P(h) - 1), radius=P(r), fill=255)
    return m


def shadow(base, w, h, r, x, y, blur=30, alpha=0.6, dx=0, dy=18, mask=None):
    pad = blur * 3
    layer = Image.new("RGBA", (P(w + 2 * pad), P(h + 2 * pad)), (0, 0, 0, 0))
    if mask is None:
        ImageDraw.Draw(layer).rounded_rectangle((P(pad), P(pad), P(pad + w), P(pad + h)), radius=P(r), fill=(0, 0, 0, int(255 * alpha)))
    else:
        a = mask.point(lambda v: int(v * alpha))
        layer.paste((0, 0, 0, 255), (P(pad), P(pad)), a)
    layer = layer.filter(ImageFilter.GaussianBlur(P(blur)))
    composite(base, layer, P(x - pad + dx), P(y - pad + dy))


def rotated(base, layer, x, y, deg):
    """Rotate layer around its center by deg (CSS sign: positive = clockwise), keep the center where it was."""
    rot = layer.rotate(-deg, resample=Image.BICUBIC, expand=True)
    cx, cy = P(x) + layer.width / 2, P(y) + layer.height / 2
    composite(base, rot, int(cx - rot.width / 2), int(cy - rot.height / 2))


def linear_gradient(w, h, stops):
    xs = np.linspace(0, 1, P(w))
    pos = np.linspace(0, 1, len(stops))
    arr = np.zeros((P(h), P(w), 4), dtype=np.uint8)
    for c in range(4):
        arr[:, :, c] = np.interp(xs, pos, [s[c] for s in stops])[None, :]
    return Image.fromarray(arr, "RGBA")


def conic_gradient(size, stops, start_deg):
    n = P(size)
    yy, xx = np.mgrid[0:n, 0:n]
    ang = (np.degrees(np.arctan2(yy - n / 2, xx - n / 2)) + 90 - start_deg) % 360 / 360.0
    pos = np.linspace(0, 1, len(stops))
    arr = np.zeros((n, n, 4), dtype=np.uint8)
    for c in range(4):
        arr[:, :, c] = np.interp(ang, pos, [s[c] for s in stops])
    return Image.fromarray(arr, "RGBA")


def radial_glow(base, cx, cy, rx, ry, color, max_alpha):
    yy, xx = np.mgrid[0:base.height, 0:base.width]
    d = np.sqrt(((xx - P(cx)) / P(rx)) ** 2 + ((yy - P(cy)) / P(ry)) ** 2)
    a = (np.clip(1 - d, 0, 1) ** 1.8 * 255 * max_alpha).astype(np.uint8)
    arr = np.zeros((base.height, base.width, 4), dtype=np.uint8)
    arr[:, :, :3] = color[:3]
    arr[:, :, 3] = a
    base.alpha_composite(Image.fromarray(arr, "RGBA"))


def qr_image(qr, inner: int) -> Image.Image:
    """Crisp QR at exactly inner px (1x): integer module scale, centered on white."""
    n = qr.modules_count + 2 * qr.border
    k = max(1, P(inner) // n)
    img = qr.make_image(fill_color="#000000", back_color="#FFFFFF").convert("RGB")
    img = img.resize((n * k, n * k), Image.NEAREST)
    out = Image.new("RGB", (P(inner), P(inner)), "white")
    out.paste(img, ((P(inner) - n * k) // 2, (P(inner) - n * k) // 2))
    return out.convert("RGBA")


def phone(shot_path: Path, width: float) -> Image.Image:
    """iPhone-style frame with the screenshot inside. Returns RGBA layer (with room for shadow)."""
    bezel, pad = 14, 60
    sw = width - 2 * bezel
    shot = Image.open(shot_path).convert("RGBA")
    sh = sw * shot.height / shot.width
    fh = sh + 2 * bezel
    layer = Image.new("RGBA", (P(width + 2 * pad), P(fh + 2 * pad)), (0, 0, 0, 0))
    shadow(layer, width, fh, width * 0.13, pad, pad, blur=28, alpha=0.7, dy=26)
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((P(pad), P(pad), P(pad + width), P(pad + fh)), radius=P(width * 0.13), fill=(21, 21, 26, 255), outline=(255, 255, 255, 60), width=P(1.5))
    screen = shot.resize((P(sw), P(sh)), Image.LANCZOS)
    layer.paste(screen, (P(pad + bezel), P(pad + bezel)), rounded_mask(sw, sh, width * 0.13 - bezel))
    iw, ih = width * 0.24, 28
    d.rounded_rectangle((P(pad + width / 2 - iw / 2), P(pad + bezel + 12), P(pad + width / 2 + iw / 2), P(pad + bezel + 12 + ih)), radius=P(ih / 2), fill=(0, 0, 0, 255))
    return layer, pad


# ---------------------------------------------------------------- FRONT
def render_front(qr, rep_first: str, sms_number: str) -> Image.Image:
    im = Image.new("RGBA", (P(W), P(H)), BG)
    d = ImageDraw.Draw(im)

    tile = 540
    lx, ly = 95, 130
    shadow(im, tile, tile, tile * 0.2237, lx, ly, blur=26, alpha=0.6, dy=22)
    icon = Image.open(ASSETS / "icon.png").convert("RGBA").resize((P(tile), P(tile)), Image.LANCZOS)
    icon.putalpha(rounded_mask(tile, tile, tile * 0.2237))
    composite(im, icon, P(lx), P(ly))

    tx = 710
    end = text(d, tx, 130, "I'M ON ", font("mont9", 136), WHITE)
    end = text(d, end, 130, "SOCIAL", font("mont9", 136), BLUE)
    text(d, end + 8, 146, "TM", font("mont8", 26), WHITE)
    text(d, tx, 292, "THE RELATIONSHIP OS", font("inter5", 40), WHITE, spacing=16)

    props = [("user-group", RED, "REMEMBER", "every contact"), ("paper-plane", BLUE, "ENGAGE", "every relationship"),
             ("gear", GREEN, "AUTOMATE", "every touchpoint"), ("chart-simple", YELLOW, "GROW", "every opportunity")]
    col_w, top = (1790 - tx) / 4, 425
    for i, (icon, color, label, sub) in enumerate(props):
        cx = tx + col_w * i + col_w / 2
        if i:
            d.rectangle((P(tx + col_w * i), P(top), P(tx + col_w * i + 2), P(top + 190)), fill=(255, 255, 255, 90))
        f_icon = font("fa", 74)
        text(d, cx - text_w(FA[icon], f_icon) / 2, top + 4, FA[icon], f_icon, color)
        f_l = font("mont8", 38)
        text(d, cx - text_w(label, f_l) / 2, top + 104, label, f_l, WHITE)
        f_s = font("inter5", 28)
        text(d, cx - text_w(sub, f_s) / 2, top + 152, sub, f_s, SOFT)

    hook = Image.new("RGBA", (P(1000), P(200)), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hook)
    f_hook = font("caveat", 66)
    text(hd, 10, 10, "Your CRM remembers the sale.", f_hook, WHITE)
    text(hd, 60, 86, "We remember the person.", f_hook, BLUE)
    rotated(im, hook, 95, 880, -3)

    f_tag = font("inter6", 30)
    x = text(d, 100, 1132, "PEOPLE", f_tag, WHITE, spacing=7)
    for sep_color, word in [(RED, "CONVERSATIONS"), (GREEN, "RELATIONSHIPS"), (YELLOW, "FOR LIFE")]:
        x = text(d, x + 28, 1132, "|", font("inter5", 30), sep_color)
        x = text(d, x + 28, 1132, word, f_tag, WHITE, spacing=7)

    # "See -> I'M ON SOCIAL IN ACTION" pointer block
    see_cx = 1270
    f_see = font("caveat", 84)
    see_layer = Image.new("RGBA", (P(240), P(120)), (0, 0, 0, 0))
    text(ImageDraw.Draw(see_layer), 10, 8, "See", f_see, WHITE)
    rotated(im, see_layer, see_cx - 150, 900, -8)
    f_arrow = font("fa", 66)
    arrow_layer = Image.new("RGBA", (P(100), P(100)), (0, 0, 0, 0))
    text(ImageDraw.Draw(arrow_layer), 10, 14, FA["arrow"], f_arrow, BLUE)
    rotated(im, arrow_layer, see_cx + 30, 910, -12)
    f_l1 = font("mont9", 36)
    text(d, see_cx - text_w("I'M ON SOCIAL", f_l1) / 2, 1012, "I'M ON SOCIAL", f_l1, BLUE)
    text(d, see_cx - text_w("IN ACTION", f_l1, 2) / 2, 1056, "IN ACTION", f_l1, WHITE, spacing=2)

    # QR frame
    fx, fy, fs = 1460, 800, 300
    shadow(im, fs, fs, 26, fx, fy, blur=24, alpha=0.6, dy=20)
    ring = conic_gradient(fs, [BLUE, GREEN, YELLOW, ORANGE, RED, BLUE], 210)
    ring.putalpha(rounded_mask(fs, fs, 26))
    composite(im, ring, P(fx), P(fy))
    inner = fs - 20
    white = Image.new("RGBA", (P(inner), P(inner)), WHITE)
    white.putalpha(rounded_mask(inner, inner, 18))
    composite(im, white, P(fx + 10), P(fy + 10))
    q = qr_image(qr, inner - 24)
    composite(im, q, P(fx + 22), P(fy + 22))
    f_url = font("inter7", 22)
    url = "IMONSOCIAL.COM"
    text(d, fx + fs / 2 - text_w(url, f_url, 5) / 2, fy + fs + 16, url, f_url, WHITE, spacing=5)
    if sms_number:
        label = f"Text {rep_first}: " if rep_first else "Text us: "
        num = format_phone(sms_number)
        f_rep = font("inter7", 26)
        total = text_w(label, f_rep) + text_w(num, f_rep)
        sx = fx + fs / 2 - total / 2
        sx = text(d, sx, fy + fs + 50, label, f_rep, BLUE)
        text(d, sx, fy + fs + 50, num, f_rep, WHITE)
    return im


# ---------------------------------------------------------------- BACK (white stock: cheaper to print, same message, colors reversed)
INK = (16, 16, 20, 255)
INK_SOFT = (58, 58, 66, 255)
YELLOW_INK = (232, 176, 0, 255)


def render_back() -> Image.Image:
    im = Image.new("RGBA", (P(W), P(H)), WHITE)
    radial_glow(im, 1420, 900, 620, 640, BLUE, 0.14)
    d = ImageDraw.Draw(im)

    f_h = font("mont9", 78)
    lines = [[("YOU DON'T NEED", INK)], [("MORE CONTACTS.", INK)], [("YOU NEED TO", BLUE)],
             [("REMEMBER", GREEN), (" THE ONES", ORANGE)], [("YOU ALREADY", YELLOW_INK), (" HAVE.", RED)]]
    y = 96
    for parts in lines:
        x = 100
        for s, color in parts:
            x = text(d, x, y, s, f_h, color)
        y += 78

    bar = linear_gradient(560, 10, RAINBOW)
    bar.putalpha(rounded_mask(560, 10, 5))
    composite(im, bar, P(100), P(516))

    f_body = font("inter5", 33)
    body = ("I'm On Social is the Relationship OS that remembers the people, conversations and details "
            "that matter, then helps you stay engaged automatically.")
    y = 556
    for line in wrap(body, f_body, 720):
        text(d, 100, y, line, f_body, INK_SOFT)
        y += 46

    script = Image.new("RGBA", (P(900), P(260)), (0, 0, 0, 0))
    sd = ImageDraw.Draw(script)
    f_sc = font("caveat", 86)
    text(sd, 10, 10, "Stay connected.", f_sc, INK)
    end = text(sd, 40, 100, "Be the one they remember.", f_sc, BLUE)
    sd.rounded_rectangle((P(70), P(206), P(end + 10), P(212)), radius=P(3), fill=BLUE)
    rotated(im, script, 90, 745, -5)

    f_b = font("mont9", 58)
    end = text(d, 100, 1035, "I'M ON ", f_b, INK)
    end = text(d, end, 1035, "SOCIAL", f_b, BLUE)
    text(d, end + 6, 1041, "TM", font("mont8", 18), INK)
    text(d, 100, 1106, "IMONSOCIAL.COM", font("inter6", 28), INK, spacing=8)
    f_t = font("inter6", 22)
    x = text(d, 100, 1156, "CONNECT", f_t, INK, spacing=5)
    for sep_color, word in [(RED, "AUTOMATE"), (GREEN, "STAY IN TOUCH")]:
        x = text(d, x + 22, 1156, "|", font("inter5", 22), sep_color)
        x = text(d, x + 22, 1156, word, f_t, INK, spacing=5)

    f_m = font("inter5", 29)
    y = 100
    for line in ["STRONGER", "RELATIONSHIPS", "DRIVE A", "BRIGHTER", "TOMORROW."]:
        wdt = text_w(line, f_m, 10)
        text(d, 1775 - wdt, y, line, f_m, INK, spacing=10)
        if line.startswith("TOMORROW"):
            text(d, 1775 + 4, y - 4, "TM", font("inter6", 15), INK)
        y += 45

    back_phone, pad = phone(ASSETS / "inbox.jpg", 470)
    rotated(im, back_phone, 1010 - pad, 520 - pad, -8)
    front_phone, pad = phone(ASSETS / "people-today.jpg", 470)
    rotated(im, front_phone, 1290 - pad, 400 - pad, 5)
    return im


# ---------------------------------------------------------------- outputs
def _jpeg(img: Image.Image, quality=92) -> bytes:
    buf = BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality, dpi=(300 * S, 300 * S), subsampling=0)
    return buf.getvalue()


BLEED_IN = 0.125
LAYOUTS = ("bleed", "exact", "letter")


def _trim(img: Image.Image) -> Image.Image:
    b = P(BLEED_IN * 300)
    return img.crop((b, b, img.width - b, img.height - b))


def _build_pdf(front: Image.Image, back: Image.Image, layout: str = "bleed") -> bytes:
    """bleed: 6.25x4.25 for print shops. exact: true 4x6 (6x4) for photo paper. letter: 4x6 centered on 8.5x11 with cut marks."""
    from fpdf import FPDF
    card_w, card_h = PAGE_IN[0] - 2 * BLEED_IN, PAGE_IN[1] - 2 * BLEED_IN
    if layout == "letter":
        pdf = FPDF(unit="in", format="Letter")
    else:
        pdf = FPDF(unit="in", format=PAGE_IN if layout == "bleed" else (card_w, card_h))
    pdf.set_margins(0, 0, 0)
    pdf.set_auto_page_break(False)
    pdf.set_title("i'M On Social 4x6 leave-behind card")
    for page in (front, back):
        pdf.add_page()
        if layout == "bleed":
            pdf.image(BytesIO(_jpeg(page)), x=0, y=0, w=PAGE_IN[0], h=PAGE_IN[1])
            continue
        x, y = ((pdf.w - card_w) / 2, (pdf.h - card_h) / 2) if layout == "letter" else (0, 0)
        pdf.image(BytesIO(_jpeg(_trim(page))), x=x, y=y, w=card_w, h=card_h)
        if layout == "letter":
            pdf.set_draw_color(140, 140, 140)
            pdf.set_line_width(0.004)
            gap, ln = 0.06, 0.25
            for cx in (x, x + card_w):
                for cy in (y, y + card_h):
                    sx, sy = (1 if cx == x else -1), (1 if cy == y else -1)
                    pdf.line(cx, cy - sy * gap, cx, cy - sy * (gap + ln))
                    pdf.line(cx - sx * gap, cy, cx - sx * (gap + ln), cy)
            pdf.set_font("Helvetica", size=8)
            pdf.set_text_color(120, 120, 120)
            pdf.set_xy(0, y + card_h + 0.45)
            pdf.cell(pdf.w, 0.2, "Print at Actual Size (100%). Cut along the marks for a true 4x6 in card.", align="C")
    return bytes(pdf.output())


def _cache_key(*parts) -> str:
    stamp = str(Path(__file__).stat().st_mtime) + str(max(p.stat().st_mtime for p in ASSETS.rglob("*") if p.is_file()))
    return hashlib.sha1("|".join([stamp, *map(str, parts)]).encode()).hexdigest()[:20]


def _render_sync(qr, rep_first, sms_number, kind, side, width, layout) -> bytes:
    if kind == "pdf":
        return _build_pdf(render_front(qr, rep_first, sms_number), render_back(), layout)
    img = render_front(qr, rep_first, sms_number) if side == "front" else render_back()
    width = max(300, min(int(width or 900), W * S))
    img = img.convert("RGB").resize((width, int(width * H / W)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, "PNG", dpi=(300, 300))
    return buf.getvalue()


async def render_card(qr, rep_first: str, sms_number: str, kind: str = "pdf", side: str = "front", width: int = 900, layout: str = "bleed") -> bytes:
    """kind='pdf' -> 2-page print PDF (layout: bleed | exact | letter); kind='png' -> preview of one side at `width` px. Disk-cached."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(qr.data_list[0].data if qr.data_list else "", rep_first, sms_number, kind, side, width, layout)
    path = CACHE_DIR / f"{key}.{kind}"
    if path.exists():
        return path.read_bytes()
    async with _render_lock:
        if path.exists():
            return path.read_bytes()
        data = await asyncio.to_thread(_render_sync, qr, rep_first, sms_number, kind, side, width, layout)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return data
